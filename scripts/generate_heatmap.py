#!/usr/bin/env python3
"""Generate a GitHub-style contribution heatmap SVG for the profile README.

Pulls the last 365 days of public contributions via the GitHub GraphQL API
and renders a static SVG (no third-party image host required). Designed to be
run by a GitHub Action, but works locally too:

    GH_TOKEN=<token> python scripts/generate_heatmap.py
"""
import json
import os
import datetime
import urllib.request

USER = "Refeain"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "contribution-heatmap.svg")


def color(count: int) -> str:
    if count == 0:
        return "#ebedf0"
    if count <= 9:
        return "#9be9a8"
    if count <= 19:
        return "#40c463"
    if count <= 29:
        return "#30a14e"
    return "#216e39"


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
            weeks { contributionDays { contributionCount date } }
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

    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

    size = 11
    gap = 3
    step = size + gap
    left = 32
    top = 18
    cols = len(weeks)
    rows = 7
    width = left + cols * step
    height = top + rows * step

    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
           f'height="{height}" viewBox="0 0 {width} {height}">']

    for ri, lab in enumerate(["", "Mon", "", "Wed", "", "Fri", ""]):
        if lab:
            svg.append(f'<text x="0" y="{top + ri * step + size - 2}" '
                       f'font-size="10" font-family="sans-serif" fill="#57606a">{lab}</text>')

    prev_month = None
    for ci, week in enumerate(weeks):
        first = week["contributionDays"][0]["date"]
        m = int(first[5:7])
        if m != prev_month:
            svg.append(f'<text x="{left + ci * step}" y="{top - 6}" '
                       f'font-size="10" font-family="sans-serif" fill="#57606a">{months[m]}</text>')
            prev_month = m

    for ci, week in enumerate(weeks):
        for ri, day in enumerate(week["contributionDays"]):
            count = day["contributionCount"]
            x = left + ci * step
            y = top + ri * step
            svg.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" '
                       f'rx="2" ry="2" fill="{color(count)}"/>')

    svg.append("</svg>")

    out_path = os.path.abspath(OUT)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print(f"generated heatmap -> {out_path} ({cols} weeks)")


if __name__ == "__main__":
    main()
