#!/usr/bin/env python3
"""Generate a GitHub contribution trend line chart SVG for the profile README.

Pulls the last 365 days of public contributions via the GitHub GraphQL API
and renders a self-contained line chart (no third-party image host).

Visual style:
  * dark rounded card, blue->purple gradient line, subtle area fill
  * a left-to-right "draw" animation (plays every render -- GitHub embeds
    as <img> and only runs internal CSS animations)

Run by a GitHub Action, or locally:

    GH_TOKEN=<token> python scripts/generate_chart.py
"""
import json
import os
import datetime
import urllib.request

USER = "Refeain"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "contribution-chart.svg")

W, H = 720, 240
PAD_L, PAD_R, PAD_T, PAD_B = 46, 18, 36, 26
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def catmull_rom_to_bezier(pts):
    """Return an SVG path 'd' string with smooth curves through pts."""
    if len(pts) < 2:
        return ""
    d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[i + 1]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        d += (f" C {c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} "
              f"{p2[0]:.2f} {p2[1]:.2f}")
    return d


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN / GITHUB_TOKEN not set")

    now = datetime.datetime.now(datetime.timezone.utc)
    to_date = now.strftime("%Y-%m-%dT00:00:00Z")
    from_date = (now - datetime.timedelta(days=364)).strftime("%Y-%m-%dT00:00:00Z")

    query = """
    query($user: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $user) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date weekday } }
          }
        }
      }
    }
    """
    body = json.dumps({
        "query": query,
        "variables": {"user": USER, "from": from_date, "to": to_date},
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    total = cal.get("totalContributions", 0)

    series = []
    for w in weeks:
        s = sum(d["contributionCount"] for d in w["contributionDays"])
        first = w["contributionDays"][0]["date"]
        series.append((s, first))

    n = len(series)
    vals = [s for s, _ in series]
    maxv = max(vals) if vals else 0
    if maxv <= 0:
        maxv = 1

    plotW = W - PAD_L - PAD_R
    plotH = H - PAD_T - PAD_B
    baseline = PAD_T + plotH

    def xpos(i):
        return PAD_L + (i / (n - 1)) * plotW if n > 1 else PAD_L + plotW / 2

    def ypos(v):
        return baseline - (v / maxv) * plotH

    pts = [(xpos(i), ypos(v)) for i, (v, _) in enumerate(series)]
    line_d = catmull_rom_to_bezier(pts)
    area_d = line_d + f" L {pts[-1][0]:.2f} {baseline:.2f} L {pts[0][0]:.2f} {baseline:.2f} Z"

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}" role="img" '
               f'aria-label="Contribution trend line chart">')
    svg.append('<defs>')
    svg.append('<linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">'
               '<stop offset="0%" stop-color="#3B82F6"/>'
               '<stop offset="100%" stop-color="#BC8CFF"/></linearGradient>')
    svg.append('<linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">'
               '<stop offset="0%" stop-color="#3B82F6" stop-opacity="0.35"/>'
               '<stop offset="100%" stop-color="#3B82F6" stop-opacity="0"/></linearGradient>')
    svg.append('</defs>')
    svg.append('<style>')
    svg.append('@keyframes cc-draw{to{stroke-dashoffset:0}}')
    svg.append('@keyframes cc-fade{from{opacity:0}to{opacity:1}}')
    svg.append('.cc-line{stroke-dasharray:1;stroke-dashoffset:1;'
               'animation:cc-draw 1.8s cubic-bezier(.4,0,.2,1) forwards}')
    svg.append('.cc-area{animation:cc-fade 1.2s ease 1s forwards;opacity:0}')
    svg.append('.cc-dot{animation:cc-fade .6s ease 1.7s forwards;opacity:0}')
    svg.append('</style>')

    # card background
    svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="#0D1117"/>')

    # title + total
    svg.append(f'<text x="{PAD_L}" y="22" font-size="13" '
               f'font-family="-apple-system,Segoe UI,sans-serif" fill="#c9d1d9" '
               f'font-weight="600">Contributions per week</text>')
    svg.append(f'<text x="{W - PAD_R}" y="22" text-anchor="end" font-size="11" '
               f'font-family="-apple-system,Segoe UI,sans-serif" fill="#8b949e">'
               f'{total} in the last year</text>')

    # y gridlines + labels (0, mid, max)
    for frac, lab in [(0.0, "0"), (0.5, str(maxv // 2)), (1.0, str(maxv))]:
        gy = baseline - frac * plotH
        svg.append(f'<line x1="{PAD_L}" y1="{gy:.2f}" x2="{W - PAD_R}" y2="{gy:.2f}" '
                   f'stroke="#21262d" stroke-width="1"/>')
        svg.append(f'<text x="{PAD_L - 8}" y="{gy + 3:.2f}" text-anchor="end" '
                   f'font-size="9" font-family="-apple-system,Segoe UI,sans-serif" '
                   f'fill="#8b949e">{lab}</text>')

    # x month labels: when month changes
    prev_m = None
    for i, (v, first) in enumerate(series):
        m = int(first[5:7])
        if m != prev_m:
            svg.append(f'<text x="{xpos(i):.2f}" y="{H - 8}" text-anchor="middle" '
                       f'font-size="9" font-family="-apple-system,Segoe UI,sans-serif" '
                       f'fill="#8b949e">{MONTHS[m-1]}</text>')
            prev_m = m

    # area + line
    svg.append(f'<path class="cc-area" d="{area_d}" fill="url(#areaGrad)" '
               f'stroke="none"/>')
    svg.append(f'<path class="cc-line" d="{line_d}" fill="none" '
               f'stroke="url(#lineGrad)" stroke-width="2.5" '
               f'stroke-linecap="round" stroke-linejoin="round" '
               f'pathLength="1"/>')

    # last point dot
    lx, ly = pts[-1]
    svg.append(f'<circle class="cc-dot" cx="{lx:.2f}" cy="{ly:.2f}" r="3.5" '
               f'fill="#BC8CFF" stroke="#0D1117" stroke-width="1.5"/>')

    svg.append('</svg>')

    out = os.path.abspath(OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print(f"generated line chart -> {out} ({n} weeks, total={total}, max/week={maxv})")


if __name__ == "__main__":
    main()
