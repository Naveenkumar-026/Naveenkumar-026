
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

BG = "#020000"
ACCENT = "#ff2a2a"
ACCENT_LIGHT = "#ff8080"
GRID = "#2b0a0a"
MUTED = "#6b7280"

FONT = "JetBrains Mono, monospace"

WIDTH = 980
HEIGHT = 300
PAD_X = 28
HEADER_H = 56

PLOT_TOP = HEADER_H + 10
PLOT_H = 160
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

def moving_avg(series, window=11):
    half = window // 2
    out = []
    for i in range(len(series)):
        lo = max(0, i-half)
        hi = min(len(series), i+half+1)
        out.append(sum(series[lo:hi])/(hi-lo))
    return out

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

    ma = moving_avg(counts, 9)

    sx = (WIDTH - 2*PAD_X)/(DAYS-1)

    pts = []
    hist = []
    for i,v in enumerate(ma):
        x = PAD_X + i*sx
        y = PLOT_BOTTOM - (v/peak)*(PLOT_H-10)
        pts.append((x,y))

        h = (v/peak)*(PLOT_H*0.4)
        hist.append((x, h))

    path = "M " + " ".join(f"{x:.2f},{y:.2f}" for x,y in pts)

    # generate random spectrum spikes
    spikes = []
    for _ in range(22):
        x = random.uniform(PAD_X, WIDTH-PAD_X)
        h = random.uniform(20,80)
        spikes.append((x,h))

    # interference bursts
    bursts = []
    for _ in range(5):
        x = random.uniform(PAD_X, WIDTH-PAD_X)
        bursts.append(x)

    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{WIDTH}' height='{HEIGHT}'>

<defs>

<linearGradient id='bgGrad' x1='0' x2='0' y1='0' y2='1'>
<stop offset='0%' stop-color='{BG}'/>
<stop offset='100%' stop-color='#000000'/>
</linearGradient>

<linearGradient id='signalGrad' x1='0' x2='1'>
<stop offset='0%' stop-color='#7f1d1d'/>
<stop offset='50%' stop-color='{ACCENT}'/>
<stop offset='100%' stop-color='{ACCENT_LIGHT}'/>
</linearGradient>

<filter id='glow'>
<feGaussianBlur stdDeviation='4'/>
</filter>

<filter id='noise'>
<feTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3'/>
</filter>

</defs>

<rect width='100%' height='100%' fill='url(#bgGrad)'/>
<rect width='100%' height='100%' filter='url(#noise)' opacity='0.03'/>

<!-- header -->
<text x='{PAD_X}' y='26' font-family='{FONT}' font-size='13' fill='{ACCENT}'>
SIGNAL // 365D
</text>

<text x='{PAD_X}' y='42' font-family='{FONT}' font-size='10' fill='{MUTED}'>
{total} contributions · peak/day {peak}
</text>

<!-- sweep -->
<rect x='0' y='0' width='{WIDTH}' height='2' fill='{ACCENT}' opacity='0.4'>
<animate attributeName='y' from='0' to='{HEIGHT}' dur='7s' repeatCount='indefinite'/>
</rect>

<!-- histogram -->
{"".join(f"<rect x='{x:.2f}' y='{PLOT_BOTTOM-h:.2f}' width='2' height='{h:.2f}' fill='{ACCENT}' opacity='0.15'/>" for x,h in hist)}

<!-- spectrum spikes -->
{"".join(f"<line x1='{x:.2f}' y1='{PLOT_TOP}' x2='{x:.2f}' y2='{PLOT_TOP+h:.2f}' stroke='{ACCENT_LIGHT}' stroke-width='1' opacity='0.4'/>" for x,h in spikes)}

<!-- interference bursts -->
{"".join(f"<circle cx='{x:.2f}' cy='{PLOT_TOP+40}' r='3' fill='{ACCENT_LIGHT}' opacity='0.7'><animate attributeName='r' values='3;12;3' dur='1.6s' repeatCount='indefinite'/></circle>" for x in bursts)}

<!-- ghost signal -->
<path d='{path}' stroke='{ACCENT}' stroke-width='5' opacity='0.07' fill='none'/>

<!-- glow density -->
<path d='{path} L {WIDTH-PAD_X},{PLOT_BOTTOM} L {PAD_X},{PLOT_BOTTOM} Z'
fill='{ACCENT}' opacity='0.08' filter='url(#glow)'/>

<!-- main signal -->
<path d='{path}' stroke='url(#signalGrad)' stroke-width='2.5' fill='none' filter='url(#glow)'/>

<!-- pulse -->
<circle cx='{pts[-1][0]:.2f}' cy='{pts[-1][1]:.2f}' r='5' fill='{ACCENT_LIGHT}'>
<animate attributeName='r' values='4;9;4' dur='2s' repeatCount='indefinite'/>
</circle>

</svg>
"""

    Path(os.path.dirname(OUT_PATH) or ".").mkdir(parents=True, exist_ok=True)

    with open(OUT_PATH,"w",encoding="utf-8") as f:
        f.write(svg)

    print("Advanced cinematic telemetry generated →", OUT_PATH)

if __name__ == "__main__":
    main()
