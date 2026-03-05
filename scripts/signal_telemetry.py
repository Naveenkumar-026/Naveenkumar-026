
import os
import json
import datetime
import urllib.request
from pathlib import Path

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
HEIGHT = 300
PAD_X = 40
HEADER_H = 60

PLOT_TOP = HEADER_H + 10
PLOT_H = 170
PLOT_BOTTOM = PLOT_TOP + PLOT_H

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

    by_date = {}
    for w in cal["weeks"]:
        for d in w["contributionDays"]:
            by_date[d["date"]] = int(d["contributionCount"])

    counts = []
    cur = start_date
    while cur <= end_date:
        counts.append(by_date.get(cur.isoformat(),0))
        cur += datetime.timedelta(days=1)

    total = sum(counts)
    peak = max(counts) if counts else 1

    sx = (WIDTH - 2*PAD_X)/(DAYS-1)

    bars = []
    markers = []

    for i,v in enumerate(counts):
        x = PAD_X + i*sx
        h = (v/peak)*(PLOT_H-10)

        if v > 0:
            bars.append((x,h))

        if v >= peak*0.6:
            markers.append((x,h))

    grid_lines = ""
    for i in range(5):
        y = PLOT_TOP + (i*(PLOT_H/4))
        grid_lines += f"<line x1='{PAD_X}' y1='{y:.1f}' x2='{WIDTH-PAD_X}' y2='{y:.1f}' stroke='{GRID}'/>"

    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{WIDTH}' height='{HEIGHT}'>

<rect width='100%' height='100%' fill='{BG}'/>

<!-- grid -->
{grid_lines}

<!-- histogram -->
{"".join(f"<rect x='{x:.2f}' y='{PLOT_BOTTOM-h:.2f}' width='2.4' height='{h:.2f}' fill='{ACCENT}'/>" for x,h in bars)}

<!-- high activity markers -->
{"".join(f"<circle cx='{x:.2f}' cy='{PLOT_BOTTOM-h:.2f}' r='3' fill='{TEXT}'/>" for x,h in markers)}

<!-- baseline -->
<line x1='{PAD_X}' y1='{PLOT_BOTTOM}' x2='{WIDTH-PAD_X}' y2='{PLOT_BOTTOM}' stroke='{ACCENT}' stroke-width='1'/>

<!-- header -->
<text x='{PAD_X}' y='28' font-family='{FONT}' font-size='13' fill='{ACCENT}'>
SIGINT TELEMETRY // 365D
</text>

<text x='{PAD_X}' y='46' font-family='{FONT}' font-size='11' fill='{MUTED}'>
{total} events · peak/day {peak}
</text>

<!-- axis labels -->
<text x='{WIDTH-PAD_X}' y='{PLOT_BOTTOM+16}' font-family='{FONT}' font-size='10' fill='{MUTED}' text-anchor='end'>
timeline →
</text>

</svg>
"""

    Path(os.path.dirname(OUT_PATH) or ".").mkdir(parents=True, exist_ok=True)

    with open(OUT_PATH,"w",encoding="utf-8") as f:
        f.write(svg)

    print("SIGINT telemetry generated →", OUT_PATH)

if __name__ == "__main__":
    main()
