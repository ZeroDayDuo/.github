#!/usr/bin/env python3
import os
import json
import urllib.request
import shutil
from datetime import datetime, timedelta, timezone

def fetch_activity_counts(token, org_name="ZeroDayDuo"):
    commit_counts = {}
    if not token:
        return commit_counts

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Activity-Matrix-Updater"
    }

    try:
        req = urllib.request.Request(f"https://api.github.com/orgs/{org_name}/repos?type=all&per_page=100", headers=headers)
        with urllib.request.urlopen(req) as resp:
            repos = json.load(resp)
    except Exception as e:
        return commit_counts

    since = (datetime.now(timezone.utc) - timedelta(days=375)).isoformat()

    for r in repos:
        repo_name = r.get("name")
        if not repo_name:
            continue
        url = f"https://api.github.com/repos/{org_name}/{repo_name}/commits?per_page=100&since={since}"
        try:
            c_req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(c_req) as c_resp:
                commits = json.load(c_resp)
                for c in commits:
                    date_str = c.get("commit", {}).get("author", {}).get("date", "")[:10]
                    if date_str:
                        commit_counts[date_str] = commit_counts.get(date_str, 0) + 1
        except Exception:
            pass

    return commit_counts

def generate_svgs(commit_counts, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    
    # 53 columns (weeks), 7 rows (days)
    cols, rows = 53, 7
    dot_size, gap = 11, 4
    start_x, start_y = 35, 50
    width = start_x + (cols * (dot_size + gap)) + 20
    height = start_y + (rows * (dot_size + gap)) + 40

    colors = {
        0: "#121927",
        1: "#0a3a40",
        2: "#057a6e",
        3: "#00bfa5",
        4: "#00f2fe"
    }

    now = datetime.now(timezone.utc)
    # Calculate starting Sunday 52 weeks ago
    today_weekday = (now.weekday() + 1) % 7 # Sunday = 0
    start_date = (now - timedelta(days=today_weekday) - timedelta(weeks=52)).date()

    grid_data = []
    curr_date = start_date
    for c in range(cols):
        col_cells = []
        for r in range(rows):
            d_str = curr_date.strftime("%Y-%m-%d")
            count = commit_counts.get(d_str, 0)
            if count == 0:
                lvl = 0
            elif count <= 2:
                lvl = 1
            elif count <= 5:
                lvl = 2
            elif count <= 9:
                lvl = 3
            else:
                lvl = 4
            col_cells.append((lvl, count))
            curr_date += timedelta(days=1)
        grid_data.append(col_cells)

    months = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    month_step = cols / 12.0

    # 1. activity-matrix.svg
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">')
    svg.append('<style>')
    svg.append('.bg { fill: #080c14; stroke: #19273c; stroke-width: 1.2px; rx: 10px; }')
    svg.append('.title { font-family: monospace, -apple-system, sans-serif; font-size: 13px; font-weight: 700; fill: #e2e8f0; letter-spacing: 1px; }')
    svg.append('.badge { font-family: monospace, sans-serif; font-size: 10px; font-weight: 600; fill: #00f2fe; letter-spacing: 1px; }')
    svg.append('.lbl { font-family: monospace, -apple-system, sans-serif; font-size: 10px; fill: #64748b; }')
    svg.append('.dot { rx: 2.5px; ry: 2.5px; }')
    svg.append('</style>')
    svg.append(f'<rect width="{width}" height="{height}" class="bg" />')
    svg.append(f'<text x="20" y="27" class="title">⚡ Cadence &amp; Activity Matrix</text>')
    svg.append(f'<text x="{width - 20}" y="27" text-anchor="end" class="badge">● Live Timeline</text>')

    day_labels = [(1, "Mon"), (3, "Wed"), (5, "Fri")]
    for r_idx, txt in day_labels:
        y = start_y + r_idx * (dot_size + gap) + 9
        svg.append(f'<text x="12" y="{y}" class="lbl">{txt}</text>')

    for i, m_name in enumerate(months):
        x = start_x + int(i * month_step * (dot_size + gap))
        svg.append(f'<text x="{x}" y="{start_y - 10}" class="lbl">{m_name}</text>')

    for c in range(cols):
        for r in range(rows):
            lvl, count = grid_data[c][r]
            color = colors[lvl]
            x = start_x + c * (dot_size + gap)
            y = start_y + r * (dot_size + gap)
            svg.append(f'<rect x="{x}" y="{y}" width="{dot_size}" height="{dot_size}" fill="{color}" class="dot" />')

    leg_x = width - 140
    leg_y = height - 16
    svg.append(f'<text x="{leg_x - 30}" y="{leg_y + 9}" class="lbl">Less</text>')
    for i in range(5):
        lx = leg_x + i * (dot_size + 3)
        svg.append(f'<rect x="{lx}" y="{leg_y}" width="{dot_size}" height="{dot_size}" fill="{colors[i]}" class="dot" />')
    svg.append(f'<text x="{leg_x + 5 * (dot_size + 3) + 6}" y="{leg_y + 9}" class="lbl">More</text>')
    svg.append('</svg>')

    matrix_path = os.path.join(out_dir, "activity-matrix.svg")
    with open(matrix_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

    # 2. snake.svg
    cols_s = 48
    start_y_s = 45
    width_s = start_x + (cols_s * (dot_size + gap)) + 20
    height_s = start_y_s + (rows * (dot_size + gap)) + 30

    svg_s = []
    svg_s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_s}" height="{height_s}" viewBox="0 0 {width_s} {height_s}" fill="none">')
    svg_s.append('<style>')
    svg_s.append('.bg { fill: #080c14; stroke: #19273c; stroke-width: 1.2px; rx: 10px; }')
    svg_s.append('.title { font-family: monospace, -apple-system, sans-serif; font-size: 13px; font-weight: 700; fill: #e2e8f0; letter-spacing: 1px; }')
    svg_s.append('.badge { font-family: monospace, sans-serif; font-size: 10px; font-weight: 600; fill: #00f2fe; letter-spacing: 1px; }')
    svg_s.append('.grid-dot { rx: 2.5px; ry: 2.5px; fill: #121927; }')
    svg_s.append('.lit-1 { fill: #0a3a40; }')
    svg_s.append('.lit-2 { fill: #057a6e; }')
    svg_s.append('.lit-3 { fill: #00bfa5; }')
    svg_s.append('.lit-4 { fill: #00f2fe; }')
    svg_s.append('.snake-head { fill: #00f2fe; rx: 3px; filter: drop-shadow(0 0 5px #00f2fe); }')
    svg_s.append('.snake-body { fill: #38bdf8; rx: 2.5px; opacity: 0.85; }')
    svg_s.append('@keyframes snakeMove {')
    svg_s.append('  0% { transform: translate(0px, 0px); }')
    svg_s.append('  25% { transform: translate(160px, 0px); }')
    svg_s.append('  50% { transform: translate(160px, 45px); }')
    svg_s.append('  75% { transform: translate(320px, 45px); }')
    svg_s.append('  100% { transform: translate(0px, 0px); }')
    svg_s.append('}')
    svg_s.append('.snake-group { animation: snakeMove 12s ease-in-out infinite alternate; }')
    svg_s.append('</style>')
    svg_s.append(f'<rect width="{width_s}" height="{height_s}" class="bg" />')
    svg_s.append(f'<text x="20" y="24" class="title">🐍 Execution Trajectory</text>')
    svg_s.append(f'<text x="{width_s - 20}" y="24" text-anchor="end" class="badge">● Continuous Run</text>')

    for c in range(cols_s):
        for r in range(rows):
            lvl, _ = grid_data[c + (cols - cols_s)][r]
            x = start_x + c * (dot_size + gap)
            y = start_y_s + r * (dot_size + gap)
            cls = f"lit-{lvl}" if lvl > 0 else "grid-dot"
            svg_s.append(f'<rect x="{x}" y="{y}" width="{dot_size}" height="{dot_size}" class="{cls}" />')

    sx = start_x + 10 * (dot_size + gap)
    sy = start_y_s + 3 * (dot_size + gap)
    svg_s.append('<g class="snake-group">')
    svg_s.append(f'<rect x="{sx + (dot_size+gap)*3}" y="{sy}" width="{dot_size}" height="{dot_size}" class="snake-head" />')
    for seg in range(1, 4):
        svg_s.append(f'<rect x="{sx + (dot_size+gap)*(3-seg)}" y="{sy}" width="{dot_size}" height="{dot_size}" class="snake-body" />')
    svg_s.append('</g>')
    svg_s.append('</svg>')

    snake_path = os.path.join(out_dir, "snake.svg")
    with open(snake_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_s))

if __name__ == "__main__":
    token = os.environ.get("ORG_TOKEN") or os.environ.get("GITHUB_TOKEN")
    counts = fetch_activity_counts(token)
    
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    assets_dir = os.path.join(root_dir, "assets")
    profile_assets_dir = os.path.join(root_dir, "profile", "assets")
    
    generate_svgs(counts, assets_dir)
    generate_svgs(counts, profile_assets_dir)
    print("Activity SVGs successfully generated and synchronized.")
