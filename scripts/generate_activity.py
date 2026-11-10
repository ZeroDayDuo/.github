#!/usr/bin/env python3
"""Build the two live profile SVGs (activity matrix + patrol snake).

Reads every repo of the org with ORG_TOKEN, counts human commits per UTC day,
and writes animated dark-mode SVGs. Fails loudly when the token is missing or
cannot list the org's repos, so a broken token never ships an empty grid.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ORG = "ZeroDayDuo"
API = "https://api.github.com"

COLS, ROWS = 53, 7
DOT, GAP = 11, 4
STEP = DOT + GAP
GRID_X = 38
WIDTH = GRID_X + COLS * STEP + 17  # 850

LEVELS = ["#111a2b", "#0b3b46", "#0a6f7a", "#12b5c4", "#5ef4ff"]
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


# ---------------------------------------------------------------- data ----

def api_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Activity-Matrix-Updater",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def paged(url, token):
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        batch = api_get(f"{url}{sep}per_page=100&page={page}", token)
        yield from batch
        if len(batch) < 100:
            return
        page += 1


def is_bot(commit):
    login = (commit.get("author") or {}).get("login") or ""
    name = ((commit.get("commit") or {}).get("author") or {}).get("name") or ""
    return login.endswith("[bot]") or name.endswith("[bot]")


def fetch_activity_counts(token):
    try:
        repos = list(paged(f"{API}/orgs/{ORG}/repos?type=all", token))
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: cannot list {ORG} repos (HTTP {e.code}). "
                 "ORG_TOKEN is expired or lacks access.")
    private = sum(1 for r in repos if r.get("private"))
    print(f"Repos visible: {len(repos)} ({private} private)")
    if private == 0:
        sys.exit("ERROR: token sees no private repos. Give ORG_TOKEN read "
                 "access to all org repositories (Contents + Metadata).")

    since = (datetime.now(timezone.utc) - timedelta(days=375)).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts, failed = {}, 0
    for r in repos:
        url = f"{API}/repos/{ORG}/{r['name']}/commits?since={since}"
        try:
            for c in paged(url, token):
                if is_bot(c):
                    continue
                day = c["commit"]["author"]["date"][:10]
                counts[day] = counts.get(day, 0) + 1
        except urllib.error.HTTPError as e:
            if e.code != 409:  # 409 = empty repository
                failed += 1
                print(f"WARN: commits fetch failed for one repo (HTTP {e.code})")
    if failed > len(repos) // 2:
        sys.exit("ERROR: commit fetch failed for most repos.")
    return counts


# ---------------------------------------------------------------- grid ----

def level(count):
    if count == 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 9:
        return 3
    return 4


def build_grid(counts, today):
    """Return (start_date, cells) where cells[c][r] = (date, count) or None for future days."""
    weekday = (today.weekday() + 1) % 7  # Sunday = 0
    start = today - timedelta(days=weekday) - timedelta(weeks=COLS - 1)
    cells, d = [], start
    for _ in range(COLS):
        col = []
        for _ in range(ROWS):
            col.append((d, counts.get(d.isoformat(), 0)) if d <= today else None)
            d += timedelta(days=1)
        cells.append(col)
    return start, cells


def stats(cells, today):
    days = [x for col in cells for x in col if x]
    total = sum(n for _, n in days)
    active = sum(1 for _, n in days if n)
    peak = max((n for _, n in days), default=0)
    best = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        best = max(best, run)
    cur = 0
    for d, n in reversed(days):
        if n:
            cur += 1
        elif d == today:
            continue  # today may still be empty, streak is not broken yet
        else:
            break
    return {"total": total, "active": active, "peak": peak, "best": best, "streak": cur}


# ----------------------------------------------------------------- svg ----

def shell(height, title, badge, extra_css, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" fill="none">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b111d"/><stop offset="1" stop-color="#06090f"/></linearGradient>
<linearGradient id="edge" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#5ef4ff" stop-opacity="0"/><stop offset=".3" stop-color="#5ef4ff"/><stop offset=".7" stop-color="#8b5cf6"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/></linearGradient>
<linearGradient id="scan" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#5ef4ff" stop-opacity="0"/><stop offset=".5" stop-color="#5ef4ff" stop-opacity=".09"/><stop offset="1" stop-color="#5ef4ff" stop-opacity="0"/></linearGradient>
<clipPath id="panel"><rect width="{WIDTH}" height="{height}" rx="12"/></clipPath>
</defs>
<style>
text {{ font-family: {FONT}; }}
.title {{ font-size: 13px; font-weight: 700; fill: #e2e8f0; letter-spacing: 1.5px; }}
.badge {{ font-size: 10px; font-weight: 600; fill: #5ef4ff; letter-spacing: 1.5px; }}
.lbl {{ font-size: 10px; fill: #5b6b82; }}
.stat {{ font-size: 10.5px; fill: #8fa3bd; letter-spacing: .5px; }}
.num {{ fill: #5ef4ff; font-weight: 700; }}
.live {{ fill: #5ef4ff; animation: blink 1.6s ease-in-out infinite; }}
.scan {{ animation: sweep 9s linear infinite; }}
@keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .25; }} }}
@keyframes sweep {{ from {{ transform: translateX(-140px); }} to {{ transform: translateX({WIDTH}px); }} }}
{extra_css}
</style>
<rect x=".6" y=".6" width="{WIDTH - 1.2}" height="{height - 1.2}" rx="12" fill="url(#bg)" stroke="#1b2a41" stroke-width="1.2"/>
<g clip-path="url(#panel)">
<rect width="{WIDTH}" height="1.6" fill="url(#edge)"/>
<rect class="scan" width="140" height="{height}" fill="url(#scan)"/>
</g>
<text x="20" y="28" class="title">{title}</text>
<circle class="live" cx="{WIDTH - 24}" cy="24" r="3.2"/>
<text x="{WIDTH - 34}" y="28" text-anchor="end" class="badge">{badge}</text>
{body}
</svg>
"""


def stat_line(x, y, parts):
    spans = "".join(f'<tspan class="num">{v}</tspan> {k}' + ("   " if i < len(parts) - 1 else "")
                    for i, (v, k) in enumerate(parts))
    return f'<text x="{x}" y="{y}" class="stat" xml:space="preserve">{spans}</text>'


def matrix_svg(start, cells, st, today):
    gy = 62
    height = gy + ROWS * STEP + 39
    css = """.col { animation: rise .6s ease-out both; }
.hot { animation: glow 3.4s ease-in-out infinite; }
.ring { stroke: #5ef4ff; stroke-width: 1.2; animation: ping 2s ease-out infinite; transform-box: fill-box; transform-origin: center; }
@keyframes rise { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
@keyframes glow { 0%, 100% { opacity: 1; } 50% { opacity: .62; } }
@keyframes ping { 0% { opacity: .9; transform: scale(1); } 100% { opacity: 0; transform: scale(2.1); } }"""
    b = []
    for r, txt in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(f'<text x="12" y="{gy + r * STEP + 9}" class="lbl">{txt}</text>')

    last_x = -99
    for c, col in enumerate(cells):
        first = start + timedelta(days=c * 7)
        for i in range(7):
            d = first + timedelta(days=i)
            if d.day == 1 or (c == 0 and i == 0):
                x = GRID_X + c * STEP
                if x - last_x >= 34 and d <= today:
                    b.append(f'<text x="{x}" y="{gy - 10}" class="lbl">{d.strftime("%b")}</text>')
                    last_x = x
                break

    ring = ""
    for c, col in enumerate(cells):
        b.append(f'<g class="col" style="animation-delay:{c * 16}ms">')
        for r, cell in enumerate(col):
            if not cell:
                continue
            d, n = cell
            lv = level(n)
            x, y = GRID_X + c * STEP, gy + r * STEP
            hot = f' class="hot" style="animation-delay:-{(c * 7 + r) % 9 * 0.4:.1f}s"' if lv == 4 else ""
            b.append(f'<rect x="{x}" y="{y}" width="{DOT}" height="{DOT}" rx="2.5" fill="{LEVELS[lv]}"{hot}>'
                     f'<title>{d.isoformat()}: {n} commits</title></rect>')
            if d == today:
                ring = f'<rect class="ring" x="{x}" y="{y}" width="{DOT}" height="{DOT}" rx="2.5"/>'
        b.append('</g>')
    b.append(ring)

    fy = height - 15
    b.append(stat_line(20, fy, [(st["total"], "commits"), (st["active"], "active days"),
                                (f'{st["streak"]}d', "streak")]))
    lx = WIDTH - 122
    b.append(f'<text x="{lx - 8}" y="{fy}" text-anchor="end" class="lbl">Less</text>')
    for i, colr in enumerate(LEVELS):
        b.append(f'<rect x="{lx + i * (DOT + 3)}" y="{fy - 9}" width="{DOT}" height="{DOT}" rx="2.5" fill="{colr}"/>')
    b.append(f'<text x="{lx + 5 * (DOT + 3) + 4}" y="{fy}" class="lbl">More</text>')
    return shell(height, "// CADENCE MATRIX", "LIVE TIMELINE", css, "\n".join(b))


def snake_svg(cells, st, today):
    gy = 46
    height = gy + ROWS * STEP + 37
    n_steps = COLS * ROWS - 1
    loop = 46.0                     # seconds for one full patrol
    dt = loop / n_steps
    segs = 5

    def pos(idx):
        c, k = divmod(idx, ROWS)
        r = k if c % 2 == 0 else ROWS - 1 - k
        return GRID_X + c * STEP, gy + r * STEP

    # Keyframes only at the corners: top and bottom of every column.
    corners = sorted({c * ROWS for c in range(COLS)} | {c * ROWS + ROWS - 1 for c in range(COLS)})
    kf = []
    for idx in corners:
        x, y = pos(idx)
        op = ""
        if idx == 0 or idx == n_steps:
            op = " opacity: 0;"
        elif idx == corners[1] or idx == corners[-2]:
            op = " opacity: 1;"
        kf.append(f"{idx / n_steps * 100:.3f}% {{ transform: translate({x}px, {y}px);{op} }}")

    css = f""".seg {{ animation: patrol {loop}s linear infinite; }}
.head {{ fill: #5ef4ff; filter: drop-shadow(0 0 4px #5ef4ff); }}
.food {{ animation-duration: {loop}s; animation-timing-function: linear; animation-iteration-count: infinite; }}
{{FOOD}}
@keyframes patrol {{
{chr(10).join(kf)}
}}"""

    b, food = [], []
    for c, col in enumerate(cells):
        for r, cell in enumerate(col):
            if cell:
                b.append(f'<rect x="{GRID_X + c * STEP}" y="{gy + r * STEP}" width="{DOT}" height="{DOT}" rx="2.5" fill="{LEVELS[0]}"/>')
    for c, col in enumerate(cells):
        for r, cell in enumerate(col):
            if not cell or not cell[1]:
                continue
            idx = c * ROWS + (r if c % 2 == 0 else ROWS - 1 - r)
            # Lit until the head lands on it, dark until the loop ends, then regrows.
            p = min(max((idx - segs) / n_steps * 100, 0.0), 96.0)
            food.append(f"@keyframes e{idx} {{ 0%, {p:.2f}% {{ opacity: 1; }} {p + 0.3:.2f}%, 97.5% {{ opacity: 0; }} 100% {{ opacity: 1; }} }}")
            b.append(f'<rect class="food" style="animation-name:e{idx}" x="{GRID_X + c * STEP}" y="{gy + r * STEP}" '
                     f'width="{DOT}" height="{DOT}" rx="2.5" fill="{LEVELS[level(cell[1])]}"/>')

    css = css.replace("{FOOD}", "\n".join(food))

    body_fill = ["#38bdf8", "#2f9fd6", "#2782b3", "#1f6690"]
    for k in range(segs - 1, -1, -1):           # tail first so the head draws on top
        delay = -(segs - k) * dt
        if k == 0:
            b.append(f'<rect class="seg head" style="animation-delay:{delay:.3f}s" width="{DOT}" height="{DOT}" rx="3"/>')
        else:
            b.append(f'<rect class="seg" style="animation-delay:{delay:.3f}s" width="{DOT}" height="{DOT}" rx="2.5" fill="{body_fill[k - 1]}"/>')

    fy = height - 14
    b.append(stat_line(20, fy, [(f'{st["best"]}d', "best streak"), (st["peak"], "peak commits / day")]))
    b.append(f'<text x="{WIDTH - 20}" y="{fy}" text-anchor="end" class="lbl">synced {today.isoformat()} UTC</text>')
    return shell(height, "// AUTONOMOUS PATROL", "CONTINUOUS RUN", css, "\n".join(b))


def main():
    token = os.environ.get("ORG_TOKEN")
    if not token:
        sys.exit("ERROR: ORG_TOKEN is not set.")
    counts = fetch_activity_counts(token)

    today = datetime.now(timezone.utc).date()
    start, cells = build_grid(counts, today)
    st = stats(cells, today)
    files = {
        "activity-matrix.svg": matrix_svg(start, cells, st, today),
        "snake.svg": snake_svg(cells, st, today),
    }

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for out_dir in (os.path.join(root, "assets"), os.path.join(root, "profile", "assets")):
        os.makedirs(out_dir, exist_ok=True)
        for name, svg in files.items():
            with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(svg)
    print(f"Activity SVGs written: {st}")


if __name__ == "__main__":
    main()
