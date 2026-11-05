#!/usr/bin/env python3
"""Trade Empire for trader-timemachine. Standard library only. Paper money only.

Runs every strategy in the pack ("skills") on real past market data with a
paper account each, then ranks them like an empire: who earned the most, who
lost the most, the win rate with its honest error bars, the drawdown, and the
odds each skill stays green over its next 20 trades if it keeps trading the
way it did. No order is ever placed. No real money is ever used.

    python3 empire.py run --demo                     # the recorded real data shipped with the pack
    python3 empire.py run --demo --write             # also save trader/empire.json and trader/empire.html
    python3 empire.py run --symbols TSLA,AAPL,NVDA   # live: 60 days of 5-min bars + 1 year of daily closes
    python3 empire.py run --offline TSLA-60d5m.json.gz --daily spark.json
    python3 empire.py run --demo --json

Two provinces:
  Day trading (5-minute bars, one trade per skill per day, long only, flat by
  3:55 PM, no entries before 9:45 AM or after 3:30 PM). Each trade risks at
  most $50 (max_loss_per_trade_usd) and buys at most $4,000 (max_order_usd),
  the same sizing as trader-budget. A bar that touches both the stop and the
  target counts as the stop. A bar that opens through the stop fills at its
  open, which can be worse than the stop. Every fill pays 1 cent a share of
  slippage on the way in and on the way out.
  Swing trading (daily closes, one position per stock at a time, at most 5
  open, $1,000 a position). Entries and exits at the close.

Every skill gets its own $5,000 paper account. The empire's treasury is the
sum of all of them. The numbers are exactly what the rules did on that data,
nothing more: past or simulated results are not a forecast and never a
promise of future wins. Most day traders lose money.

Stats per skill:
  wins / losses   a trade that made money after slippage / one that did not
  win rate        wins / trades, with a 95 % Wilson interval (small samples
                  have wide intervals: 9 of 15 is 60 %, but anywhere from
                  36 % to 80 % is consistent with it)
  profit factor   gross profit / gross loss
  expectancy      average dollars per trade
  max drawdown    the deepest fall of the account from its high, in dollars
  odds green      bootstrap: draw 20 trades at random (with replacement) from
                  the skill's own past trades, 10,000 times, seed 19; the share
                  of draws that end above zero. A skill with a lucky past looks
                  lucky here too: it measures the past, not the future.
"""

import argparse
import datetime
import gzip
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import timemachine as tm  # noqa: E402  (same folder: the time, the data and the bars)

ROOT = os.path.dirname(HERE)
DEMO_INTRADAY = os.path.join(ROOT, "tests", "fixtures", "trader-timemachine", "TSLA-60d5m.json.gz")
DEMO_DAILY = os.path.join(ROOT, "tests", "fixtures", "trader-scanner", "spark-3mo-live-2026-10-20.json")

ACCOUNT = 5000.0
MAX_LOSS = 50.0          # dollars at risk per day trade
MAX_ORDER = 4000.0       # dollars per day trade
SWING_SIZE = 1000.0      # dollars per swing position
SWING_MAX_OPEN = 5
SLIP = 0.01              # dollars a share, each side
FIRST_ENTRY = 2          # bar 2 closes at 9:45
LAST_ENTRY = 71          # bar 71 closes at 3:30
FLAT = 76                # bar 76 closes at 3:55
BOOT_TRADES = 20
BOOT_RUNS = 10000
SEED = 19
MIN_TITLE_TRADES = 10   # fewer trades than this: a Squire, not ranked for a crown
TITLES = ("Emperor", "King", "Duke", "Count", "Baron", "Knight")
DISCLAIMER = ("Paper trading on past data. No real money, no real orders. Past or simulated results do not "
              "guarantee future wins. Education and tooling, not financial advice.")


class EmpireError(Exception):
    pass


# ---------------------------------------------------------------- helpers

def ema(values, n):
    k = 2.0 / (n + 1)
    out, e = [], None
    for v in values:
        e = v if e is None else e + k * (v - e)
        out.append(e)
    return out


def vwap(D):
    out, pv, vv = [], 0.0, 0.0
    for b in D:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        v = b["v"] or 1
        pv += tp * v
        vv += v
        out.append(pv / vv)
    return out


def clock_after(k):
    """The time bar k closes, as 10:15 AM."""
    return tm.clock12(tm.OPEN_MIN + 5 * (k + 1))


def wilson(wins, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = wins / float(n)
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


# ---------------------------------------------------------------- the day-trading skills
# Each returns None (no trade today) or {k, entry, stop, target, exit_rule}.
# k is the bar whose close is the entry (or the bar where a stop order fills).

def _plan(k, entry, stop, r):
    entry = round(entry, 2)
    stop = tm.cents_away(stop, True)
    risk = entry - stop
    if risk <= max(0.01, entry * 0.0005):
        return None
    return {"k": k, "entry": entry, "stop": stop,
            "target": round(entry + r * risk, 2) if r else None, "exit_rule": None}


def orb_1r(D, prev_close):
    oh, ol = tm.opening_range(D, 3)
    k = next((i for i in range(3, LAST_ENTRY + 1) if D[i]["c"] > oh), None)
    return None if k is None else _plan(k, D[k]["c"], (oh + ol) / 2, 1.0)


def orb_2r(D, prev_close):
    oh, ol = tm.opening_range(D, 3)
    k = next((i for i in range(3, LAST_ENTRY + 1) if D[i]["c"] > oh), None)
    return None if k is None else _plan(k, D[k]["c"], ol, 2.0)


def vwap_reclaim(D, prev_close):
    vw = vwap(D)
    for i in range(6, LAST_ENTRY + 1):
        if D[i - 1]["c"] < vw[i - 1] and D[i]["c"] > vw[i]:
            return _plan(i, D[i]["c"], min(b["l"] for b in D[i - 5:i + 1]), 2.0)
    return None


def dip_bounce(D, prev_close):
    o = D[0]["o"]
    low = D[0]["l"]
    for i in range(1, LAST_ENTRY + 1):
        low = min(low, D[i]["l"])
        if i >= FIRST_ENTRY + 1 and low <= o * 0.99 and D[i]["c"] < o and D[i]["c"] > D[i - 1]["h"]:
            return _plan(i, D[i]["c"], low, 1.5)
    return None


def ema_trend(D, prev_close):
    closes = [b["c"] for b in D]
    fast, slow, vw = ema(closes, 9), ema(closes, 21), vwap(D)
    for i in range(6, LAST_ENTRY + 1):
        if fast[i - 1] <= slow[i - 1] and fast[i] > slow[i] and D[i]["c"] > vw[i]:
            rng = sum(b["h"] - b["l"] for b in D[max(0, i - 11):i + 1]) / float(min(12, i + 1))
            p = _plan(i, D[i]["c"], D[i]["c"] - 2 * rng, None)
            if p:
                p["exit_rule"] = lambda j: fast[j] < slow[j]
                p["exit_name"] = "9 EMA under 21 EMA"
            return p
    return None


def gap_go(D, prev_close):
    if prev_close is None or D[0]["o"] < prev_close * 1.01:
        return None
    oh, ol = tm.opening_range(D, 3)
    trigger = round(oh + 0.01, 2)
    for i in range(3, LAST_ENTRY + 1):
        if D[i]["h"] >= trigger:
            p = _plan(i, max(trigger, D[i]["o"]), ol, 2.0)
            if p:
                p["stop_order"] = True
            return p
    return None


def power_hour(D, prev_close):
    for i in range(54, LAST_ENTRY + 1):
        if D[i]["c"] > max(b["h"] for b in D[:i]):
            return _plan(i, D[i]["c"], min(b["l"] for b in D[i - 5:i + 1]), 1.5)
    return None


DAY_SKILLS = [
    ("orb_1r", "Opening Range Breaker", "15-minute opening-range breakout, stop at the range midpoint, target 1R "
     "(the pack's own reel trade)", orb_1r),
    ("orb_2r", "Range Breakout 2R", "15-minute opening-range breakout, stop under the range, target 2R", orb_2r),
    ("vwap_reclaim", "VWAP Reclaimer", "first close back above VWAP after 10:00, stop under the last 30 minutes, "
     "target 2R", vwap_reclaim),
    ("dip_bounce", "Dip Hunter", "the stock falls 1 % below its open, then a bar closes above the last bar's "
     "high: buy the bounce, stop at the day's low, target 1.5R", dip_bounce),
    ("ema_trend", "Trend Rider", "9 EMA crosses over 21 EMA above VWAP on 5-minute bars, stop 2 average bars "
     "away, out when the 9 drops back under the 21", ema_trend),
    ("gap_go", "Gap Runner", "gap up 1 % or more: buy-stop 1 cent over the 15-minute high, stop under it, "
     "target 2R", gap_go),
    ("power_hour", "Power Hour", "a new high of the day after 2:00 PM, stop under the last 30 minutes, "
     "target 1.5R", power_hour),
]


def walk(D, p):
    """Run one planned trade bar by bar to the 3:55 close. Returns (exit price, outcome, exit bar)."""
    s, t = p["stop"], p["target"]
    start = p["k"] + (0 if p.get("stop_order") else 1)
    for j in range(start, FLAT + 1):
        b = D[j]
        if j == p["k"] and p.get("stop_order"):
            # the bar that filled the buy-stop: only its low after the fill can hit the stop, and we do
            # not know the order inside the bar, so the conservative call is: a low under the stop is a stop
            if b["l"] <= s:
                return s, "stop", j
            continue
        if b["o"] <= s:
            return b["o"], "stop (gap)", j
        if b["l"] <= s:
            return s, "stop", j
        if t is not None and b["h"] >= t:
            return max(t, b["o"]), "target", j
        if p.get("exit_rule") and p["exit_rule"](j):
            return b["c"], "exit signal", j
    return D[FLAT]["c"], "flat 3:55", FLAT


def run_day_skill(fn, sessions, prev_closes):
    trades = []
    for (d, D) in sessions:
        p = fn(D, prev_closes.get(d))
        if not p or p["k"] < FIRST_ENTRY or p["k"] > LAST_ENTRY:
            continue
        risk = p["entry"] - p["stop"]
        shares = int(min(MAX_LOSS / risk, MAX_ORDER / p["entry"]))
        if shares < 1:
            continue
        px, outcome, j = walk(D, p)
        pnl = round(shares * ((px - SLIP) - (p["entry"] + SLIP)), 2)
        trades.append({"date": d, "in": clock_after(p["k"]) if not p.get("stop_order") else
                       tm.clock12(tm.OPEN_MIN + 5 * p["k"]) + " (stop order)",
                       "out": clock_after(j), "shares": shares, "entry": p["entry"], "stop": p["stop"],
                       "target": p["target"], "exit": round(px, 2), "outcome": outcome, "pnl": pnl,
                       "R": round(pnl / (shares * risk), 2)})
    return trades


# ---------------------------------------------------------------- the swing skills (daily closes)

def three_red(closes, i, entry_i):
    """Entry: three lower closes in a row. Exit: +5 %, -5 %, or 5 days."""
    if entry_i is None:
        return i >= 3 and closes[i] < closes[i - 1] < closes[i - 2] < closes[i - 3]
    e = closes[entry_i]
    return closes[i] >= e * 1.05 or closes[i] <= e * 0.95 or i - entry_i >= 5


def breakout20(closes, i, entry_i):
    """Entry: a close above the last 20 closes. Exit: a close under the last 10, or 15 days."""
    if entry_i is None:
        return i >= 20 and closes[i] > max(closes[i - 20:i])
    return closes[i] < min(closes[i - 10:i]) or i - entry_i >= 15


SWING_SKILLS = [
    ("three_red", "Bargain Hunter", "three lower daily closes in a row: buy the close, sell at +5 %, -5 % or "
     "after 5 days", three_red),
    ("breakout20", "20-Day Breakout", "a daily close above the last 20 closes: buy, sell on a close under the last "
     "10 or after 15 days", breakout20),
]


def run_swing_skill(fn, series):
    """series: {sym: [(date, close), ...]}. One position per stock, at most SWING_MAX_OPEN open."""
    dates = sorted(set(d for s in series.values() for d, _ in s))
    idx = {sym: {d: n for n, (d, _) in enumerate(s)} for sym, s in series.items()}
    closes = {sym: [c for _, c in s] for sym, s in series.items()}
    open_pos, trades = {}, []
    for d in dates:
        for sym in sorted(series):
            i = idx[sym].get(d)
            if i is None:
                continue
            c = closes[sym]
            if sym in open_pos:
                ei, sh = open_pos[sym]
                last = i == len(c) - 1
                if fn(c, i, ei) or last:
                    pnl = round(sh * ((c[i] - SLIP) - (c[ei] + SLIP)), 2)
                    trades.append({"date": series[sym][ei][0], "symbol": sym, "out_date": d, "shares": sh,
                                   "entry": round(c[ei], 2), "exit": round(c[i], 2), "days": i - ei,
                                   "outcome": "still open at the end (marked at the close)" if last and not
                                   fn(c, i, ei) else "exit rule", "pnl": pnl})
                    del open_pos[sym]
            elif len(open_pos) < SWING_MAX_OPEN and i < len(c) - 1 and fn(c, i, None):
                sh = int(SWING_SIZE / c[i])
                if sh >= 1:
                    open_pos[sym] = (i, sh)
    trades.sort(key=lambda t: (t["out_date"], t["symbol"]))
    return trades


# ---------------------------------------------------------------- stats

def stats(trades, seed=SEED):
    pnls = [t["pnl"] for t in trades]
    n = len(pnls)
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]
    eq, peak, dd, curve = ACCOUNT, ACCOUNT, 0.0, [ACCOUNT]
    streak = worst_streak = 0
    for x in pnls:
        eq += x
        curve.append(round(eq, 2))
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        streak = streak + 1 if x <= 0 else 0
        worst_streak = max(worst_streak, streak)
    lo, hi = wilson(len(wins), n)
    gp, gl = sum(wins), -sum(losses)
    odds = None
    if n >= 5:
        rng = random.Random(seed)
        odds = sum(1 for _ in range(BOOT_RUNS) if sum(rng.choice(pnls) for _ in range(BOOT_TRADES)) > 0) \
            / float(BOOT_RUNS)
    return {
        "trades": n, "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / float(n), 4) if n else None,
        "win_rate_95": [round(lo, 4), round(hi, 4)],
        "pnl": round(sum(pnls), 2), "end_balance": round(ACCOUNT + sum(pnls), 2),
        "return_pct": round(100 * sum(pnls) / ACCOUNT, 2),
        "avg_win": round(gp / len(wins), 2) if wins else 0.0,
        "avg_loss": round(-gl / len(losses), 2) if losses else 0.0,
        "profit_factor": round(gp / gl, 2) if gl > 0 else None,
        "expectancy": round(sum(pnls) / n, 2) if n else 0.0,
        "best": round(max(pnls), 2) if pnls else 0.0, "worst": round(min(pnls), 2) if pnls else 0.0,
        "max_drawdown": round(dd, 2), "max_drawdown_pct": round(100 * dd / ACCOUNT, 2),
        "losing_streak": worst_streak, "odds_green_next_20": odds, "curve": curve,
    }


def verdict(s):
    if s["trades"] < 10:
        return "Too few trades to judge"
    if s["pnl"] > 0 and s["win_rate_95"][0] > 0.5:
        return "Made money and won more often than not, even at the low end of its interval"
    if s["pnl"] > 0 and (s["profit_factor"] or 0) >= 1.3:
        return "Made money here, but the sample is small: could still be luck"
    if s["pnl"] > 0:
        return "Barely positive: close to break-even after slippage"
    if s["pnl"] > -0.5 * MAX_LOSS:
        return "Close to break-even, slightly negative"
    return "Lost money on this data"


def crown(skills):
    """Sort by P&L and hand out titles: the best earner with 10+ trades is Emperor, then King, Duke...;
    losers are Peasants, the worst is Exiled; under 10 trades is a Squire whatever it made."""
    skills.sort(key=lambda s: -s["stats"]["pnl"])
    up = 0
    for n, s in enumerate(skills):
        if s["stats"]["trades"] < MIN_TITLE_TRADES:
            s["title"] = "Squire"   # too few trades to earn a crown or lose one
        elif s["stats"]["pnl"] > 0:
            s["title"] = TITLES[min(up, len(TITLES) - 1)]
            up += 1
        elif s["stats"]["pnl"] < 0 and all(x["stats"]["pnl"] >= s["stats"]["pnl"] for x in skills
                                           if x["stats"]["trades"] >= MIN_TITLE_TRADES):
            s["title"] = "Exiled"
        else:
            s["title"] = "Peasant"
        s["rank"] = n + 1
    return skills


# ---------------------------------------------------------------- data

def load_intraday(text, sym):
    meta, bars, _ = tm.parse_bars(tm.chart_result(text, sym), datetime.datetime(2100, 1, 1))
    days = tm.split_sessions(bars)
    sessions, short = tm.full_sessions(days, "9999-12-31")
    prev, last = {}, None
    for d in sorted(days):
        if last is not None:
            prev[d] = days[last][max(days[last])]["c"]
        last = d
    return sessions, prev, short


def parse_daily(text):
    """A Yahoo spark JSON ({spark: {result: [...]}}) or a list of chart results -> {sym: [(date, close)]}."""
    data = json.loads(text)
    out = {}
    rows = []
    if isinstance(data, dict) and "spark" in data:
        for r in data["spark"].get("result") or []:
            rows.extend((r.get("symbol"), x) for x in r.get("response") or [])
    elif isinstance(data, dict) and "chart" in data:
        res = data["chart"].get("result") or []
        rows.extend(((x.get("meta") or {}).get("symbol"), x) for x in res)
    for sym, x in rows:
        ts = x.get("timestamp") or []
        cl = (((x.get("indicators") or {}).get("quote") or [{}])[0] or {}).get("close") or []
        pts = []
        for t, c in zip(ts, cl):
            if t is None or c is None:
                continue
            pts.append((tm.to_eastern(tm.utc_of(t)).date().isoformat(), float(c)))
        if len(pts) >= 25 and sym:
            out[sym] = pts
    return out


def read_text(path):
    if not os.path.exists(path):
        raise EmpireError("no file %s" % path)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return fh.read()


def fetch_daily(sym):
    url = "https://query2.finance.yahoo.com/v8/finance/chart/%s?range=1y&interval=1d" % sym.upper()
    try:
        return tm._get(url)
    except Exception as e:
        raise EmpireError("could not fetch daily closes for %s: %s" % (sym, e))


# ---------------------------------------------------------------- the run

def run(intraday, daily, source):
    """intraday: [(sym, text)], daily: {sym: [(date, close)]}."""
    skills, periods = [], []
    benchmarks = []
    for key, name, rule, fn in DAY_SKILLS:
        trades = []
        for sym, (sessions, prev) in intraday:
            for t in run_day_skill(fn, sessions, prev):
                t["symbol"] = sym
                trades.append(t)
        trades.sort(key=lambda t: (t["date"], t["symbol"]))
        skills.append({"key": key, "name": name, "rule": rule, "province": "Day trading (5-minute bars)",
                       "trades": trades, "stats": stats(trades)})
    for sym, (sessions, prev) in intraday:
        if sessions:
            periods.append("%s %s to %s, %d full sessions" % (sym, sessions[0][0], sessions[-1][0], len(sessions)))
            o, c = sessions[0][1][0]["o"], sessions[-1][1][FLAT]["c"]
            sh = int(MAX_ORDER / o)
            benchmarks.append({"name": "Buy and hold %s" % sym, "detail": "%d shares at the first open %.2f, "
                               "held to %.2f" % (sh, o, c), "pnl": round(sh * (c - o), 2)})
    if daily:
        for key, name, rule, fn in SWING_SKILLS:
            trades = run_swing_skill(fn, daily)
            skills.append({"key": key, "name": name, "rule": rule, "province": "Swing trading (daily closes)",
                           "trades": trades, "stats": stats(trades)})
        first = min(s[0][0] for s in daily.values())
        last = max(s[-1][0] for s in daily.values())
        periods.append("%d stocks, daily closes %s to %s" % (len(daily), first, last))
        per = ACCOUNT / len(daily)
        bh = sum(int(per / s[0][1]) * (s[-1][1] - s[0][1]) for s in daily.values())
        benchmarks.append({"name": "Buy and hold all %d stocks" % len(daily),
                           "detail": "$%.0f in each (one $5,000 account) at the first close, held to the last" % per,
                           "pnl": round(bh, 2)})
    for s in skills:
        s["verdict"] = verdict(s["stats"])
    crown(skills)
    all_trades = [t for s in skills for t in s["trades"]]
    total = sum(t["pnl"] for t in all_trades)
    wins = sum(1 for t in all_trades if t["pnl"] > 0)
    lo, hi = wilson(wins, len(all_trades))
    empire = {
        "accounts": len(skills), "start": ACCOUNT * len(skills), "treasury": round(ACCOUNT * len(skills) + total, 2),
        "pnl": round(total, 2), "trades": len(all_trades), "wins": wins, "losses": len(all_trades) - wins,
        "win_rate": round(wins / float(len(all_trades)), 4) if all_trades else None,
        "win_rate_95": [round(lo, 4), round(hi, 4)],
        "profitable_skills": sum(1 for s in skills if s["stats"]["pnl"] > 0),
        "losing_skills": sum(1 for s in skills if s["stats"]["pnl"] <= 0),
    }
    return {"source": source, "periods": periods, "disclaimer": DISCLAIMER, "seed": SEED,
            "rules": {"account": ACCOUNT, "max_loss_per_trade": MAX_LOSS, "max_order": MAX_ORDER,
                      "slippage_per_share_each_side": SLIP, "no_entries_before": "09:45",
                      "no_entries_after": "15:30", "flat_by": "15:55", "long_only": True,
                      "swing_position": SWING_SIZE, "swing_max_open": SWING_MAX_OPEN},
            "empire": empire, "skills": skills, "benchmarks": benchmarks}


def money(x):
    return ("-$" if x < 0 else "+$" if x > 0 else "$") + "{:,.2f}".format(abs(x))


def pctf(x):
    return "n/a" if x is None else "%.1f %%" % (100 * x)


def report(res):
    e = res["empire"]
    out = ["TRADE EMPIRE  (paper money only)", res["disclaimer"], "",
           "Data: %s." % res["source"]]
    out += ["  " + p for p in res["periods"]]
    out += ["", "Treasury: $%s from $%s across %d paper accounts (%s). %d trades: %d wins, %d losses, "
            "win rate %s (95 %% range %s to %s)." % (
                "{:,.2f}".format(e["treasury"]), "{:,.0f}".format(e["start"]), e["accounts"], money(e["pnl"]),
                e["trades"], e["wins"], e["losses"], pctf(e["win_rate"]), pctf(e["win_rate_95"][0]),
                pctf(e["win_rate_95"][1])),
            "%d skills made money, %d did not." % (e["profitable_skills"], e["losing_skills"]), ""]
    hdr = "%-3s %-9s %-21s %6s %5s %5s %8s %13s %11s %6s %9s %7s" % (
        "#", "title", "skill", "trades", "wins", "loss", "win", "95 % range", "P&L", "PF", "drawdown", "green20")
    out += [hdr, "-" * len(hdr)]
    for s in res["skills"]:
        st = s["stats"]
        out.append("%-3d %-9s %-21s %6d %5d %5d %8s %13s %11s %6s %9s %7s" % (
            s["rank"], s["title"], s["name"][:21], st["trades"], st["wins"], st["losses"], pctf(st["win_rate"]),
            "%.0f-%.0f %%" % (100 * st["win_rate_95"][0], 100 * st["win_rate_95"][1]), money(st["pnl"]),
            "-" if st["profit_factor"] is None else "%.2f" % st["profit_factor"],
            "$%.0f" % st["max_drawdown"], pctf(st["odds_green_next_20"])))
    out += [""]
    for s in res["skills"]:
        out.append("%s, %s: %s." % (s["name"], s["title"], s["verdict"]))
    if res["benchmarks"]:
        out += ["", "For comparison, doing nothing clever:"]
        out += ["  %s: %s (%s)" % (b["name"], money(b["pnl"]), b["detail"]) for b in res["benchmarks"]]
    out += ["", "green20 = share of 10,000 random draws of 20 of the skill's own past trades that ended above "
            "zero (seed %d). It describes the past, not the future." % res["seed"]]
    return "\n".join(out)


def public(res):
    """The JSON to save: no lambdas, trades kept."""
    return json.loads(json.dumps(res, default=lambda o: None))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trade Empire: every skill, paper money, real past data.")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("--demo", action="store_true", help="the real recorded data shipped in tests/fixtures")
    r.add_argument("--symbols", help="live: comma-separated tickers (60 days of 5-min bars + 1 year daily)")
    r.add_argument("--offline", action="append", default=[], help="a saved Yahoo 5-min chart (.json/.gz)")
    r.add_argument("--daily", help="a saved Yahoo spark or chart JSON of daily closes")
    r.add_argument("--write", action="store_true", help="save trader/empire.json and trader/empire.html")
    r.add_argument("--out", default="trader", help="folder for --write (default trader)")
    r.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd != "run":
        ap.print_help()
        return 2
    try:
        intraday, daily, src = [], {}, []
        offline = list(a.offline)
        daily_path = a.daily
        if a.demo:
            offline.append(DEMO_INTRADAY)
            daily_path = daily_path or DEMO_DAILY
            src.append("real Yahoo Finance bars recorded with the pack (tests/fixtures), replayed offline")
        for path in offline:
            text = read_text(path)
            sym = (tm.chart_result(text, "?").get("meta") or {}).get("symbol") or os.path.basename(path)
            sessions, prev, _ = load_intraday(text, sym)
            intraday.append((sym, (sessions, prev)))
        if daily_path:
            daily = parse_daily(read_text(daily_path))
        if a.symbols:
            src.append("live Yahoo Finance bars (free, unofficial, can lag)")
            for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
                sessions, prev, _ = load_intraday(tm.fetch_chart(sym), sym)
                intraday.append((sym, (sessions, prev)))
                pts = parse_daily(fetch_daily(sym))
                daily.update(pts)
                tm._sleep(tm.PAUSE)
        if not intraday and not daily:
            raise EmpireError("no data: pass --demo, --symbols TSLA,AAPL or --offline FILE")
        res = run(intraday, daily, "; ".join(src) or "saved files")
    except (EmpireError, tm.TMError, ValueError) as e:
        print("empire: %s" % e, file=sys.stderr)
        return 1
    clean = public(res)
    if a.write:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "empire.json"), "w", encoding="utf-8") as fh:
            json.dump(clean, fh, indent=1)
        import empire_html
        with open(os.path.join(a.out, "empire.html"), "w", encoding="utf-8") as fh:
            fh.write(empire_html.render(clean))
    print(json.dumps(clean, indent=1) if a.json else report(res))
    if a.write and not a.json:
        print("\nSaved %s and %s" % (os.path.join(a.out, "empire.json"), os.path.join(a.out, "empire.html")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
