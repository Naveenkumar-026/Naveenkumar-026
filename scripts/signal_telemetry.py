#!/usr/bin/env python3
"""
signal_telemetry.py — SIGNAL // 365D contribution barcode
Generates assets/signal_barcode.svg

Aesthetic: red sine wave on deep black — matches the eye.gif color signature.
  · Background  : #030000  (near-black with faint red tint)
  · Accent      : #ef4444  (vivid red — plot line + bars)
  · Hot tip     : #fca5a5  (light red for glow tip)
  · Grid        : #1a0a0a  (very dark red-tinted grid)
  · Text        : #e2e8f0  (near-white)
  · Muted       : #6b7280  (gray)
  · Corner/HUD  : #ef4444  (matches plot accent)

ENV:
  GH_USER              GitHub username
  GH_TOKEN             Personal access token (read:user scope)
  OUT_PATH             Output SVG path  (default: assets/signal_barcode.svg)
  TZ_OFFSET_MINUTES    Your UTC offset in minutes (default: 330 → IST)
  DAYS                 Rolling window length    (default: 365)
  INCLUDE_PRIVATE      Show private count       (default: 0)
"""

import os
import json
import datetime
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────
USER              = os.environ.get("GH_USER") or os.environ.get("GITHUB_ACTOR") or ""
TOKEN             = os.environ.get("GH_TOKEN") or ""
OUT_PATH          = os.environ.get("OUT_PATH", "assets/signal_barcode.svg")
TZ_OFFSET_MINUTES = int(os.environ.get("TZ_OFFSET_MINUTES", "330"))
DAYS              = int(os.environ.get("DAYS", "365"))
INCLUDE_PRIVATE   = os.environ.get("INCLUDE_PRIVATE", "0").strip().lower() not in (
    "0", "false", "no", "off"
)

# ── Palette — red × black ─────────────────────────────────────────────────────
BG           = "#030000"    # near-black, faint red tint
PANEL_BG     = "#000000"    # pure black for tooltip/cards
GRID_LINE    = "#1a0a0a"    # very dark red-tinted grid
GRID_RULE    = "#2d1010"    # slightly brighter rule lines
ACCENT       = "#ef4444"    # vivid red  — main plot + bars
ACCENT_LT    = "#fca5a5"    # light red  — glow tip highlight
ACCENT_DIM   = "#7f1d1d"    # deep red   — bar fill (semi-transparent)
TEXT         = "#e2e8f0"    # near-white
MUTED        = "#6b7280"    # gray
STROKE_HUD   = "#ef4444"    # corner brackets, border
TOOLTIP_BDR  = "#ef4444"    # tooltip stroke

FONT         = ("JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, "
                "Monaco, Consolas, 'Courier New', monospace")

# ── Canvas ────────────────────────────────────────────────────────────────────
W          = 980
H          = 240
PAD_X      = 28
HEADER_H   = 64        # top area for labels
PLOT_TOP   = HEADER_H + 6
PLOT_H     = 118
PLOT_BOT   = PLOT_TOP + PLOT_H
BK         = 18        # corner bracket arm length


# ── Helpers ───────────────────────────────────────────────────────────────────
def iso_z(dt_utc: datetime.datetime) -> str:
    return dt_utc.replace(microsecond=0).isoformat() + "Z"


def gh_api(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise SystemExit("GH_TOKEN missing.")
    req = urllib.request.Request("https://api.github.com/graphql", method="POST")
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    body = json.dumps({"query": query, "variables": variables}).encode()
    with urllib.request.urlopen(req, data=body, timeout=30) as r:
        data = json.loads(r.read().decode())
    if "errors" in data:
        raise SystemExit(f"GraphQL errors: {data['errors']}")
    return data["data"]


def compute_window(days: int, tz_offset_minutes: int):
    now_utc   = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    local_now = now_utc + datetime.timedelta(minutes=tz_offset_minutes)
    end_local = local_now.date()
    start_local = end_local - datetime.timedelta(days=days - 1)

    local_from = datetime.datetime.combine(start_local, datetime.time(0, 0))
    local_to   = datetime.datetime.combine(
        end_local + datetime.timedelta(days=1), datetime.time(0, 0)
    )
    from_utc = (local_from - datetime.timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)
    to_utc   = (local_to   - datetime.timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)
    return from_utc, to_utc, start_local, end_local


def percentile(values, p):
    if not values:
        return 1
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] if f == c else s[f] * (c - k) + s[c] * (k - f)


def moving_avg(series, window=11):
    half = window // 2
    return [
        sum(series[max(0, i - half): min(len(series), i + half + 1)])
        / len(series[max(0, i - half): min(len(series), i + half + 1)])
        for i in range(len(series))
    ]


def xe(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


# ── SVG builder ───────────────────────────────────────────────────────────────
def build_svg(
    counts, scale_max, raw_max, total,
    streak, best, last_7, last_30,
    restricted_raw, start_date, end_date,
    user, now_label, meta
) -> str:

    sx    = (W - 2 * PAD_X) / max(DAYS - 1, 1)
    bar_w = max(1.0, sx * 0.72)

    # Smooth curve points
    smoothed = moving_avg([min(v, scale_max) for v in counts], window=11)
    pts = [
        (PAD_X + i * sx,
         PLOT_BOT - (min(v, scale_max) / scale_max) * (PLOT_H - 8))
        for i, v in enumerate(smoothed)
    ]

    # SVG path (polyline via L commands)
    path_d = (f"M {pts[0][0]:.2f} {pts[0][1]:.2f} "
              + " ".join(f"L {x:.2f} {y:.2f}" for x, y in pts[1:]))

    # Area fill path (close below plot)
    area_d = (path_d
              + f" L {pts[-1][0]:.2f} {PLOT_BOT:.2f}"
              + f" L {pts[0][0]:.2f} {PLOT_BOT:.2f} Z")

    # Tooltip position (top-right quadrant)
    tt_w, tt_h = 240, 72
    tt_x = W - PAD_X - tt_w - 4
    tt_y = PLOT_TOP + 14

    tooltip_lines = [
        f"Streak {streak}d  ·  Best {best}d",
        f"Last 7d {last_7}  ·  30d {last_30}",
        f"Avg {total / DAYS:.2f}/d",
    ]

    # ── Open SVG ─────────────────────────────────────────────────────────────
    out = f'''<svg xmlns="http://www.w3.org/2000/svg"
     width="{W}" height="{H}" viewBox="0 0 {W} {H}">

  <defs>

    <!-- Background gradient -->
    <linearGradient id="bgGrad" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="{BG}"/>
      <stop offset="100%" stop-color="#000000"/>
    </linearGradient>

    <!-- Subtle grid pattern -->
    <pattern id="gridPat" width="26" height="26" patternUnits="userSpaceOnUse">
      <path d="M 26 0 L 0 0 0 26" fill="none"
            stroke="{ACCENT}" stroke-width="0.13" opacity="0.14"/>
    </pattern>

    <!-- Area fill gradient (under the line) -->
    <linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"   stop-color="{ACCENT}" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>

    <!-- Plot line glow -->
    <filter id="lineGlow" x="-10%" y="-100%" width="120%" height="300%">
      <feGaussianBlur stdDeviation="3.5" result="b"/>
      <feColorMatrix in="b" type="matrix"
        values="1.2 0   0   0  0
                0   0   0   0  0
                0   0   0   0  0
                0   0   0   1  0" result="c"/>
      <feMerge>
        <feMergeNode in="c"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <!-- Outer border pulse -->
    <filter id="borderGlow">
      <feGaussianBlur stdDeviation="2" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>

    <!-- Tooltip shadow + glow -->
    <filter id="ttShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="5" result="blur"/>
      <feOffset dx="0" dy="2" result="off"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.5"/></feComponentTransfer>
      <feMerge><feMergeNode in="off"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="ttGlow">
      <feGaussianBlur stdDeviation="3" result="g"/>
      <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>

    <!-- Clip to canvas -->
    <clipPath id="cClip"><rect width="{W}" height="{H}"/></clipPath>

    <style>
      @keyframes scanMove {{
        0%   {{ transform: translateY(-4px); opacity: 0; }}
        6%   {{ opacity: 0.50; }}
        94%  {{ opacity: 0.15; }}
        100% {{ transform: translateY({H + 4}px); opacity: 0; }}
      }}
      @keyframes borderPulse {{
        0%, 100% {{ opacity: 0.35; }}
        50%      {{ opacity: 0.65; }}
      }}
      @keyframes dotBlink {{
        0%, 100% {{ opacity: 1;   r: 4; }}
        50%      {{ opacity: 0.2; r: 2.5; }}
      }}
      .scanLine    {{ animation: scanMove    9s linear    infinite 1s; }}
      .outerBorder {{ animation: borderPulse 4s ease-in-out infinite; }}
      .statusDot   {{ animation: dotBlink    2s step-end  infinite; }}
    </style>

  </defs>

  <g clip-path="url(#cClip)">

    <!-- Base fill + grid overlay -->
    <rect width="{W}" height="{H}" fill="url(#bgGrad)"/>
    <rect width="{W}" height="{H}" fill="url(#gridPat)"/>

    <!-- Left accent stripe -->
    <rect x="0" y="0" width="3" height="{H}" fill="{ACCENT}" opacity="0.28"/>

    <!-- Outer border (animated) -->
    <rect class="outerBorder" x="0.5" y="0.5" width="{W-1}" height="{H-1}"
          fill="none" stroke="{STROKE_HUD}" stroke-width="0.8"/>

    <!-- Corner brackets — TL -->
    <path d="M3,{BK+3} L3,3 L{BK+3},3"
          fill="none" stroke="{STROKE_HUD}" stroke-width="2.5" opacity="0.9"/>
    <!-- TR -->
    <path d="M{W-BK-3},3 L{W-3},3 L{W-3},{BK+3}"
          fill="none" stroke="{STROKE_HUD}" stroke-width="2.5" opacity="0.9"/>
    <!-- BL -->
    <path d="M3,{H-BK-3} L3,{H-3} L{BK+3},{H-3}"
          fill="none" stroke="{STROKE_HUD}" stroke-width="2.5" opacity="0.9"/>
    <!-- BR -->
    <path d="M{W-BK-3},{H-3} L{W-3},{H-3} L{W-3},{H-BK-3}"
          fill="none" stroke="{STROKE_HUD}" stroke-width="2.5" opacity="0.9"/>

    <!-- Scan line -->
    <rect class="scanLine" x="0" y="0" width="{W}" height="1.5"
          fill="{ACCENT}" opacity="0.45"/>

    <!-- Header bar -->
    <rect x="1" y="1" width="{W-2}" height="{HEADER_H-8}"
          fill="{ACCENT}" fill-opacity="0.05"/>
    <line x1="1" y1="{HEADER_H-8}" x2="{W-1}" y2="{HEADER_H-8}"
          stroke="{ACCENT}" stroke-width="0.5" opacity="0.30"/>

    <!-- Header text -->
    <text x="{PAD_X}" y="28"
          font-family="{FONT}" font-size="11.5" font-weight="bold"
          fill="{ACCENT}" opacity="0.9" letter-spacing="0.6"
          >SIGNAL // 365D</text>

    <text x="{W//2}" y="28" text-anchor="middle"
          font-family="{FONT}" font-size="11" fill="{TEXT}" opacity="0.50"
          letter-spacing="0.4"
          >{xe(user.upper())} · CONTRIBUTION TELEMETRY</text>

    <text x="{W - PAD_X}" y="28" text-anchor="end"
          font-family="{FONT}" font-size="10" fill="{MUTED}"
          >{xe(now_label)}</text>

    <text x="{PAD_X}" y="{HEADER_H - 14}"
          font-family="{FONT}" font-size="10" fill="{MUTED}"
          >{xe(meta)}</text>

    <!-- Status dot -->
    <circle class="statusDot" cx="{W - PAD_X - 8}" cy="{HEADER_H//2 - 4}"
            r="4" fill="{ACCENT}"/>

    <!-- Plot rules -->
    <line x1="{PAD_X}" y1="{PLOT_BOT}" x2="{W - PAD_X}" y2="{PLOT_BOT}"
          stroke="{GRID_RULE}" stroke-width="1.0" opacity="0.8"/>
    <line x1="{PAD_X}" y1="{PLOT_TOP}" x2="{W - PAD_X}" y2="{PLOT_TOP}"
          stroke="{GRID_RULE}" stroke-width="0.6" opacity="0.5"/>
    <line x1="{PAD_X}" y1="{(PLOT_TOP + PLOT_BOT)//2}" x2="{W - PAD_X}" y2="{(PLOT_TOP + PLOT_BOT)//2}"
          stroke="{GRID_RULE}" stroke-width="0.4" opacity="0.3"/>

'''

    # ── Bars ─────────────────────────────────────────────────────────────────
    for i, v in enumerate(counts):
        if v <= 0:
            continue
        x = PAD_X + i * sx
        h = (min(v, scale_max) / scale_max) * (PLOT_H - 8)
        y = PLOT_BOT - h
        out += (f'    <rect x="{x - bar_w/2:.2f}" y="{y:.2f}" '
                f'width="{bar_w:.2f}" height="{h:.2f}" '
                f'fill="{ACCENT}" opacity="0.18"/>\n')

    # ── Area + Line ───────────────────────────────────────────────────────────
    out += f'''
    <!-- Area fill under the line -->
    <path d="{area_d}" fill="url(#areaGrad)"/>

    <!-- Plot line with red glow -->
    <path d="{path_d}" fill="none" stroke="{ACCENT}"
          stroke-width="2.4" opacity="0.95" filter="url(#lineGlow)"/>

    <!-- Bright tip dot at final point -->
    <circle cx="{pts[-1][0]:.2f}" cy="{pts[-1][1]:.2f}" r="4"
            fill="{ACCENT_LT}" filter="url(#lineGlow)"/>
    <circle cx="{pts[-1][0]:.2f}" cy="{pts[-1][1]:.2f}" r="2"
            fill="#ffffff" opacity="0.9"/>

'''

    # ── Tooltip ───────────────────────────────────────────────────────────────
    out += f'''
    <!-- Tooltip shadow layer -->
    <rect x="{tt_x}" y="{tt_y}" width="{tt_w}" height="{tt_h}" rx="8"
          fill="{PANEL_BG}" opacity="0.9" filter="url(#ttShadow)"/>

    <!-- Tooltip glow stroke -->
    <rect x="{tt_x}" y="{tt_y}" width="{tt_w}" height="{tt_h}" rx="8"
          fill="none" stroke="{TOOLTIP_BDR}" stroke-width="1.2" opacity="0.20"
          filter="url(#ttGlow)"/>

    <!-- Tooltip solid fill + border -->
    <rect x="{tt_x}" y="{tt_y}" width="{tt_w}" height="{tt_h}" rx="8"
          fill="{PANEL_BG}" stroke="{TOOLTIP_BDR}" stroke-width="0.8" opacity="0.97"/>

    <!-- Tooltip left accent bar -->
    <rect x="{tt_x}" y="{tt_y + 8}" width="2.5" height="{tt_h - 16}" rx="1.5"
          fill="{ACCENT}" opacity="0.6"/>

    <!-- Tooltip text -->
    <text font-family="{FONT}" font-size="11" fill="{TEXT}">
      <tspan x="{tt_x + 14}" y="{tt_y + 22}">{xe(tooltip_lines[0])}</tspan>
      <tspan x="{tt_x + 14}" dy="17" fill="{TEXT}" opacity="0.8">{xe(tooltip_lines[1])}</tspan>
      <tspan x="{tt_x + 14}" dy="16" fill="{MUTED}">{xe(tooltip_lines[2])}</tspan>
    </text>

    <!-- Footer rule -->
    <line x1="{PAD_X}" y1="{H - 18}" x2="{W - PAD_X}" y2="{H - 18}"
          stroke="{ACCENT}" stroke-width="0.4" opacity="0.18"/>

    <text x="{PAD_X}" y="{H - 7}"
          font-family="{FONT}" font-size="8.5" fill="{ACCENT}" opacity="0.22"
          >{xe(start_date.isoformat())} → {xe(end_date.isoformat())} · {DAYS}d WINDOW · NAVEENKUMAR-026</text>

    <text x="{W - PAD_X}" y="{H - 7}" text-anchor="end"
          font-family="{FONT}" font-size="8.5" fill="{ACCENT}" opacity="0.20"
          >Build durable systems. Release deliberately.</text>

  </g>
</svg>
'''
    return out


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not USER:
        raise SystemExit("GH_USER is empty. Set GH_USER (usually github.repository_owner).")

    from_dt, to_dt, start_date, end_date = compute_window(DAYS, TZ_OFFSET_MINUTES)

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
        "to":   iso_z(to_dt),
    })

    coll            = data["user"]["contributionsCollection"]
    cal             = coll["contributionCalendar"]
    restricted_raw  = int(coll.get("restrictedContributionsCount", 0) or 0)
    total_calendar  = int(cal.get("totalContributions", 0) or 0)

    by_date = {}
    for w in cal.get("weeks", []):
        for d in w.get("contributionDays", []):
            by_date[d["date"]] = int(d.get("contributionCount", 0) or 0)

    counts, cur = [], start_date
    while cur <= end_date:
        counts.append(by_date.get(cur.isoformat(), 0))
        cur += datetime.timedelta(days=1)

    if len(counts) != DAYS:
        raise SystemExit(f"Window error: expected {DAYS} days, got {len(counts)}")

    total_visible   = sum(counts)
    total           = total_calendar if total_calendar else total_visible
    raw_max         = max(counts) if counts else 1
    nonzero         = [v for v in counts if v > 0]
    cap_p85         = percentile(nonzero, 85) if nonzero else 1
    scale_max       = max(1, int(round(cap_p85)))

    # Streaks
    cur_streak = best = 0
    for v in counts:
        if v > 0:
            cur_streak += 1
            best = max(best, cur_streak)
        else:
            cur_streak = 0

    streak  = cur_streak
    last_7  = sum(counts[-7:])
    last_30 = sum(counts[-30:])

    meta = f"{total} contributions"
    if not INCLUDE_PRIVATE and restricted_raw > 0:
        meta += " (private hidden)"
    meta += f" · peak/day {raw_max} · cap@p85 {scale_max} · mode BARCODE"

    now_label = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    svg = build_svg(
        counts=counts,
        scale_max=scale_max,
        raw_max=raw_max,
        total=total,
        streak=streak,
        best=best,
        last_7=last_7,
        last_30=last_30,
        restricted_raw=restricted_raw,
        start_date=start_date,
        end_date=end_date,
        user=user,
        now_label=now_label,
        meta=meta,
    )

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"[signal_telemetry] user={USER} window={start_date}..{end_date}")
    print(f"[signal_telemetry] total_calendar={total_calendar} visible={total_visible} "
          f"restricted={restricted_raw} include_private={INCLUDE_PRIVATE}")
    print(f"[signal_telemetry] streak={streak}d best={best}d peak={raw_max} cap={scale_max}")
    print(f"[signal_telemetry] wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
