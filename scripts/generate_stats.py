#!/usr/bin/env python3
"""Generate self-hosted GitHub stats / streak / languages cards as SVG.

Pulls profile data via the GitHub GraphQL API and renders three self-contained
SVG cards (no third-party image host, no vercel, no Cloudflare login). Served
through jsDelivr just like the contribution heatmap, so they render reliably in
China. Designed to run from a GitHub Action, also works locally:

    GH_TOKEN=<token> python scripts/generate_stats.py
"""
import json
import os
import datetime
import urllib.request

USER = "Refeain"
ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")

# dracula-ish palette tuned to the README's dark cards
BG = "#0D1117"
BORDER = "#30363D"
TITLE = "#58A6FF"
TEXT = "#C9D1D9"
SUB = "#8B949E"
ACCENT = "#BC8CFF"
BAR_BG = "#21262D"
BAR_FG = "#BC8CFF"


def gql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def num(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.1f}k".rstrip("0").rstrip(".")
    return str(n)


def card_frame(w: int, h: int, title: str, icon: str) -> list:
    """Common rounded background + header for a card."""
    s = []
    s.append(f'<rect x="0" y="0" width="{w}" height="{h}" rx="12" ry="12" '
             f'fill="{BG}" stroke="{BORDER}" stroke-width="1"/>')
    # header icon + title
    s.append(f'<text x="18" y="34" font-size="20">{icon}</text>')
    s.append(f'<text x="46" y="34" font-size="15" font-weight="700" '
             f'font-family="-apple-system,Segoe UI,sans-serif" fill="{TITLE}">{title}</text>')
    return s


def stats_card(data: dict) -> str:
    w, h = 460, 232
    col = data["user"]["contributionsCollection"]
    repos = data["user"]["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    rows = [
        ("📅", "Contributions (last year)", col["contributionCalendar"]["totalContributions"]),
        ("💻", "Commits (last year)", col["totalCommitContributions"]),
        ("🔀", "Total Pull Requests", col["totalPullRequestContributions"]),
        ("🐛", "Total Issues", col["totalIssueContributions"]),
        ("⭐", "Total Stars Earned", total_stars),
        ("👥", "Followers / Following",
         f'{data["user"]["followers"]["totalCount"]} / {data["user"]["following"]["totalCount"]}'),
    ]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}" role="img" aria-label="GitHub stats">']
    s += card_frame(w, h, f"{USER}'s GitHub Stats", "📊")
    y = 70
    for icon, label, val in rows:
        s.append(f'<text x="20" y="{y}" font-size="15">{icon}</text>')
        s.append(f'<text x="46" y="{y}" font-size="14" '
                 f'font-family="-apple-system,Segoe UI,sans-serif" fill="{TEXT}">{label}</text>')
        s.append(f'<text x="{w-20}" y="{y}" font-size="14" text-anchor="end" '
                 f'font-family="-apple-system,Segoe UI,sans-serif" font-weight="700" fill="{ACCENT}">{val}</text>')
        s.append(f'<line x1="46" y1="{y+8}" x2="{w-20}" y2="{y+8}" stroke="{BAR_BG}" stroke-width="3" stroke-linecap="round"/>')
        y += 27
    s.append("</svg>")
    return "\n".join(s)


def compute_streaks(weeks: list) -> tuple:
    days = []
    for wk in weeks:
        for d in wk["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort(key=lambda x: x[0])
    # current streak: allow today to be 0 (not contributed yet today)
    cur = 0
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    # longest streak within window
    longest = run = 0
    for _, c in days:
        if c > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return cur, longest


def streak_card(data: dict) -> str:
    cal = data["user"]["contributionsCollection"]["contributionCalendar"]
    cur, longest = compute_streaks(cal["weeks"])
    total = cal["totalContributions"]
    w, h = 460, 232
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}" role="img" aria-label="GitHub streak">']
    s += card_frame(w, h, f"{USER}'s Streak", "🔥")
    blocks = [
        ("🔥", "Current Streak", f"{cur} days"),
        ("📆", "Longest Streak", f"{longest} days"),
        ("✅", "Total Contributions", f"{total}"),
    ]
    y = 84
    for icon, label, val in blocks:
        s.append(f'<text x="20" y="{y}" font-size="16">{icon}</text>')
        s.append(f'<text x="48" y="{y}" font-size="14" '
                 f'font-family="-apple-system,Segoe UI,sans-serif" fill="{SUB}">{label}</text>')
        s.append(f'<text x="{w-20}" y="{y}" font-size="18" text-anchor="end" '
                 f'font-family="-apple-system,Segoe UI,sans-serif" font-weight="700" fill="{ACCENT}">{val}</text>')
        y += 50
    s.append("</svg>")
    return "\n".join(s)


def langs_card(data: dict) -> str:
    agg = {}
    for r in data["user"]["repositories"]["nodes"]:
        for edge in r["languages"]["edges"]:
            name = edge["node"]["name"]
            agg[name] = agg.get(name, 0) + edge["size"]
    top = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:8]
    total = sum(v for _, v in top) or 1
    w, h = 460, 232
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}" role="img" aria-label="Top languages">']
    s += card_frame(w, h, "Top Languages", "🧩")
    if not top:
        s.append(f'<text x="20" y="80" font-size="14" fill="{SUB}" '
                 f'font-family="-apple-system,Segoe UI,sans-serif">No language data yet.</text>')
    else:
        y = 70
        for name, v in top:
            pct = v / total * 100
            color = next((e["node"]["color"] for r in data["user"]["repositories"]["nodes"]
                          for e in r["languages"]["edges"] if e["node"]["name"] == name), "#8B949E")
            s.append(f'<text x="20" y="{y}" font-size="13" '
                     f'font-family="-apple-system,Segoe UI,sans-serif" fill="{TEXT}">{name}</text>')
            s.append(f'<text x="{w-20}" y="{y}" font-size="13" text-anchor="end" '
                     f'font-family="-apple-system,Segoe UI,sans-serif" fill="{SUB}">{pct:.1f}%</text>')
            s.append(f'<rect x="20" y="{y+6}" width="{w-40}" height="8" rx="4" fill="{BAR_BG}"/>')
            s.append(f'<rect x="20" y="{y+6}" width="{(w-40)*pct/100:.1f}" height="8" rx="4" fill="{color}"/>')
            y += 34
    s.append("</svg>")
    return "\n".join(s)


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN / GITHUB_TOKEN not set")

    query = """
    query($user: String!) {
      user(login: $user) {
        followers { totalCount }
        following { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date } }
          }
        }
      }
    }
    """
    payload = gql(token, query, {"user": USER})
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    data = payload["data"]

    os.makedirs(ASSETS, exist_ok=True)
    out = {
        "stats-card.svg": stats_card(data),
        "streak-card.svg": streak_card(data),
        "langs-card.svg": langs_card(data),
    }
    for name, svg in out.items():
        path = os.path.abspath(os.path.join(ASSETS, name))
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"generated -> {path}")


if __name__ == "__main__":
    main()
