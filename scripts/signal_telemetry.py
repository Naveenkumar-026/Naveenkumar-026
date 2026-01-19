import os
import json
import datetime
import urllib.request

# ------------------------
# Config
# ------------------------
USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_ACTOR") or ""
TOKEN = os.environ.get("GH_TOKEN") or ""
OUT_PATH = os.environ.get("OUT_PATH", "assets/signal_barcode.svg")

TZ_OFFSET_MINUTES = int(os.environ.get("TZ_OFFSET_MINUTES", "330"))
DAYS = int(os.environ.get("DAYS", "365"))

# If INCLUDE_PRIVATE=0, we still match GitHub's "last year" total as shown on your profile.
# We only hide the private breakdown text.
INCLUDE_PRIVATE = os.environ.get("INCLUDE_PRIVATE", "0").strip().lower() not in ("0", "false", "no", "off")

# ------------------------
# Theme
# ------------------------
BG = "#0D1117"
FG = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"
GRID = "#1F2937"
PANEL_BG = "#000000"      # pure black panel
PANEL_STROKE = "#1F2937"  # dark neutral border (no blue)

WIDTH = 980
HEIGHT = 220
PAD_X = 24
PLOT_TOP = 86
PLOT_H = 104
PLOT_BOTTOM = PLOT_TOP + PLOT_H


# ------------------------
# Helpers
# ------------------------
def iso_z(dt_utc_naive: datetime.datetime) -> str:
    """Naive UTC datetime -> ISO8601 with Z."""
    return dt_utc_naive.replace(microsecond=0).isoformat() + "Z"


def gh_api(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise SystemExit("GH_TOKEN missing. Set GH_TOKEN env or Actions secret.")
    req = urllib.request.Request("https://api.github.com/graphql", method="POST")
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    with urllib.request.urlopen(req, data=payload, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "errors" in data:
        raise SystemExit(f"GitHub GraphQL errors: {data['errors']}")
    return data["data"]


def compute_rolling_window(days: int, tz_offset_minutes: int):
    """
    Rolling local-date window: [start_date .. end_date] inclusive (days long).
    Query window for GraphQL: [from_dt_utc, to_dt_utc) aligned to local midnights.
    """
    now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    local_now = now_utc + datetime.timedelta(minutes=tz_offset_minutes)

    end_date_local = local_now.date()  # include "today" in your local time
    start_date_local = end_date_local - datetime.timedelta(days=days - 1)

    local_from = datetime.datetime.combine(start_date_local, datetime.time(0, 0, 0))
    local_to = datetime.datetime.combine(end_date_local + datetime.timedelta(days=1), datetime.time(0, 0, 0))

    from_dt_utc = (local_from - datetime.timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)
    to_dt_utc = (local_to - datetime.timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)

    return from_dt_utc, to_dt_utc, start_date_local, end_date_local


def percentile(values, p):
    if not values:
        return 1
    values = sorted(values)
    k = (len(values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return d0 + d1


def moving_avg(series, window=11):
    if window <= 1:
        return series[:]
    half = window // 2
    out = []
    for i in range(len(series)):
        lo = max(0, i - half)
        hi = min(len(series), i + half + 1)
        out.append(sum(series[lo:hi]) / (hi - lo))
    return out


def svg_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))


# ------------------------
# Main
# ------------------------
def main():
    if not USER:
        raise SystemExit("GH_USER is empty. Set GH_USER env (usually github.repository_owner).")

    from_dt, to_dt, start_date, end_date = compute_rolling_window(DAYS, TZ_OFFSET_MINUTES)

    query = """
    query($user:String!, $from:DateTime!, $to:DateTime!) {
      user(login: $user) {
        contributionsCollection(from: $from, to: $to) {
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
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

    coll = data["user"]["contributionsCollection"]
    cal = coll["contributionCalendar"]
    restricted_raw = int(coll.get("restrictedContributionsCount", 0) or 0)
    total_calendar = int(cal.get("totalContributions", 0) or 0)

    # Build date -> count map
    by_date = {}
    for w in cal.get("weeks", []):
        for d in w.get("contributionDays", []):
            by_date[d["date"]] = int(d.get("contributionCount", 0) or 0)

    # Build rolling day list (local)
    counts = []
    cur = start_date
    while cur <= end_date:
        counts.append(by_date.get(cur.isoformat(), 0))
        cur += datetime.timedelta(days=1)

    # Sanity
    if len(counts) != DAYS:
        raise SystemExit(f"Window error: expected {DAYS} days, got {len(counts)} days.")

    total_visible = sum(counts)

    # Use GitHub's calendar total as the headline number (matches the UI "in the last year")
    total = total_calendar if total_calendar else total_visible

    raw_max = max(counts) if counts else 1
    nonzero = [v for v in counts if v > 0]
    cap_p85 = percentile(nonzero, 85) if nonzero else 1
    scale_max = max(1, int(round(cap_p85)))

    ma = moving_avg([min(v, scale_max) for v in counts], window=11)

    # Streak + rollups
    cur_streak = 0
    best = 0
    last_7 = sum(counts[-7:])
    last_30 = sum(counts[-30:])
    for v in counts:
        if v > 0:
            cur_streak += 1
            best = max(best, cur_streak)
        else:
            cur_streak = 0
    streak = cur_streak

    meta = f"{total} contributions"
    if (not INCLUDE_PRIVATE) and restricted_raw > 0:
        meta += " (private hidden)"
    meta += f" · peak/day {raw_max} · cap@p85 {scale_max} · mode BARCODE"

    now_label = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    tooltip_lines = [
        f"Streak {streak}d  ·  Best {best}d",
        f"Last 7d {last_7}  ·  30d {last_30}",
        f"Avg {total / DAYS:.2f}/d",
    ]

    sx = (WIDTH - 2 * PAD_X) / (DAYS - 1)
    bar_w = max(1.0, sx * 0.75)

    pts = []
    for i, v in enumerate(ma):
        x = PAD_X + i * sx
        y = PLOT_BOTTOM - (min(v, scale_max) / scale_max) * (PLOT_H - 6)
        pts.append((x, y))

    path_d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f} " + " ".join(
        f"L {pts[i][0]:.2f} {pts[i][1]:.2f}" for i in range(1, len(pts))
    )

    tooltip_x = WIDTH - PAD_X - 240
    tooltip_y = PLOT_TOP + 22

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <rect width="100%" height="100%" fill="{BG}"/>
  <line x1="{PAD_X}" y1="{PLOT_BOTTOM}" x2="{WIDTH-PAD_X}" y2="{PLOT_BOTTOM}" stroke="{GRID}" stroke-width="1"/>
  <line x1="{PAD_X}" y1="{PLOT_TOP}" x2="{WIDTH-PAD_X}" y2="{PLOT_TOP}" stroke="{GRID}" stroke-width="1" opacity="0.6"/>

  <text x="{PAD_X}" y="34" fill="{FG}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace" font-size="12" letter-spacing="0.5">SIGNAL // 365D</text>
  <text x="{PAD_X}" y="54" fill="{MUTED}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace" font-size="11">{svg_escape(meta)}</text>
  <text x="{WIDTH-PAD_X}" y="34" fill="{MUTED}" text-anchor="end" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace" font-size="11">{now_label}</text>

  <path d="{path_d}" fill="none" stroke="{ACCENT}" stroke-width="2.2" opacity="0.9"/>

  <!-- Bars -->
'''
    for i, v in enumerate(counts):
        if v <= 0:
            continue
        x = PAD_X + i * sx
        h = (min(v, scale_max) / scale_max) * (PLOT_H - 6)
        y = PLOT_BOTTOM - h
        svg += f'  <rect x="{x - bar_w/2:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{ACCENT}" opacity="0.18"/>\n'

    svg += f'''
  <g>
    <rect x="{tooltip_x}" y="{tooltip_y}" width="230" height="64" rx="10" fill="{PANEL_BG}" stroke="{PANEL_STROKE}" opacity="1"/>
    <text x="{tooltip_x+14}" y="{tooltip_y+22}" fill="{FG}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace" font-size="11">
      <tspan x="{tooltip_x+14}" dy="0">{svg_escape(tooltip_lines[0])}</tspan>
      <tspan x="{tooltip_x+14}" dy="16">{svg_escape(tooltip_lines[1])}</tspan>
      <tspan x="{tooltip_x+14}" dy="16" fill="{MUTED}">{svg_escape(tooltip_lines[2])}</tspan>
    </text>
  </g>
</svg>
'''

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    # Logs: compare these directly to the GitHub UI when debugging
    print(f"[signal] user={USER} window={start_date}..{end_date} total_calendar={total_calendar} total_visible={total_visible} restricted={restricted_raw} include_private={INCLUDE_PRIVATE}")
    print(f"[signal] wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
