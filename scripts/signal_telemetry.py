import os, json, datetime, urllib.request, urllib.parse, re

USER = os.environ.get("GH_USER", os.environ.get("GITHUB_ACTOR", ""))
TOKEN = os.environ.get("GH_TOKEN", "")
OUT_PATH = os.environ.get("OUT_PATH", "assets/signal_barcode.svg")

# ------------------------
# Helpers
# ------------------------

def iso(dt: datetime.datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def compute_window(days: int, tz_offset_minutes: int):
    # Window is [from_dt, to_dt) in local midnight boundaries, then converted to UTC datetimes.
    # to_dt is next local midnight so "today" is included.
    now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    tz = datetime.timezone(datetime.timedelta(minutes=tz_offset_minutes))
    now_local = now_utc.astimezone(tz)

    # Align to local midnight boundaries
    today_local_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    from_local = today_local_midnight - datetime.timedelta(days=days - 1)
    to_local = today_local_midnight + datetime.timedelta(days=1)

    from_dt = from_local.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    to_dt = to_local.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return from_dt, to_dt


def fetch_contrib_counts(user: str, from_date: str, to_date: str):
    """Fetch daily contribution counts from GitHub's public contributions endpoint.

    This matches the GitHub profile UI (including 'private contributions' if the user has enabled
    'Include private contributions on my profile'). No authentication required.
    """
    u = urllib.parse.quote(user, safe="")
    url = f"https://github.com/users/{u}/contributions?from={from_date}&to={to_date}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "readme-telemetry/1.0")
    req.add_header("Accept", "text/html,application/xhtml+xml")
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")

    pairs = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-count="(\d+)"', html)
    if not pairs:
        # Some responses may reorder attributes; try the inverse.
        inv = re.findall(r'data-count="(\d+)"[^>]*data-date="(\d{4}-\d{2}-\d{2})"', html)
        pairs = [(d, c) for c, d in inv]

    if not pairs:
        raise SystemExit("Could not parse contributions HTML (GitHub markup changed or blocked).")

    by_date = {}
    for d, c in pairs:
        by_date[d] = int(c)
    return by_date


# ------------------------
# SVG builder
# ------------------------

def build_svg(stats: dict) -> str:
    # Minimal barcode-style telemetry with text overlay
    days = stats["days"]
    total = stats["total"]
    peak = stats["peak"]
    cap_p85 = stats["cap_p85"]
    mode = stats["mode"]
    best_streak = stats["best_streak"]
    last7 = stats["last7"]
    last30 = stats["last30"]
    avg = stats["avg"]
    date_label = stats["date_label"]

    W = 1200
    H = 320
    margin = 40
    bar_h = 90
    bar_y = 130
    bar_w = (W - 2 * margin) / len(days)
    grid_y1 = bar_y - 10
    grid_y2 = bar_y + bar_h + 10

    bg = "#0b0f14"
    fg = "#d9e2ec"
    dim = "#9fb3c8"
    neon = "#20c997"
    grid = "#12202e"
    stroke = "#1c2d3e"

    # Build bars
    bars = []
    for i, d in enumerate(days):
        x = margin + i * bar_w
        v = d["count"]
        # robust scaling using p85 cap to avoid one spike flattening everything
        scaled = 0.0 if cap_p85 <= 0 else clamp(v / cap_p85, 0.0, 1.0)
        h = scaled * bar_h
        y = bar_y + (bar_h - h)
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" rx="0.8" fill="{neon}" opacity="0.90" />'
        )

    # Subtle grid
    grid_lines = []
    for k in range(0, 13):
        gx = margin + k * ((W - 2 * margin) / 12.0)
        grid_lines.append(f'<line x1="{gx:.2f}" y1="{grid_y1}" x2="{gx:.2f}" y2="{grid_y2}" stroke="{grid}" stroke-width="1" opacity="0.55" />')
    for k in range(0, 5):
        gy = grid_y1 + k * ((grid_y2 - grid_y1) / 4.0)
        grid_lines.append(f'<line x1="{margin}" y1="{gy:.2f}" x2="{W - margin}" y2="{gy:.2f}" stroke="{grid}" stroke-width="1" opacity="0.35" />')

    # Telemetry labels
    header_left = f"SIGNAL  //  365D"
    header_mid = f"{total} contributions  •  peak/day {peak}  •  cap@p85 {cap_p85}  •  mode {mode}"
    header_right = date_label

    panel = (
        f'<rect x="{margin}" y="{70}" width="{W - 2*margin}" height="{H - 100}" rx="16" fill="none" stroke="{stroke}" stroke-width="1.2" opacity="0.9" />'
    )

    tooltip = (
        f'<g opacity="0.95">'
        f'<rect x="{W-360}" y="{150}" width="300" height="72" rx="12" fill="#0d141c" stroke="{stroke}" stroke-width="1.0" />'
        f'<text x="{W-340}" y="{178}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="14" fill="{fg}">'
        f'Streak {stats["current_streak"]}d  •  Best {best_streak}d</text>'
        f'<text x="{W-340}" y="{200}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="13" fill="{dim}">'
        f'Last 7d {last7}  •  30d {last30}</text>'
        f'<text x="{W-340}" y="{220}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="13" fill="{dim}">'
        f'Avg {avg:.2f}/d</text>'
        f'</g>'
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{neon}" stop-opacity="0.0" />
      <stop offset="50%" stop-color="{neon}" stop-opacity="0.25" />
      <stop offset="100%" stop-color="{neon}" stop-opacity="0.0" />
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{bg}" />

  {panel}

  <text x="{margin}" y="110" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
        font-size="18" fill="{neon}">{header_left}</text>

  <text x="{margin}" y="135" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
        font-size="12" fill="{dim}">{header_mid}</text>

  <text x="{W - margin}" y="110" text-anchor="end"
        font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
        font-size="12" fill="{dim}">{header_right}</text>

  {''.join(grid_lines)}

  <rect x="{margin}" y="{bar_y-10}" width="{W - 2*margin}" height="{bar_h+20}" fill="url(#fade)" opacity="0.55" />

  {''.join(bars)}

  {tooltip}

  <text x="{W/2}" y="{H-30}" text-anchor="middle"
        font-family="system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, sans-serif"
        font-size="14" fill="{fg}">
    Signal over time: sustained development, consistent iteration
  </text>
</svg>'''
    return svg


def compute_streak(days):
    # days: list of dict(date, count) sorted
    best = 0
    cur = 0
    for d in days:
        if d["count"] > 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    # current streak from the end
    cur_end = 0
    for d in reversed(days):
        if d["count"] > 0:
            cur_end += 1
        else:
            break
    return best, cur_end


def percentile(values, p: float) -> int:
    if not values:
        return 0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return int(round(xs[f] + (xs[c] - xs[f]) * (k - f)))


def mode_int(values):
    if not values:
        return 0
    freq = {}
    for v in values:
        freq[v] = freq.get(v, 0) + 1
    # prefer non-zero if tied
    items = sorted(freq.items(), key=lambda kv: (kv[1], kv[0] != 0, kv[0]))
    return items[-1][0]


def main():
    if not USER:
        raise SystemExit("GH_USER not set (or GITHUB_ACTOR missing).")

    tz_offset = int(os.environ.get("TZ_OFFSET_MINUTES", "0"))
    from_dt, to_dt = compute_window(365, tz_offset)

    # Pull the exact same daily counts GitHub renders on your profile page.
    # Note: 'Include private contributions' is controlled by your GitHub profile setting.
    from_date = from_dt.date().isoformat()
    to_date = (to_dt - datetime.timedelta(days=1)).date().isoformat()
    by_date = fetch_contrib_counts(USER, from_date, to_date)

    # Build ordered day list
    days = []
    cursor = from_dt.date()
    end = (to_dt - datetime.timedelta(days=1)).date()
    while cursor <= end:
        ds = cursor.isoformat()
        days.append({"date": ds, "count": int(by_date.get(ds, 0))})
        cursor += datetime.timedelta(days=1)

    counts = [d["count"] for d in days]
    total = sum(counts)
    peak = max(counts) if counts else 0
    cap_p85 = percentile(counts, 85.0)
    mode = mode_int(counts)
    best_streak, current_streak = compute_streak(days)

    last7 = sum(d["count"] for d in days[-7:]) if len(days) >= 7 else total
    last30 = sum(d["count"] for d in days[-30:]) if len(days) >= 30 else total
    avg = (total / len(days)) if days else 0.0

    date_label = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    stats = {
        "days": days,
        "total": total,
        "peak": peak,
        "cap_p85": cap_p85,
        "mode": mode,
        "best_streak": best_streak,
        "current_streak": current_streak,
        "last7": last7,
        "last30": last30,
        "avg": avg,
        "date_label": date_label,
    }

    svg = build_svg(stats)

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"[signal_telemetry] wrote {OUT_PATH}  total={total}  peak={peak}  cap_p85={cap_p85}")


if __name__ == "__main__":
    main()
