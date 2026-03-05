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
# Theme — red x black (matches eye.gif color signature)
# ------------------------
BG          = "#030000"    # near-black with faint red tint
PANEL_BG    = "#000000"    # pure black
ACCENT      = "#ef4444"    # vivid red  — plot line, bars, HUD chrome
ACCENT_LT   = "#fca5a5"    # light red  — tip glow
GRID        = "#2d1010"    # dark red-tinted rule lines
TEXT        = "#e2e8f0"    # near-white
MUTED       = "#6b7280"    # gray
FONT        = "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Courier New', monospace"

WIDTH       = 980
HEIGHT      = 240
PAD_X       = 28
HEADER_H    = 62
PLOT_TOP    = HEADER_H + 6
PLOT_H      = 118
PLOT_BOTTOM = PLOT_TOP + PLOT_H
BK          = 18           # corner bracket arm length


# ------------------------
# Helpers  (unchanged from original)
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
# Main  (data logic unchanged — only SVG rendering restyled)
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

    # Area fill (close shape below baseline)
    area_d = (path_d
              + f" L {pts[-1][0]:.2f} {PLOT_BOTTOM:.2f}"
              + f" L {pts[0][0]:.2f}  {PLOT_BOTTOM:.2f} Z")

    tooltip_x = WIDTH - PAD_X - 244
    tooltip_y = PLOT_TOP + 16

    # ── SVG ──────────────────────────────────────────────────────────────────
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>

  <!-- Background gradient -->
  <linearGradient id="bgGrad" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0%"   stop-color="{BG}"/>
    <stop offset="100%" stop-color="#000000"/>
  </linearGradient>

  <!-- Subtle red-tinted grid -->
  <pattern id="gridPat" width="26" height="26" patternUnits="userSpaceOnUse">
    <path d="M 26 0 L 0 0 0 26" fill="none"
          stroke="{ACCENT}" stroke-width="0.13" opacity="0.14"/>
  </pattern>

  <!-- Area fill gradient under the line -->
  <linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0%"   stop-color="{ACCENT}" stop-opacity="0.16"/>
    <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0.00"/>
  </linearGradient>

  <!-- Plot line red glow -->
  <filter id="lineGlow" x="-10%" y="-100%" width="120%" height="300%">
    <feGaussianBlur stdDeviation="3.5" result="b"/>
    <feColorMatrix in="b" type="matrix"
      values="1.2 0 0 0 0
              0   0 0 0 0
              0   0 0 0 0
              0   0 0 1 0" result="c"/>
    <feMerge>
      <feMergeNode in="c"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>

  <!-- Tooltip shadow -->
  <filter id="ttShadow" x="-30%" y="-30%" width="160%" height="160%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="blur"/>
    <feOffset dx="0" dy="2" result="off"/>
    <feComponentTransfer><feFuncA type="linear" slope="0.45"/></feComponentTransfer>
    <feMerge><feMergeNode in="off"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>

  <!-- Tooltip border glow -->
  <filter id="ttGlow" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="3.5" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>

  <!-- Canvas clip -->
  <clipPath id="cClip"><rect width="{WIDTH}" height="{HEIGHT}"/></clipPath>

  <style>
    @keyframes scanMove {{
      0%   {{ transform: translateY(-4px); opacity: 0; }}
      6%   {{ opacity: 0.50; }}
      94%  {{ opacity: 0.14; }}
      100% {{ transform: translateY({HEIGHT + 4}px); opacity: 0; }}
    }}
    @keyframes borderPulse {{
      0%, 100% {{ opacity: 0.35; }}
      50%      {{ opacity: 0.65; }}
    }}
    @keyframes dotBlink {{
      0%, 100% {{ opacity: 1; }}
      50%      {{ opacity: 0.15; }}
    }}
    .scanLine    {{ animation: scanMove    9s linear     infinite 1s; }}
    .outerBorder {{ animation: borderPulse 4s ease-in-out infinite; }}
    .statusDot   {{ animation: dotBlink    2s step-end   infinite; }}
  </style>

</defs>

<g clip-path="url(#cClip)">

  <!-- Base fill + grid -->
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bgGrad)"/>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#gridPat)"/>

  <!-- Left accent stripe -->
  <rect x="0" y="0" width="3" height="{HEIGHT}" fill="{ACCENT}" opacity="0.28"/>

  <!-- Outer border (animated pulse) -->
  <rect class="outerBorder" x="0.5" y="0.5" width="{WIDTH-1}" height="{HEIGHT-1}"
        fill="none" stroke="{ACCENT}" stroke-width="0.8"/>

  <!-- Corner brackets — TL -->
  <path d="M3,{BK+3} L3,3 L{BK+3},3"
        fill="none" stroke="{ACCENT}" stroke-width="2.5" opacity="0.9"/>
  <!-- TR -->
  <path d="M{WIDTH-BK-3},3 L{WIDTH-3},3 L{WIDTH-3},{BK+3}"
        fill="none" stroke="{ACCENT}" stroke-width="2.5" opacity="0.9"/>
  <!-- BL -->
  <path d="M3,{HEIGHT-BK-3} L3,{HEIGHT-3} L{BK+3},{HEIGHT-3}"
        fill="none" stroke="{ACCENT}" stroke-width="2.5" opacity="0.9"/>
  <!-- BR -->
  <path d="M{WIDTH-BK-3},{HEIGHT-3} L{WIDTH-3},{HEIGHT-3} L{WIDTH-3},{HEIGHT-BK-3}"
        fill="none" stroke="{ACCENT}" stroke-width="2.5" opacity="0.9"/>

  <!-- Animated scan line -->
  <rect class="scanLine" x="0" y="0" width="{WIDTH}" height="1.5"
        fill="{ACCENT}" opacity="0.45"/>

  <!-- Header bar -->
  <rect x="1" y="1" width="{WIDTH-2}" height="{HEADER_H-10}"
        fill="{ACCENT}" fill-opacity="0.05"/>
  <line x1="1" y1="{HEADER_H-10}" x2="{WIDTH-1}" y2="{HEADER_H-10}"
        stroke="{ACCENT}" stroke-width="0.5" opacity="0.28"/>

  <!-- Header text -->
  <text x="{PAD_X}" y="26"
        font-family="{FONT}" font-size="12" font-weight="bold"
        fill="{ACCENT}" opacity="0.92" letter-spacing="0.6"
        >SIGNAL // 365D</text>

  <text x="{WIDTH - PAD_X}" y="26" text-anchor="end"
        font-family="{FONT}" font-size="10.5" fill="{MUTED}"
        >{svg_escape(now_label)}</text>

  <text x="{PAD_X}" y="{HEADER_H - 16}"
        font-family="{FONT}" font-size="10" fill="{MUTED}"
        >{svg_escape(meta)}</text>

  <!-- Status dot -->
  <circle class="statusDot" cx="{WIDTH - PAD_X - 8}" cy="{HEADER_H // 2 - 6}"
          r="4" fill="{ACCENT}"/>

  <!-- Plot rules -->
  <line x1="{PAD_X}" y1="{PLOT_BOTTOM}" x2="{WIDTH-PAD_X}" y2="{PLOT_BOTTOM}"
        stroke="{GRID}" stroke-width="1.0" opacity="0.9"/>
  <line x1="{PAD_X}" y1="{PLOT_TOP}" x2="{WIDTH-PAD_X}" y2="{PLOT_TOP}"
        stroke="{GRID}" stroke-width="0.6" opacity="0.5"/>
  <line x1="{PAD_X}" y1="{(PLOT_TOP + PLOT_BOTTOM)//2}" x2="{WIDTH-PAD_X}" y2="{(PLOT_TOP + PLOT_BOTTOM)//2}"
        stroke="{GRID}" stroke-width="0.4" opacity="0.3"/>

'''

    # Bars
    for i, v in enumerate(counts):
        if v <= 0:
            continue
        x = PAD_X + i * sx
        h = (min(v, scale_max) / scale_max) * (PLOT_H - 6)
        y = PLOT_BOTTOM - h
        svg += f'  <rect x="{x - bar_w/2:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{ACCENT}" opacity="0.18"/>\n'

    svg += f'''
  <!-- Area fill under the line -->
  <path d="{area_d}" fill="url(#areaGrad)"/>

  <!-- Plot line with red glow -->
  <path d="{path_d}" fill="none" stroke="{ACCENT}"
        stroke-width="2.2" opacity="0.95" filter="url(#lineGlow)"/>

  <!-- Bright tip dot at the most recent point -->
  <circle cx="{pts[-1][0]:.2f}" cy="{pts[-1][1]:.2f}" r="4.5"
          fill="{ACCENT_LT}" filter="url(#lineGlow)"/>
  <circle cx="{pts[-1][0]:.2f}" cy="{pts[-1][1]:.2f}" r="2"
          fill="#ffffff" opacity="0.9"/>

  <!-- Tooltip shadow layer -->
  <rect x="{tooltip_x}" y="{tooltip_y}" width="232" height="68" rx="8"
        fill="{PANEL_BG}" opacity="0.92" filter="url(#ttShadow)"/>

  <!-- Tooltip glow stroke -->
  <rect x="{tooltip_x}" y="{tooltip_y}" width="232" height="68" rx="8"
        fill="none" stroke="{ACCENT}" stroke-width="1.2" opacity="0.20"
        filter="url(#ttGlow)"/>

  <!-- Tooltip solid fill + border -->
  <rect x="{tooltip_x}" y="{tooltip_y}" width="232" height="68" rx="8"
        fill="{PANEL_BG}" stroke="{ACCENT}" stroke-width="0.8" stroke-opacity="0.40" opacity="0.98"/>

  <!-- Tooltip left accent bar -->
  <rect x="{tooltip_x}" y="{tooltip_y + 8}" width="2.5" height="52" rx="1.5"
        fill="{ACCENT}" opacity="0.55"/>

  <!-- Tooltip text -->
  <text x="{tooltip_x + 14}" y="{tooltip_y + 22}"
        font-family="{FONT}" font-size="11" fill="{TEXT}">
    <tspan x="{tooltip_x + 14}" dy="0">{svg_escape(tooltip_lines[0])}</tspan>
    <tspan x="{tooltip_x + 14}" dy="17" fill="{TEXT}" opacity="0.85">{svg_escape(tooltip_lines[1])}</tspan>
    <tspan x="{tooltip_x + 14}" dy="16" fill="{MUTED}">{svg_escape(tooltip_lines[2])}</tspan>
  </text>

  <!-- Footer rule -->
  <line x1="{PAD_X}" y1="{HEIGHT - 18}" x2="{WIDTH - PAD_X}" y2="{HEIGHT - 18}"
        stroke="{ACCENT}" stroke-width="0.4" opacity="0.18"/>

  <text x="{PAD_X}" y="{HEIGHT - 6}"
        font-family="{FONT}" font-size="8.5" fill="{ACCENT}" opacity="0.22"
        >{svg_escape(start_date.isoformat())} → {svg_escape(end_date.isoformat())} · {DAYS}d WINDOW · {svg_escape(USER)}</text>

  <text x="{WIDTH - PAD_X}" y="{HEIGHT - 6}" text-anchor="end"
        font-family="{FONT}" font-size="8.5" fill="{ACCENT}" opacity="0.20"
        >Build durable systems. Release deliberately.</text>

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
