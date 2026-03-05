
import os
import json
import datetime
import urllib.request
from pathlib import Path

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_ACTOR") or ""
TOKEN = os.environ.get("GH_TOKEN") or ""
OUT_PATH = os.environ.get("OUT_PATH", "assets/signal_barcode.svg")

TZ_OFFSET_MINUTES = int(os.environ.get("TZ_OFFSET_MINUTES", "330"))
DAYS = int(os.environ.get("DAYS", "365"))

WIDTH = 980
HEIGHT = 380

PAD_X = 70
RIGHT_PANEL = 200
HEADER_H = 20
CHANNEL_H = 80
PLOT_TOP = HEADER_H + 20

FONT = "JetBrains Mono, monospace"

BG = "#020203"
GRID = "#1b1b1d"
ACCENT = "#ff4040"
TEXT = "#e5e7eb"
MUTED = "#9ca3af"

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

def classify(v, peak):
    if peak == 0:
        return "LOW"
    r = v/peak
    if r > 0.66:
        return "HIGH"
    if r > 0.33:
        return "MED"
    return "LOW"

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

    # --- classification counters
    low = med = high = 0
    for v in counts:
        c = classify(v, peak)
        if c == "LOW":
            low += 1
        elif c == "MED":
            med += 1
        else:
            high += 1

    # --- different telemetry channels
    code_series = counts
    commits_series = [int(v*0.7) for v in counts]
    repos_series = [1 if v>0 else 0 for v in counts]

    channels_data = [code_series, commits_series, repos_series]

    sx = (WIDTH-RIGHT_PANEL-PAD_X*2)/(DAYS-1)

    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{WIDTH}' height='{HEIGHT}'>"
    svg += f"<rect width='100%' height='100%' fill='{BG}'/>"

    labels = ["CODE","COMMITS","REPOS"]

    for ch,data_series in enumerate(channels_data):

        base = PLOT_TOP + ch*CHANNEL_H

        svg += f"<text x='{PAD_X-50}' y='{base+CHANNEL_H/2}' font-family='{FONT}' font-size='10' fill='{MUTED}'>{labels[ch]}</text>"

        svg += f"<line x1='{PAD_X}' y1='{base+CHANNEL_H}' x2='{WIDTH-RIGHT_PANEL}' y2='{base+CHANNEL_H}' stroke='{GRID}'/>"

        for i,v in enumerate(data_series):

            x = PAD_X + i*sx
            h = (v/(peak if peak else 1))*(CHANNEL_H-8)

            svg += f"<rect x='{x:.2f}' y='{base+CHANNEL_H-h:.2f}' width='2' height='{h:.2f}' fill='{ACCENT}'/>"

    # sweep scanner
    svg += f"""
    <g>
      <rect x='{PAD_X}' y='{PLOT_TOP}' width='1' height='{CHANNEL_H*3}' fill='{TEXT}' opacity='0.9'>
        <animate attributeName='x' values='{PAD_X};{WIDTH-RIGHT_PANEL}' dur='5s' repeatCount='indefinite'/>
      </rect>

      <rect x='{PAD_X}' y='{PLOT_TOP}' width='10' height='{CHANNEL_H*3}' fill='{TEXT}' opacity='0.06'>
        <animate attributeName='x' values='{PAD_X};{WIDTH-RIGHT_PANEL}' dur='5s' repeatCount='indefinite'/>
      </rect>
    </g>
    """

    # classification panel
    svg += f"""
    <text x='{WIDTH-180}' y='120' font-family='{FONT}' font-size='10' fill='{TEXT}'>CLASSIFICATION</text>

    <text x='{WIDTH-180}' y='145' font-family='{FONT}' font-size='10' fill='{MUTED}'>LOW : {low}</text>
    <text x='{WIDTH-180}' y='165' font-family='{FONT}' font-size='10' fill='{MUTED}'>MED : {med}</text>
    <text x='{WIDTH-180}' y='185' font-family='{FONT}' font-size='10' fill='{MUTED}'>HIGH: {high}</text>
    """

    # diagnostics
    svg += f"""
    <rect x='{WIDTH-190}' y='220' width='170' height='110' stroke='{GRID}' fill='none'/>
    <text x='{WIDTH-180}' y='240' font-family='{FONT}' font-size='10' fill='{TEXT}'>DIAGNOSTICS</text>

    <text x='{WIDTH-180}' y='260' font-family='{FONT}' font-size='10' fill='{MUTED}'>events:{sum(counts)}</text>
    <text x='{WIDTH-180}' y='280' font-family='{FONT}' font-size='10' fill='{MUTED}'>peak:{peak}</text>
    <text x='{WIDTH-180}' y='300' font-family='{FONT}' font-size='10' fill='{MUTED}'>window:{DAYS}d</text>
    """

    svg += "</svg>"

    Path(os.path.dirname(OUT_PATH) or ".").mkdir(parents=True, exist_ok=True)

    with open(OUT_PATH,"w",encoding="utf-8") as f:
        f.write(svg)

    print("SIGINT console fixed ->", OUT_PATH)

if __name__ == "__main__":
    main()
