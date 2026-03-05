
import os
import json
import datetime
import urllib.request
from pathlib import Path
import random

# ---------------- CONFIG ----------------
USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_ACTOR") or ""
TOKEN = os.environ.get("GH_TOKEN") or ""
OUT_PATH = os.environ.get("OUT_PATH", "assets/signal_barcode.svg")

TZ_OFFSET_MINUTES = int(os.environ.get("TZ_OFFSET_MINUTES", "330"))
DAYS = int(os.environ.get("DAYS", "365"))

BG = "#020203"
GRID = "#1b1b1d"
ACCENT = "#ff4040"
TEXT = "#e5e7eb"
MUTED = "#9ca3af"

FONT = "JetBrains Mono, monospace"

WIDTH = 980
HEIGHT = 360
PAD_X = 40
HEADER_H = 60

PLOT_TOP = HEADER_H + 10
CHANNEL_H = 70

# ---------------- HELPERS ----------------
def iso_z(dt):
    return dt.replace(microsecond=0).isoformat() + "Z"

def gh_api(query, variables):
    req = urllib.request.Request("https://api.github.com/graphql", method="POST")
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    payload = json.dumps({"query": query, "variables": variables}).encode()

    with urllib.request.urlopen(req, data=payload, timeout=30) as r:
        data = json.loads(r.read().decode())

    return data["data"]

def compute_window(days, tz_offset):
    now = datetime.datetime.utcnow()
    local = now + datetime.timedelta(minutes=tz_offset)

    end_date = local.date()
    start_date = end_date - datetime.timedelta(days=days - 1)

    from_dt = datetime.datetime.combine(start_date, datetime.time(0))
    to_dt = datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time(0))

    from_dt_utc = from_dt - datetime.timedelta(minutes=tz_offset)
    to_dt_utc = to_dt - datetime.timedelta(minutes=tz_offset)

    return from_dt_utc, to_dt_utc, start_date, end_date

# ---------------- MAIN ----------------
def main():
    if not USER:
        raise SystemExit("GH_USER missing")

    from_dt, to_dt, start_date, end_date = compute_window(DAYS, TZ_OFFSET_MINUTES)

    query = """
    query($user:String!, $from:DateTime!, $to:DateTime!) {
      user(login: $user) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
          totalCommitContributions
          totalPullRequestContributions
          totalRepositoryContributions
        }
      }
    }
    """

    data = gh_api(query, {
        "user": USER,
        "from": iso_z(from_dt),
        "to": iso_z(to_dt),
    })

    cal = data["user"]["contributionsCollection"]["contributionCalendar"]

    commits_total = data["user"]["contributionsCollection"]["totalCommitContributions"]
    repos_total = data["user"]["contributionsCollection"]["totalRepositoryContributions"]
    prs_total = data["user"]["contributionsCollection"]["totalPullRequestContributions"]

    by_date = {}
    for w in cal["weeks"]:
        for d in w["contributionDays"]:
            by_date[d["date"]] = int(d["contributionCount"])

    counts = []
    cur = start_date
    while cur <= end_date:
        counts.append(by_date.get(cur.isoformat(),0))
        cur += datetime.timedelta(days=1)

    peak = max(counts) if counts else 1

    sx = (WIDTH - 2*PAD_X)/(DAYS-1)

    channels = []

    for i,v in enumerate(counts):
        x = PAD_X + i*sx
        h = (v/peak)*(CHANNEL_H-8)
        channels.append((x,h))

    # glitch lines
    glitches = []
    for _ in range(14):
        x = random.uniform(PAD_X, WIDTH-PAD_X)
        y = random.uniform(HEADER_H, HEIGHT-20)
        glitches.append((x,y))

    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{WIDTH}' height='{HEIGHT}'>

<rect width='100%' height='100%' fill='{BG}'/>

<!-- header -->
<text x='{PAD_X}' y='28' font-family='{FONT}' font-size='13' fill='{ACCENT}'>
SIGINT TELEMETRY
</text>

<text x='{PAD_X}' y='46' font-family='{FONT}' font-size='11' fill='{MUTED}'>
COMMITS {commits_total} · PR {prs_total} · REPOS {repos_total}
</text>

<!-- channel labels -->
<text x='{PAD_X-28}' y='{PLOT_TOP+10}' font-family='{FONT}' font-size='9' fill='{MUTED}'>CODE</text>
<text x='{PAD_X-28}' y='{PLOT_TOP+CHANNEL_H+10}' font-family='{FONT}' font-size='9' fill='{MUTED}'>COMMITS</text>
<text x='{PAD_X-28}' y='{PLOT_TOP+CHANNEL_H*2+10}' font-family='{FONT}' font-size='9' fill='{MUTED}'>REPOS</text>

"""

    # generate 3 telemetry channels
    for ch in range(3):
        base = PLOT_TOP + ch*CHANNEL_H
        svg += f"<line x1='{PAD_X}' y1='{base+CHANNEL_H}' x2='{WIDTH-PAD_X}' y2='{base+CHANNEL_H}' stroke='{GRID}'/>"

        for x,h in channels:
            svg += f"<rect x='{x:.2f}' y='{base+CHANNEL_H-h:.2f}' width='2' height='{h:.2f}' fill='{ACCENT}'/>"

    # glitch effect
    for x,y in glitches:
        svg += f"<rect x='{x:.2f}' y='{y:.2f}' width='14' height='1' fill='{ACCENT}' opacity='0.5'/>"

    svg += "</svg>"

    Path(os.path.dirname(OUT_PATH) or ".").mkdir(parents=True, exist_ok=True)

    with open(OUT_PATH,"w",encoding="utf-8") as f:
        f.write(svg)

    print("SIGINT multi-channel telemetry generated →", OUT_PATH)


if __name__ == "__main__":
    main()
