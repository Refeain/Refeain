#!/usr/bin/env python3
"""Generate every self-hosted SVG card used by the profile README.

One GraphQL round-trip, five self-contained SVGs, zero third-party image hosts.
Served through jsDelivr so they render reliably in China.

Design rules this file sticks to:
  * inline presentation attributes only -- no <style>, no CSS animation.
    A card must look identical in a browser, in an <img>, in a screenshot,
    and under prefers-reduced-motion.
  * geometry never overflows its own viewBox (the v1 cards clipped row 6).
  * XML-escape everything that comes from the API (repo descriptions).

    GH_TOKEN=<token> python scripts/generate_cards.py
"""
import datetime
import html
import json
import os
import urllib.request

USER = "Refeain"
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

# ---------------------------------------------------------------- design tokens
BG = "#0D1117"
PANEL = "#161B22"
BORDER = "#21262D"
TEXT = "#E6EDF3"
SUB = "#8B949E"
DIM = "#30363D"
BLUE = "#58A6FF"
PURPLE = "#BC8CFF"
GREEN = "#3FB950"
GOLD = "#D29922"
RED = "#F85149"
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,"
        "'Noto Sans',sans-serif")
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"

HEAT = ["#161B22", "#0E4429", "#006D32", "#26A641", "#39D353"]


# --------------------------------------------------------------------- helpers
def esc(s):
    return html.escape(str(s), quote=True)


def num(n):
    if n >= 1000:
        return f"{n / 1000:.1f}k".rstrip("0").rstrip(".")
    return str(n)


def svg_open(w, h, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}" '
            f'font-family="{FONT}">')


def card(w, h, title, dot=BLUE):
    """Rounded shell + header row. Returns (list_of_elements, first_body_y)."""
    s = [
        f'<defs><linearGradient id="fade{dot[1:]}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{PANEL}" stop-opacity=".55"/>'
        f'<stop offset="100%" stop-color="{PANEL}" stop-opacity="0"/>'
        f'</linearGradient></defs>',
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" '
        f'fill="{BG}" stroke="{BORDER}"/>',
        f'<rect x=".5" y=".5" width="{w - 1}" height="46" rx="14" '
        f'fill="url(#fade{dot[1:]})"/>',
        f'<circle cx="22" cy="23.5" r="3.5" fill="{dot}"/>',
        f'<text x="34" y="28" font-size="12.5" font-weight="600" '
        f'letter-spacing=".3" fill="{TEXT}">{esc(title)}</text>',
        f'<line x1="14" y1="46" x2="{w - 14}" y2="46" '
        f'stroke="{BORDER}" stroke-width="1"/>',
    ]
    return s, 46


# ------------------------------------------------------------------------ data
QUERY = """
query($user:String!){
  user(login:$user){
    name
    followers{totalCount} following{totalCount}
    repositories(first:100, ownerAffiliations:OWNER, isFork:false,
                 orderBy:{field:PUSHED_AT, direction:DESC}){
      totalCount
      nodes{
        name description stargazerCount forkCount pushedAt isPrivate
        primaryLanguage{name color}
        languages(first:10, orderBy:{field:SIZE,direction:DESC}){
          edges{size node{name color}}
        }
      }
    }
    contributionsCollection{
      totalCommitContributions totalPullRequestContributions
      totalIssueContributions
      contributionCalendar{
        totalContributions
        weeks{contributionDays{contributionCount date weekday}}
      }
    }
  }
}
"""


def fetch():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN / GITHUB_TOKEN not set")
    body = json.dumps({"query": QUERY, "variables": {"user": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    return payload["data"]["user"]


# ------------------------------------------------------------------ stats card
def stats_card(u):
    W, H = 460, 210
    col = u["contributionsCollection"]
    cal = col["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    active = sum(1 for d in days if d["contributionCount"] > 0)
    best = max((d["contributionCount"] for d in days), default=0)
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])

    tiles = [
        ("Contributions", num(cal["totalContributions"]), BLUE),
        ("Commits", num(col["totalCommitContributions"]), PURPLE),
        ("Active days", f"{active}", GREEN),
        ("Repositories", f'{u["repositories"]["totalCount"]}', GOLD),
        ("Stars earned", num(stars), BLUE),
        ("Pull requests", num(col["totalPullRequestContributions"]), PURPLE),
    ]

    s = [svg_open(W, H, "GitHub stats")]
    head, y0 = card(W, H, "Contribution activity", BLUE)
    s += head

    # 3 x 2 tile grid
    cw, ch = (W - 14 * 2 - 8 * 2) / 3, 56
    for i, (label, value, color) in enumerate(tiles):
        r, c = divmod(i, 3)
        x = 14 + c * (cw + 8)
        y = y0 + 12 + r * (ch + 8)
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" height="{ch}" '
                 f'rx="9" fill="{PANEL}" stroke="{BORDER}"/>')
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="2.5" height="{ch}" '
                 f'rx="1.25" fill="{color}" opacity=".85"/>')
        s.append(f'<text x="{x + 12:.1f}" y="{y + 24:.1f}" font-size="19" '
                 f'font-weight="700" fill="{TEXT}">{esc(value)}</text>')
        s.append(f'<text x="{x + 12:.1f}" y="{y + 41:.1f}" font-size="10.5" '
                 f'fill="{SUB}">{esc(label)}</text>')

    foot = y0 + 12 + 2 * (ch + 8) + 4
    s.append(f'<text x="14" y="{foot + 9:.1f}" font-size="10.5" fill="{DIM}">'
             f'peak {best} in a single day &#183; trailing 12 months</text>')
    s.append("</svg>")
    return "\n".join(s)


# ------------------------------------------------------------------ langs card
def langs_card(u):
    W, H = 460, 210
    agg, colors = {}, {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            agg[n] = agg.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or SUB
    top = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:5]
    total = sum(v for _, v in top) or 1

    s = [svg_open(W, H, "Top languages")]
    head, y0 = card(W, H, "Language mix", PURPLE)
    s += head

    # donut, geometry derived from H so it can never overflow
    cx, cy, r, sw = 78, y0 + (H - y0) / 2 - 4, 44, 13
    circ = 2 * 3.141592653589793 * r
    off = 0.0
    s.append(f'<circle cx="{cx}" cy="{cy:.1f}" r="{r}" fill="none" '
             f'stroke="{PANEL}" stroke-width="{sw}"/>')
    for name, v in top:
        seg = circ * v / total
        # a negative dash length is invalid SVG and makes Chrome paint the whole
        # ring in this colour, so clamp to zero and skip segments that vanish
        dash = seg - 2.4
        if dash <= 0.5:
            off += seg
            continue
        s.append(f'<circle cx="{cx}" cy="{cy:.1f}" r="{r}" fill="none" '
                 f'stroke="{colors[name]}" stroke-width="{sw}" '
                 f'stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
                 f'stroke-dashoffset="{-off:.2f}" '
                 f'transform="rotate(-90 {cx} {cy:.1f})" stroke-linecap="butt"/>')
        off += seg
    s.append(f'<text x="{cx}" y="{cy - 1:.1f}" font-size="16" font-weight="700" '
             f'text-anchor="middle" fill="{TEXT}">{len(top)}</text>')
    s.append(f'<text x="{cx}" y="{cy + 14:.1f}" font-size="9.5" '
             f'text-anchor="middle" fill="{SUB}">languages</text>')

    # legend, 5 rows fits inside 210 - 46 = 164 -> 5 * 30 = 150
    lx, ly = 146, y0 + 22
    for name, v in top:
        pct = v / total * 100
        s.append(f'<circle cx="{lx}" cy="{ly - 3.5:.1f}" r="4" '
                 f'fill="{colors[name]}"/>')
        s.append(f'<text x="{lx + 13}" y="{ly:.1f}" font-size="12" '
                 f'fill="{TEXT}">{esc(name)}</text>')
        s.append(f'<text x="{W - 16}" y="{ly:.1f}" font-size="11.5" '
                 f'text-anchor="end" fill="{SUB}">{pct:.1f}%</text>')
        s.append(f'<rect x="{lx + 13}" y="{ly + 9:.1f}" width="{W - 16 - lx - 13}" '
                 f'height="3" rx="1.5" fill="{PANEL}"/>')
        s.append(f'<rect x="{lx + 13}" y="{ly + 9:.1f}" '
                 f'width="{(W - 16 - lx - 13) * pct / 100:.1f}" height="3" '
                 f'rx="1.5" fill="{colors[name]}" opacity=".85"/>')
        ly += 30

    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- heatmap card
def heatmap_card(u):
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    nw = len(weeks)
    cell, gap = 11, 3
    step = cell + gap
    left, top = 34, 46 + 26
    W = left + nw * step + 14
    H = top + 7 * step + 32

    s = [svg_open(W, H, "Contribution heatmap")]
    head, _ = card(W, H, "Contribution calendar", GREEN)
    s += head
    # summary lives in the header bar, so it can never collide with month labels
    s.append(f'<text x="{W - 16}" y="{28}" font-size="11" text-anchor="end" '
             f'fill="{SUB}"><tspan font-weight="600" fill="{TEXT}">'
             f'{cal["totalContributions"]}</tspan> contributions in the last '
             f'year</text>')

    # month labels
    prev = None
    for i, wk in enumerate(weeks):
        d = wk["contributionDays"][0]["date"]
        m = int(d[5:7])
        if m != prev:
            s.append(f'<text x="{left + i * step}" y="{top - 7}" font-size="9" '
                     f'fill="{SUB}">{datetime.date(2000, m, 1):%b}</text>')
            prev = m

    # weekday labels (Mon / Wed / Fri)
    for row, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        s.append(f'<text x="{left - 7}" y="{top + row * step + cell - 1}" '
                 f'font-size="9" text-anchor="end" fill="{SUB}">{lab}</text>')

    for i, wk in enumerate(weeks):
        for d in wk["contributionDays"]:
            c = d["contributionCount"]
            lvl = 0 if c == 0 else 1 if c <= 2 else 2 if c <= 5 else 3 if c <= 9 else 4
            x = left + i * step
            y = top + d["weekday"] * step
            s.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                     f'rx="2.5" fill="{HEAT[lvl]}">'
                     f'<title>{d["date"]}: {c}</title></rect>')

    # legend, bottom-right (reserve room for the "More" label so it never clips)
    lx = W - 20 - 26 - (5 * step - gap)
    ly = H - 16
    s.append(f'<text x="{lx - 8}" y="{ly + 9}" font-size="9" text-anchor="end" '
             f'fill="{SUB}">Less</text>')
    for k in range(5):
        s.append(f'<rect x="{lx + k * step}" y="{ly}" width="{cell}" height="{cell}" '
                 f'rx="2.5" fill="{HEAT[k]}"/>')
    s.append(f'<text x="{lx + 5 * step + 2}" y="{ly + 9}" font-size="9" '
             f'fill="{SUB}">More</text>')

    s.append("</svg>")
    return "\n".join(s)


# ------------------------------------------------------------------ repos card
def repos_card(u):
    W = 460
    # never leak private repositories onto a public profile
    repos = [r for r in u["repositories"]["nodes"] if not r.get("isPrivate")][:3]
    rh = 62
    H = 46 + 14 + len(repos) * rh + 6

    s = [svg_open(W, H, "Featured repositories")]
    head, y0 = card(W, H, "Recent repositories", GOLD)
    s += head

    for i, r in enumerate(repos):
        y = y0 + 10 + i * rh
        lang = (r["primaryLanguage"] or {}).get("name")
        col = (r["primaryLanguage"] or {}).get("color") or SUB
        desc = (r["description"] or "No description").replace("\n", " ")
        if len(desc) > 62:
            desc = desc[:61] + "\u2026"
        s.append(f'<text x="14" y="{y + 13:.1f}" font-size="12.5" font-weight="600" '
                 f'fill="{BLUE}">{esc(r["name"])}</text>')
        s.append(f'<text x="{W - 14}" y="{y + 13:.1f}" font-size="10.5" '
                 f'text-anchor="end" fill="{SUB}">'
                 f'&#9733; {num(r["stargazerCount"])} &#183; {r["pushedAt"][:7]}</text>')
        s.append(f'<text x="14" y="{y + 29:.1f}" font-size="10.5" '
                 f'fill="{SUB}">{esc(desc)}</text>')
        if lang:
            s.append(f'<circle cx="17" cy="{y + 40:.1f}" r="3.5" fill="{col}"/>')
            s.append(f'<text x="25" y="{y + 43.5:.1f}" font-size="9.5" '
                     f'fill="{SUB}">{esc(lang)}</text>')
        if i < len(repos) - 1:
            s.append(f'<line x1="14" y1="{y + rh - 4:.1f}" x2="{W - 14}" '
                     f'y2="{y + rh - 4:.1f}" stroke="{BORDER}"/>')

    s.append("</svg>")
    return "\n".join(s)


# -------------------------------------------------------------------------- run
def main() -> None:
    u = fetch()
    os.makedirs(ASSETS, exist_ok=True)
    out = {
        "stats-card.svg": stats_card(u),
        "langs-card.svg": langs_card(u),
        "contribution-chart.svg": heatmap_card(u),
        "repos-card.svg": repos_card(u),
    }
    for name, svg in out.items():
        path = os.path.abspath(os.path.join(ASSETS, name))
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg + "\n")
        print(f"generated -> {path} ({len(svg)} chars)")


if __name__ == "__main__":
    main()
