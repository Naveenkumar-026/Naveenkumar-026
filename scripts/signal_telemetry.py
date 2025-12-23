import os, json, datetime, urllib.request

USER = os.environ.get("GH_USER", "Naveenkumar-026")
TOKEN = os.environ.get("GH_TOKEN")
OUT_PATH = os.environ.get("OUT_PATH", "assets/signal_barcode.svg")

# Local timezone alignment (IST default)
TZ_OFFSET_MINUTES = int(os.environ.get("TZ_OFFSET_MINUTES", "330"))
DAYS = 365

BG = "#0D1117"
FG = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"
GRID = "#1F2937"

WIDTH = 980
HEIGHT = 220
PAD_X = 24
PLOT_TOP = 86
PLOT_H = 104
PLOT_BOTTOM = PLOT_TOP + PLOT_H


def gh_api(query, variables):
    if not TOKEN:
        raise SystemExit("GH_TOKEN missing. Set GH_TOKEN env or Actions secret.")
    req = urllib.request.Request("https://api.github.com/graphql", method="POST")
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    data = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    with urllib.request.urlopen(req, data=data, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))

    if "errors" in data and data["errors"]:
        raise SystemExit(f"GitHub GraphQL errors: {data['errors']}")
    return data


def percentile(values, p):
    if not values:
        return 0
    xs = sorted(values)
    k = int(round((p / 100.0) * (len(xs) - 1)))
    return xs[max(0, min(len(xs) - 1, k))]


def moving_avg(xs, window=11):
    if not xs:
        return []
    w = max(3, int(window) | 1)  # odd
    half = w // 2
    out = []
    for i in range(len(xs)):
        lo = max(0, i - half)
        hi = min(len(xs), i + half + 1)
        out.append(sum(xs[lo:hi]) / (hi - lo))
    return out


def svg_escape(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") \
        .replace('"', "&quot;").replace("'", "&apos;")


def streak_stats(counts):
    cur = 0
    for v in reversed(counts):
        if v > 0:
            cur += 1
        else:
            break

    best = 0
    run = 0
    for v in counts:
        if v > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return cur, best


def spaced_top_events(counts, threshold, limit=7, min_gap=7):
    cands = [(v, i) for i, v in enumerate(counts) if v >= threshold and v > 0]
    cands.sort(reverse=True)
    picked = []
    for v, i in cands:
        if all(abs(i - j) > min_gap for _, j in picked):
            picked.append((v, i))
            if len(picked) >= limit:
                break
    picked.sort(key=lambda t: t[1])
    return picked


def compute_window(days: int, tz_offset_minutes: int):
    """
    Create [from_dt, to_dt) aligned to LOCAL midnight boundaries like GitHub profile UI.

    Example (IST):
      local_to = tomorrow 00:00 IST
      local_from = local_to - 365 days
      then convert both to UTC timestamps for GraphQL.
    """
    now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    local_now = now_utc + datetime.timedelta(minutes=tz_offset_minutes)

    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_to = local_midnight + datetime.timedelta(days=1)
    local_from = local_to - datetime.timedelta(days=days)

    # Convert back to UTC, drop tzinfo for isoformat+"Z"
    to_dt = (local_to - datetime.timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)
    from_dt = (local_from - datetime.timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)
    return from_dt, to_dt


def main():
    from_dt, to_dt = compute_window(DAYS, TZ_OFFSET_MINUTES)

    include_private = os.environ.get("INCLUDE_PRIVATE", "1").strip().lower() not in ("0","false","no","off")

    # GitHub GraphQL schema does NOT support includePrivateContributions on contributionsCollection anymore.
    # Instead, private/restricted contributions are exposed via `restrictedContributionsCount` when the user
    # has enabled "private contribution counts" on their GitHub profile.
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

    payload = {
        "user": USER,
        "from": from_dt.isoformat() + "Z",
        "to": to_dt.isoformat() + "Z",
    }
    data = gh_api(query, payload)

    coll = data["data"]["user"]["contributionsCollection"]
    cal = coll["contributionCalendar"]
    restricted = int(coll.get("restrictedContributionsCount", 0) or 0)
    if not include_private:
        restricted = 0

    weeks = cal["weeks"]

    by_date = {}
    for w in weeks:
        for d in w["contributionDays"]:
            by_date[d["date"]] = int(d["contributionCount"])

    # Build exact day range [from_dt, to_dt) aligned to local midnight boundaries
    dates = []
    counts = []
    cur = from_dt.date()
    end = (to_dt - datetime.timedelta(days=1)).date()
    while cur <= end:
        ds = cur.isoformat()
        dates.append(cur)
        counts.append(by_date.get(ds, 0))
        cur += datetime.timedelta(days=1)

    total_visible = sum(counts)
    total = total_visible + restricted
    raw_max = max(counts) if counts else 1

    nonzero = [v for v in counts if v > 0]
    cap_p85 = percentile(nonzero, 85) if nonzero else 1
    scale_max = max(1, cap_p85)

    ma = moving_avg([min(v, scale_max) for v in counts], window=11)

    cur_streak, best_streak = streak_stats(counts)
    last7 = sum(counts[-7:]) if len(counts) >= 7 else sum(counts)
    last30 = sum(counts[-30:]) if len(counts) >= 30 else sum(counts)
    avg_day = (total / len(counts)) if counts else 0.0

    hot_thr = max(1, percentile(nonzero, 95) if nonzero else raw_max)
    events = spaced_top_events(counts, hot_thr, limit=7, min_gap=7)

    n = len(counts)
    plot_w = WIDTH - (PAD_X * 2)
    bw = plot_w / max(1, n)
    x0 = PAD_X

    def y_for(v):
        t = 0 if scale_max == 0 else (v / float(scale_max))
        t = max(0.0, min(1.0, t))
        return PLOT_BOTTOM - (t * PLOT_H)

    grid_lines = []
    for k in range(5):
        y = PLOT_TOP + (PLOT_H * k / 4.0)
        grid_lines.append(
            f'<line x1="{PAD_X}" y1="{y:.2f}" x2="{WIDTH-PAD_X}" y2="{y:.2f}" '
            f'stroke="{GRID}" stroke-width="1" opacity="0.55"/>'
        )

    week_lines = []
    month_lines = []
    month_labels = []
    for i, dt in enumerate(dates):
        x_mid = x0 + i * bw + (bw * 0.5)
        if dt.weekday() == 0:  # Monday
            week_lines.append(
                f'<line x1="{x_mid:.2f}" y1="{PLOT_TOP:.2f}" x2="{x_mid:.2f}" y2="{PLOT_BOTTOM:.2f}" '
                f'stroke="{GRID}" stroke-width="1" opacity="0.20"/>'
            )
        if dt.day == 1:
            month_lines.append(
                f'<line x1="{x_mid:.2f}" y1="{PLOT_TOP:.2f}" x2="{x_mid:.2f}" y2="{PLOT_BOTTOM:.2f}" '
                f'stroke="{GRID}" stroke-width="1" opacity="0.50"/>'
            )
            month_labels.append((dt.strftime("%b"), x_mid))

    month_label_svg = ""
    if month_labels:
        labels = []
        for label, x in month_labels:
            labels.append(
                f'<text x="{x:.2f}" y="{PLOT_BOTTOM+18}" fill="{MUTED}" font-size="10" text-anchor="middle" '
                f'font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \'Liberation Mono\', \'Courier New\', monospace">{label}</text>'
            )
        month_label_svg = "<g>" + "".join(labels) + "</g>"

    bars = []
    for i, v in enumerate(counts):
        x = x0 + i * bw
        y = y_for(min(v, scale_max))
        h = PLOT_BOTTOM - y
        op = 0.10 + 0.90 * (0 if scale_max == 0 else min(v, scale_max) / float(scale_max))
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(1.0, bw*0.92):.2f}" height="{h:.2f}" rx="1" '
            f'fill="{ACCENT}" opacity="{op:.3f}"/>'
        )

    line_pts = []
    for i, v in enumerate(ma):
        x = x0 + i * bw + (bw * 0.5)
        y = y_for(v)
        line_pts.append(f"{x:.2f},{y:.2f}")
    line = f'<polyline points="{" ".join(line_pts)}" fill="none" stroke="{ACCENT}" stroke-width="2" opacity="0.85"/>'

    event_marks = []
    for v, i in events:
        x = x0 + i * bw + (bw * 0.5)
        y = y_for(min(v, scale_max))
        event_marks.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.6" fill="{ACCENT}" opacity="0.95"/>')

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    # Header: show public+restricted split when available
    total_line = f"{total} contributions · peak/day {raw_max} · cap@p85 {int(scale_max)} · mode BARCODE"
    if restricted > 0:
        total_line = f"{total} contributions (public {total_visible} + private {restricted}) · peak/day {raw_max} · cap@p85 {int(scale_max)} · mode BARCODE"

    header = f"""
    <text x="{PAD_X}" y="30" fill="{FG}" font-size="14" font-weight="600"
      font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
      SIGNAL // {DAYS}D
    </text>
    <text x="{PAD_X}" y="52" fill="{MUTED}" font-size="11"
      font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
      {svg_escape(total_line)}
    </text>
    <text x="{WIDTH-PAD_X}" y="30" fill="{MUTED}" font-size="11" text-anchor="end"
      font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
      {svg_escape(now)}
    </text>
    """

    hud = f"""
    <g transform="translate({WIDTH-310},{70})">
      <rect x="0" y="0" width="286" height="58" rx="10" fill="#0B1220" opacity="0.90" stroke="{GRID}" stroke-width="1"/>
      <text x="14" y="22" fill="{FG}" font-size="11"
        font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
        Streak {cur_streak}d · Best {best_streak}d
      </text>
      <text x="14" y="40" fill="{FG}" font-size="11"
        font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
        Last 7d {last7:>3} · 30d {last30:>3}
      </text>
      <text x="14" y="56" fill="{MUTED}" font-size="10"
        font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
        Avg {avg_day:.2f}/d
      </text>
    </g>
    """

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>
  {header}
  <g opacity="1.0">
    {"".join(grid_lines)}
    {"".join(week_lines)}
    {"".join(month_lines)}
    {"".join(bars)}
    {line}
    {"".join(event_marks)}
  </g>
  {month_label_svg}
  {hud}
</svg>
"""

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
