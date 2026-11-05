"""The Trade Empire dashboard: one self-contained HTML page from empire.json. Standard library only.

    import empire_html
    html = empire_html.render(result)                 # a full page to open in any browser
    html = empire_html.render(result, fragment=True)  # the same page without <!doctype>/<html>/<body>
"""

import html as _h

FONTS = ("https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600"
         "&family=IBM+Plex+Mono:wght@400;500&display=swap")

CSS = """
/* Layout: an imperial ledger. Treasury up top, the throne-room ranking, then each skill's books. */
:root {
  --bg: #f4f5f9; --panel: #ffffff; --ink: #1b2340; --muted: #5d6585; --line: #dfe2ec;
  --brass: #9a6d12; --brass-soft: #f3e7c9; --win: #1d7a4b; --win-soft: #dcf1e6; --loss: #b0343a;
  --loss-soft: #f8e0e1; --warn-bg: #fff4d6; --warn-ink: #6b4a00;
  --display: "Cinzel", "Trajan Pro", Georgia, serif;
  --body: "IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0e1222; --panel: #161b2f; --ink: #e5e8f2; --muted: #9aa1bd; --line: #2a3150;
  --brass: #dcae4a; --brass-soft: #3a3020; --win: #4cc38a; --win-soft: #15352a; --loss: #f07a7f;
  --loss-soft: #3d1d24; --warn-bg: #3a3014; --warn-ink: #f3d68a; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0e1222; --panel: #161b2f; --ink: #e5e8f2; --muted: #9aa1bd; --line: #2a3150;
  --brass: #dcae4a; --brass-soft: #3a3020; --win: #4cc38a; --win-soft: #15352a; --loss: #f07a7f;
  --loss-soft: #3d1d24; --warn-bg: #3a3014; --warn-ink: #f3d68a; color-scheme: dark; }
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font-family: var(--body); font-size: 15px; line-height: 1.5;
  margin: 0; }
.wrap { max-width: 1120px; margin: 0 auto; padding-block: 24px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 28px; }
h1, h2 { font-family: var(--display); letter-spacing: .04em; text-wrap: balance; margin: 0; }
h1 { font-size: clamp(30px, 6vw, 46px); line-height: 1.1; }
h2 { font-size: 21px; }
.num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.muted { color: var(--muted); }
.warn { background: var(--warn-bg); color: var(--warn-ink); border-radius: 8px; padding: 12px 16px; font-weight: 500; }
.hero { display: grid; gap: 14px; }
.eyebrow { text-transform: uppercase; letter-spacing: .14em; font-size: 12px; color: var(--brass); font-weight: 600; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; min-width: 0; }
.tile .k { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.tile .v { font-family: var(--mono); font-size: 24px; font-weight: 500; font-variant-numeric: tabular-nums; }
.tile .s { font-size: 13px; color: var(--muted); }
.pos { color: var(--win); } .neg { color: var(--loss); }
.section { display: grid; gap: 12px; min-width: 0; }
.scroll { overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: middle; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); font-weight: 600; }
td.r, th.r { text-align: right; }
tr:last-child td { border-bottom: 0; }
.chip { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600;
  letter-spacing: .04em; border: 1px solid var(--line); }
.chip.crown { background: var(--brass-soft); color: var(--brass); border-color: transparent; }
.chip.bad { background: var(--loss-soft); color: var(--loss); border-color: transparent; }
.chip.squire { color: var(--muted); }
.skill { font-weight: 600; }
.rule { font-size: 13px; color: var(--muted); white-space: normal; min-width: 220px; max-width: 360px; }
svg text { fill: var(--muted); font-family: var(--mono); font-size: 11px; }
.bars { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px; overflow-x: auto; }
details { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
summary { cursor: pointer; padding: 12px 16px; font-weight: 600; display: flex; gap: 10px; flex-wrap: wrap; align-items: baseline; }
summary:focus-visible { outline: 2px solid var(--brass); outline-offset: 2px; }
details .scroll { border: 0; border-top: 1px solid var(--line); border-radius: 0 0 10px 10px; max-height: 420px; overflow: auto; }
.fine { font-size: 13px; color: var(--muted); display: grid; gap: 6px; max-width: 75ch; }
.fine p { margin: 0; }
"""


def e(x):
    return _h.escape("" if x is None else str(x), quote=True)


def money(x, sign=True):
    s = "{:,.2f}".format(abs(x))
    if x < 0:
        return "-$" + s
    return ("+$" if sign and x > 0 else "$") + s


def pct(x):
    return "n/a" if x is None else "%.1f%%" % (100 * x)


def cls(x):
    return "pos" if x > 0 else "neg" if x < 0 else ""


def spark(curve, w=140, h=34):
    """An equity curve: the account balance after each trade, with the $5,000 start as a faint line."""
    if len(curve) < 2:
        return '<span class="muted">no trades</span>'
    lo, hi = min(curve), max(curve)
    if hi - lo < 1e-9:
        hi = lo + 1
    pad = 3

    def y(v):
        return pad + (h - 2 * pad) * (hi - v) / (hi - lo)

    step = (w - 2 * pad) / float(len(curve) - 1)
    pts = " ".join("%.1f,%.1f" % (pad + i * step, y(v)) for i, v in enumerate(curve))
    color = "var(--win)" if curve[-1] > curve[0] else "var(--loss)"
    base = y(curve[0])
    return ('<svg width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-label="balance from %s to %s">'
            '<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="var(--line)" stroke-dasharray="3 3"/>'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.6"/>'
            '<circle cx="%.1f" cy="%.1f" r="2.6" fill="%s"/></svg>') % (
        w, h, w, h, money(curve[0], False), money(curve[-1], False), pad, w - pad, base, base, pts, color,
        pad + (len(curve) - 1) * step, y(curve[-1]), color)


def winbar(st, w=120):
    """The win rate as a dot, its 95 % range as a whisker, and 50 % as a tick."""
    if not st["trades"]:
        return ""
    lo, hi = st["win_rate_95"]
    x = lambda v: 4 + (w - 8) * v  # noqa: E731
    return ('<svg width="%d" height="18" viewBox="0 0 %d 18" role="img" aria-label="win rate %s, range %s to %s">'
            '<line x1="4" x2="%d" y1="9" y2="9" stroke="var(--line)" stroke-width="4" stroke-linecap="round"/>'
            '<line x1="%.1f" x2="%.1f" y1="3" y2="15" stroke="var(--muted)" stroke-width="1"/>'
            '<line x1="%.1f" x2="%.1f" y1="9" y2="9" stroke="var(--brass)" stroke-width="4" stroke-linecap="round"/>'
            '<circle cx="%.1f" cy="9" r="4" fill="var(--ink)"/></svg>') % (
        w, w, pct(st["win_rate"]), pct(lo), pct(hi), w - 4, x(.5), x(.5), x(lo), x(hi), x(st["win_rate"]))


def pnl_bars(skills):
    """Horizontal bars of each skill's P&L around a zero line, drawn to one scale."""
    w, row, left, right = 760, 30, 190, 90
    h = row * len(skills) + 30
    m = max(1.0, max(abs(s["stats"]["pnl"]) for s in skills))
    span = (w - left - right) / 2.0
    zero = left + span
    out = ['<svg width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-label="profit and loss by skill">'
           % (w, h, w, h)]
    for tick in (-m, -m / 2, 0, m / 2, m):
        tx = zero + span * tick / m
        out.append('<line x1="%.1f" x2="%.1f" y1="4" y2="%d" stroke="var(--line)"/>' % (tx, tx, h - 22))
        out.append('<text x="%.1f" y="%d" text-anchor="middle">%s</text>' % (tx, h - 6, e(money(round(tick)))))
    for i, s in enumerate(skills):
        v = s["stats"]["pnl"]
        y = 6 + i * row
        bw = span * abs(v) / m
        x0 = zero if v >= 0 else zero - bw
        color = "var(--win)" if v > 0 else "var(--loss)"
        out.append('<text x="%d" y="%d" text-anchor="end" style="fill:var(--ink);font-family:var(--body);'
                   'font-size:13px">%s</text>' % (left - 10, y + 15, e(s["name"])))
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="18" rx="3" fill="%s"/>' % (x0, y + 2, max(bw, 1.5), color))
        out.append('<text x="%d" y="%d" text-anchor="end" style="fill:%s">%s</text>' % (
            w - 6, y + 15, color, e(money(v))))
    out.append('<line x1="%.1f" x2="%.1f" y1="2" y2="%d" stroke="var(--ink)" stroke-width="1.2"/>' % (zero, zero, h - 22))
    out.append("</svg>")
    return "".join(out)


def chip(title):
    kind = "squire" if title == "Squire" else "bad" if title in ("Peasant", "Exiled") else "crown"
    return '<span class="chip %s">%s</span>' % (kind, e(title))


def ledger(s):
    day = s["province"].startswith("Day")
    head = ("date", "symbol", "in", "out", "shares", "entry", "stop", "target", "exit", "outcome", "P&L") if day else \
        ("bought", "symbol", "sold", "days", "shares", "entry", "exit", "outcome", "P&L")
    rows = []
    for t in s["trades"]:
        if day:
            cells = [t["date"], t["symbol"], t["in"], t["out"], t["shares"], "%.2f" % t["entry"], "%.2f" % t["stop"],
                     "-" if t["target"] is None else "%.2f" % t["target"], "%.2f" % t["exit"], t["outcome"]]
        else:
            cells = [t["date"], t["symbol"], t["out_date"], t["days"], t["shares"], "%.2f" % t["entry"],
                     "%.2f" % t["exit"], t["outcome"]]
        tds = "".join('<td%s>%s</td>' % (' class="r num"' if isinstance(c, (int, float)) or
                                         (isinstance(c, str) and c[:1].isdigit() and "." in c and ":" not in c)
                                         else "", e(c)) for c in cells)
        tds += '<td class="r num %s">%s</td>' % (cls(t["pnl"]), e(money(t["pnl"])))
        rows.append("<tr>%s</tr>" % tds)
    return ('<div class="scroll"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
        "".join("<th>%s</th>" % e(x) for x in head), "".join(rows) or '<tr><td>No trades.</td></tr>'))


def render(res, fragment=False):
    em = res["empire"]
    skills = res["skills"]
    parts = []
    parts.append('<title>Trade Empire</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
                 '<link rel="preconnect" href="https://fonts.googleapis.com">'
                 '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                 '<link rel="stylesheet" href="%s">\n<style>%s</style>' % (FONTS, CSS))
    parts.append('<main class="wrap">')
    parts.append('<div class="warn" role="note">%s</div>' % e(res["disclaimer"]))
    best = next((s for s in skills if s["title"] == "Emperor"), None)
    parts.append('<header class="hero"><div class="eyebrow">Paper trading demo</div><h1>Trade Empire</h1>'
                 '<p class="muted" style="margin:0;max-width:75ch">%d skills, each with its own $5,000 paper account, '
                 'traded on %s. %s</p></header>' % (
                     em["accounts"], e("; ".join(res["periods"])),
                     e("The Emperor is %s, the best earner with at least 10 trades." % best["name"]) if best else
                     "No skill with 10 or more trades made money, so the throne is empty."))
    tiles = [
        ("Treasury", money(em["treasury"], False), "started at %s" % money(em["start"], False)),
        ("Empire P&L", money(em["pnl"]), "%+.2f%% on the treasury" % (100 * em["pnl"] / em["start"])),
        ("Trades", "{:,}".format(em["trades"]), "%d wins, %d losses" % (em["wins"], em["losses"])),
        ("Win rate", pct(em["win_rate"]), "95%% range %s to %s" % (pct(em["win_rate_95"][0]), pct(em["win_rate_95"][1]))),
        ("Skills in profit", "%d of %d" % (em["profitable_skills"], em["accounts"]),
         "%d lost money" % em["losing_skills"]),
    ]
    parts.append('<section class="tiles">%s</section>' % "".join(
        '<div class="tile"><div class="k">%s</div><div class="v %s">%s</div><div class="s">%s</div></div>' % (
            e(k), cls(em["pnl"]) if k == "Empire P&L" else "", e(v), e(s)) for k, v, s in tiles))

    rows = []
    for s in skills:
        st = s["stats"]
        rows.append(
            '<tr><td class="num">%d</td><td>%s</td><td><div class="skill">%s</div><div class="rule">%s</div></td>'
            '<td class="r num">%d</td><td class="r num">%d / %d</td><td>%s <span class="num">%s</span>'
            '<div class="muted num" style="font-size:12px">%s to %s</div></td>'
            '<td class="r num %s">%s</td><td class="r num">%s</td><td class="r num">%s</td>'
            '<td class="r num">%s</td><td>%s</td><td class="rule">%s</td></tr>' % (
                s["rank"], chip(s["title"]), e(s["name"]), e(s["rule"]), st["trades"], st["wins"], st["losses"],
                winbar(st), e(pct(st["win_rate"])), e(pct(st["win_rate_95"][0])), e(pct(st["win_rate_95"][1])),
                cls(st["pnl"]), e(money(st["pnl"])),
                "-" if st["profit_factor"] is None else "%.2f" % st["profit_factor"],
                e(money(-st["max_drawdown"]) if st["max_drawdown"] else "$0.00"), e(pct(st["odds_green_next_20"])),
                spark(st["curve"]), e(s["verdict"])))
    parts.append(
        '<section class="section"><h2>The throne room</h2><p class="muted" style="margin:0">Ranked by P&amp;L. '
        'Emperor, King, Duke and on down for skills that made money; Peasant for one that lost; Exiled for the '
        'worst; Squire for a skill with under 10 trades, too few to judge.</p>'
        '<div class="scroll"><table><thead><tr><th>#</th><th>title</th><th>skill</th><th class="r">trades</th>'
        '<th class="r">wins / losses</th><th>win rate</th><th class="r">P&amp;L</th><th class="r">profit factor</th>'
        '<th class="r">max drawdown</th><th class="r">odds green, next 20</th><th>balance</th><th>verdict</th>'
        '</tr></thead><tbody>%s</tbody></table></div></section>' % "".join(rows))

    parts.append('<section class="section"><h2>Gold won and lost</h2><div class="bars">%s</div></section>'
                 % pnl_bars(skills))

    if res.get("benchmarks"):
        parts.append('<section class="section"><h2>Against doing nothing clever</h2><div class="scroll"><table>'
                     '<thead><tr><th>benchmark</th><th>how</th><th class="r">P&amp;L</th></tr></thead><tbody>%s'
                     '</tbody></table></div></section>' % "".join(
                         '<tr><td class="skill">%s</td><td class="muted">%s</td><td class="r num %s">%s</td></tr>' % (
                             e(b["name"]), e(b["detail"]), cls(b["pnl"]), e(money(b["pnl"]))) for b in res["benchmarks"]))

    books = []
    for s in skills:
        st = s["stats"]
        books.append('<details><summary>%s %s <span class="muted num" style="font-weight:400">%d trades, '
                     '<span class="%s">%s</span>, best %s, worst %s, longest losing run %d</span></summary>%s</details>'
                     % (chip(s["title"]), e(s["name"]), st["trades"], cls(st["pnl"]), e(money(st["pnl"])),
                        e(money(st["best"])), e(money(st["worst"])), st["losing_streak"], ledger(s)))
    parts.append('<section class="section"><h2>The books</h2>%s</section>' % "".join(books))

    r = res["rules"]
    parts.append(
        '<section class="fine"><h2>How it was measured</h2>'
        '<p>Data: %s. Every trade is on past bars, after the fact.</p>'
        '<p>Day trading: long only, one trade per skill per day, no entries before %s or after %s, flat by %s. '
        'Each trade risks at most %s and buys at most %s. A bar that touches the stop and the target counts as the '
        'stop. A bar that opens under the stop fills at its open. %s a share of slippage in and out.</p>'
        '<p>Swing trading: daily closes, %s a position, at most %d open at once, in and out at the close.</p>'
        '<p>Win rate range: the 95%% Wilson interval. Odds green, next 20: 10,000 random draws of 20 of the '
        'skill&#39;s own past trades (seed %d), the share that ended above zero. It describes the past, not the '
        'future.</p><p><strong>%s</strong> Most day traders lose money. A skill that looks good on 60 days can '
        'fail on the next 60.</p></section>' % (
            e(res["source"]), e(r["no_entries_before"]), e(r["no_entries_after"]), e(r["flat_by"]),
            e(money(r["max_loss_per_trade"], False)), e(money(r["max_order"], False)),
            e(money(r["slippage_per_share_each_side"], False)), e(money(r["swing_position"], False)),
            r["swing_max_open"], res["seed"], e(res["disclaimer"])))
    parts.append("</main>")
    body = "\n".join(parts)
    if fragment:
        return body + "\n"
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '%s\n</head>\n<body>\n%s\n</body>\n</html>\n') % (parts[0], "\n".join(parts[1:]))
