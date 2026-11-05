"""The Empire's Court for empire.py: every one of the pack's 11 tools, run for real. Standard library only.

Two jobs:

  reel_day(work)       Monday 2026-10-19, the reel's trade, through all eleven tools in order, each one
                       run as its own program on the real data recorded in tests/fixtures, with the clock
                       pinned: scanner -> news -> entry -> exit -> timemachine -> budget -> risk -> broker
                       -> alerts, plus analyst and pelosi as the court's intelligence. Each tool's exit
                       code and its key line are kept, so a tool that breaks shows as broken.

  full_court(...)      the same chain on every past TSLA session that has 20 full sessions before it:
                       entry (watch, bar by bar) -> exit (stop at the range midpoint, 1R) -> timemachine
                       (2,000 replays, seed 19) -> budget -> risk -> broker (show) -> alerts (stop, target,
                       flat by 3:55). The empire takes the trade on paper only when trader-risk passed it,
                       trader-broker shows it READY, and the time machine's verdict does not lean toward the
                       stop. Shares come from trader-budget. The paper fill is the empire's own: it never
                       calls trader-broker approve, because that needs a person's yes for a real order.

Nothing here can place an order. trader-broker only ever renders a ticket; the empire fills it on paper.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(ROOT, "tests", "fixtures")

ELEVEN = [
    ("trader-scanner", "Chart Scanner", "scan.py"),
    ("trader-news", "News Monitor", "news.py"),
    ("trader-entry", "Entry Timer", "entry.py"),
    ("trader-exit", "Exit Planner", "exit.py"),
    ("trader-timemachine", "Time Machine", "timemachine.py"),
    ("trader-budget", "Budget Manager", "size.py"),
    ("trader-risk", "Risk Manager", "check.py"),
    ("trader-broker", "Order Executor", "ticket.py"),
    ("trader-alerts", "Price Alerts", "alerts.py"),
    ("trader-analyst", "Earnings Analyst", "facts.py"),
    ("trader-pelosi", "Pelosi Tracker", "ptr.py"),
]
SCRIPT = dict((s, os.path.join(ROOT, s, f)) for s, _, f in ELEVEN)
JOB = dict((s, j) for s, j, _ in ELEVEN)
TSLA_60D = os.path.join(FIX, "trader-timemachine", "TSLA-60d5m.json.gz")


def tool(skill, argv, cwd, env=None):
    """Run one of the eleven as its own program. Returns (exit code, stdout + stderr)."""
    e = dict(os.environ)
    e.pop("SEC_USER_AGENT", None)
    e.update(env or {})
    p = subprocess.run([sys.executable, "-B", SCRIPT[skill]] + list(argv), cwd=cwd, env=e,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=300)
    return p.returncode, p.stdout


def _line(text, *needles):
    for ln in text.splitlines():
        if any(n in ln for n in needles):
            return ln.strip()
    return ""


def _fresh(work):
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(os.path.join(work, "trader"))
    shutil.copy(os.path.join(ROOT, "trader-budget", "config.example.json"), os.path.join(work, "trader", "config.json"))


def _read(work, name):
    path = os.path.join(work, "trader", name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- the reel's day, all eleven

def reel_day(work=None):
    own = work is None
    work = work or tempfile.mkdtemp(prefix="empire-court-")
    _fresh(work)
    now = "2026-10-19 10:16"
    steps = []

    def step(skill, argv, finding, ok_codes=(0,)):
        code, out = tool(skill, argv, work)
        steps.append({"skill": skill, "job": JOB[skill], "command": "%s %s" % (os.path.basename(SCRIPT[skill]),
                                                                                " ".join(argv)),
                      "exit": code, "ok": code in ok_codes, "finding": finding(out) if code in ok_codes else
                      (out.strip().splitlines() or ["no output"])[-1], "output": out})
        return code, out

    step("trader-scanner", ["orb", "--offline", os.path.join(FIX, "trader-scanner", "wall5m-2026-10-19.json.gz"),
                            "--now", "2026-10-19 10:15", "--min-price", "0"],
         lambda o: "%s TSLA: %s" % (_line(o, "Wrote trader/watchlist.json"), " ".join(_line(o, " TSLA ").split())))
    step("trader-news", ["--tickers", "TSLA", "--hours", "6", "--no-sec", "--no-moves",
                         "--now", "2026-10-19T10:15:00-04:00", "--offline", os.path.join(FIX, "trader-news")],
         lambda o: "%d TSLA headlines this morning; the top one: %s" % (
             len([l for l in o.splitlines() if l.startswith("  2026-10-19")]),
             re.sub(r"\s+", " ", _line(o, "Merger Mania") or _line(o, "2026-10-19"))))
    step("trader-entry", ["check", "TSLA", "--offline", os.path.join(FIX, "trader-entry", "TSLA-2026-10-19-5m.json"),
                          "--now", "2026-10-19 10:15", "--write"], lambda o: _line(o, "TRIGGERED", "WAITING"))
    step("trader-exit", ["plan", "--stop", "or-mid", "--target", "1R", "--now", now, "--write"],
         lambda o: "stop %s, target %s" % ((_read(work, "plan.json") or {}).get("stop"),
                                           (_read(work, "plan.json") or {}).get("target")))
    step("trader-timemachine", ["run", "--offline", TSLA_60D, "--now", now, "--until", "15:55", "--write"],
         lambda o: _line(o, "Close to", "Leans", "Strongly"))
    step("trader-budget", ["--now", now, "--write"],
         lambda o: ((_read(work, "orders.json") or {}).get("orders") or [{}])[0].get("why", ""))
    step("trader-risk", ["--now", now], lambda o: _line(o, "passed,"))
    step("trader-broker", ["show", "--now", now], lambda o: _line(o, "READY", "NOT READY") + " (shown, never sent)")
    step("trader-alerts", ["add", "--from-plan"], lambda o: "%d alerts set: stop, target, flat by 3:55" % o.count("Added "))
    step("trader-analyst", ["AAPL", "--offline", os.path.join(FIX, "trader-analyst"), "--quarters", "4"],
         lambda o: _line(o, "Last 4 quarters"))
    step("trader-pelosi", ["new", "--member", "pelosi", "--offline", os.path.join(FIX, "trader-pelosi", "2026FD.zip"),
                           "--year", "2026", "--today", "2026-10-13",
                           "--portfolio", os.path.join(work, "trader", "none.json")],
         lambda o: _line(o, "NEW Periodic", "Nothing new") or "no new filings")
    orders = (_read(work, "orders.json") or {}).get("orders") or []
    plan = _read(work, "plan.json")
    if own:
        shutil.rmtree(work, ignore_errors=True)
    for s in steps:
        s.pop("output", None)
    return {"date": "2026-10-19", "steps": steps, "working": sum(1 for s in steps if s["ok"]),
            "plan": plan, "order": orders[0] if orders else None}


# ---------------------------------------------------------------- every past session, the chain

def full_court(sessions, walk, slip, min_before=20, replays=2000):
    """sessions: [(date, 78 bars)] of TSLA from TSLA-60d5m. walk: empire.walk. Returns (trades, log)."""
    trades, log = [], []
    work = tempfile.mkdtemp(prefix="empire-full-court-")
    try:
        for n, (d, D) in enumerate(sessions):
            if n < min_before:
                continue
            _fresh(work)
            row = {"date": d}
            code, out = tool("trader-entry", ["watch", "TSLA", "--offline", TSLA_60D, "--now", d + " 09:30",
                                              "--until", "15:30"], work)
            ent = _read(work, "entry.json")
            if not ent or ent.get("status") != "triggered":
                row["result"] = "entry: no breakout by 3:30"
                log.append(row)
                continue
            k = int(ent["bar_index"])
            hh = 9 * 60 + 30 + 5 * (k + 1)
            now = "%s %02d:%02d" % ((d,) + divmod(hh + 1, 60))
            code, out = tool("trader-exit", ["plan", "--stop", "or-mid", "--target", "1R", "--now", now, "--write"], work)
            plan = _read(work, "plan.json")
            if code or not plan:
                row["result"] = "exit refused: " + (out.strip().splitlines() or [""])[-1]
                log.append(row)
                continue
            code, out = tool("trader-timemachine", ["run", "--offline", TSLA_60D, "--now", now, "--until", "15:55",
                                                    "--replays", str(replays), "--write"], work)
            tmj = _read(work, "timemachine.json") or {}
            verdict = tmj.get("verdict") or "no verdict"
            row["timemachine"] = verdict
            code, out = tool("trader-budget", ["--now", now, "--write"], work)
            orders = (_read(work, "orders.json") or {}).get("orders") or []
            if code or not orders:
                row["result"] = "budget refused: " + (out.strip().splitlines() or [""])[-1]
                log.append(row)
                continue
            code, out = tool("trader-risk", ["--now", now], work)
            risk = ((_read(os.path.join(work), "state/risk.json") or {}).get("results") or [{}])[0]
            row["risk"] = risk.get("verdict")
            code, out = tool("trader-broker", ["show", "--now", now, "--json"], work)
            try:
                ready = bool(json.loads(out)[0].get("ready"))
            except (ValueError, IndexError, KeyError):
                ready = False
            row["broker"] = "READY" if ready else "NOT READY"
            tool("trader-alerts", ["add", "--from-plan"], work)
            alerts = (_read(work, "alerts.json") or {})
            row["alerts"] = len(alerts.get("rules", alerts) if isinstance(alerts, dict) else alerts)
            if risk.get("verdict") != "PASS" or not ready:
                row["result"] = "skipped: risk %s, broker %s" % (risk.get("verdict"), row["broker"])
                log.append(row)
                continue
            if "toward the stop" in verdict:
                row["result"] = "skipped: the time machine leans toward the stop"
                log.append(row)
                continue
            o = orders[0]
            shares = int(o["qty"])
            p = {"k": k, "entry": plan["entry"], "stop": plan["stop"], "target": plan["target"], "exit_rule": None}
            px, outcome, j = walk(D, p)
            pnl = round(shares * ((px - slip) - (p["entry"] + slip)), 2)
            row["result"] = "paper trade: %s, %+.2f" % (outcome, pnl)
            log.append(row)
            hj = 9 * 60 + 30 + 5 * (j + 1)
            trades.append({"date": d, "symbol": "TSLA", "in": plan["entry_time"],
                           "out": "%d:%02d %s" % ((hj // 60) % 12 or 12, hj % 60, "AM" if hj < 720 else "PM"),
                           "shares": shares, "entry": p["entry"], "stop": p["stop"], "target": p["target"],
                           "exit": round(px, 2), "outcome": outcome, "pnl": pnl,
                           "R": round(pnl / (shares * (p["entry"] - p["stop"])), 2)})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return trades, log
