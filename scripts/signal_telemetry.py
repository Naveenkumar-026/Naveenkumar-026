import os, json, datetime, urllib.request, urllib.error

USER = os.environ.get("GH_USER", "Naveenkumar-026")
TOKEN = os.environ.get("GH_TOKEN")
OUT_PATH = os.environ.get("OUT_PATH", "assets/signal_barcode.svg")

INCLUDE_PRIVATE = os.environ.get("INCLUDE_PRIVATE", "true").strip().lower() in ("1","true","yes","y","on")
DAYS = int(os.environ.get("DAYS", "365"))

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


def gh_api(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise SystemExit("GH_TOKEN missing. Set GH_TOKEN env or Actions secret.")

    req = urllib.request.Request("https://api.github.com/graphql", method="POST")
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "signal-telemetry-script")

    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    try:
        with urllib.request.urlopen(req, payload, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub GraphQL HTTPError {e.code}: {body}")
    except Exception as e:
        raise SystemExit(f"GitHub GraphQL request failed: {e}")

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
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;") \
                    .replace('"',"&quot;").replace("'","&apos;")


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


def main():
    # Use a stable “last N days” boundary (includes today)
    to_dt = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    from_dt = to_dt - datetime.timedelta(days=DAYS)

    query = """
    query($user:String!, $from:DateTime!, $to:DateTime!, $priv:Boolean!) {
      user(login: $user) {
        contributionsCollection(from: $from, to: $to, includePrivateContributions: $priv) {
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
        "from": from_dt.isoformat() + "Z",
        "to": to_dt.isoformat() + "Z",
        "priv": INCLUDE_PRIVATE,
    })

    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

    # Map date -> count from API
    by_date = {}
    for w in weeks:
        for d in w["contributionDays"]:
            by_date[d["date"]] = int(d["contributionCount"])

    # Build exact day range to avoid “weeks padding” mismatches
    dates = []
    counts = []
    cur = from_dt.date()
    end = (to_dt - datetime.timedelta(days=1)).date()  # inclusive last day
    while cur <= end:
        ds = cur.isoformat()
        dates.append(cur)
        counts.append(by_date.get(ds, 0))
        cur += datetime.timedelta(days=1)

    # Ensure subtitle total matches exactly what is plotted
    total = sum(counts)
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
        x_mid = x0 + i*bw + (bw * 0.5)
        if dt.weekday() == 0:  # Monday
            week_lines.append(
                f'<line x1="{x_mid:.2f}" y1="{PLOT_TOP:.2f}" x2="{x_mid:.2f}" y2="{PLOT_BOTTOM:.2f}" '
                f'stroke="{GRID}" stroke-width="1" opacity="0.10"/>'
            )
        if dt.day == 1:
            month_lines.append(
                f'<line x1="{x_mid:.2f}" y1="{PLOT_TOP:.2f}" x2="{x_mid:.2f}" y2="{PLOT_BOTTOM:.2f}" '
                f'stroke="{GRID}" stroke-width="1.2" opacity="0.22"/>'
            )
            month_labels.append(
                f'<text x="{x_mid+4:.2f}" y="{PLOT_BOTTOM+18:.2f}" fill="{MUTED}" '
                f'font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" '
                f'font-size="10">{dt.strftime("%b")}</text>'
            )

    streak_band = ""
    if cur_streak >= 5:
        start_i = max(0, n - cur_streak)
        x1 = x0 + start_i*bw
        w = cur_streak*bw
        streak_band = (
            f'<rect x="{x1:.2f}" y="{PLOT_TOP:.2f}" width="{w:.2f}" height="{PLOT_H:.2f}" '
            f'fill="{ACCENT}" opacity="0.035"/>'
        )

    pulses = []
    for i, v_raw in enumerate(counts):
        v = min(v_raw, scale_max)
        intensity = (v / scale_max) if scale_max else 0.0
        x_mid = x0 + i*bw + (bw * 0.5)

        op_line = 0.03 + (intensity * 0.22)
        pulses.append(
            f'<line x1="{x_mid:.2f}" y1="{PLOT_TOP:.2f}" x2="{x_mid:.2f}" y2="{PLOT_BOTTOM:.2f}" '
            f'stroke="{ACCENT}" stroke-width="1.0" opacity="{op_line:.3f}"/>'
        )

        if v_raw > 0:
            burst_h = 2.0 + intensity * (PLOT_H * 0.34)
            op_burst = 0.12 + (intensity * 0.62)
            pulses.append(
                f'<line x1="{x_mid:.2f}" y1="{PLOT_BOTTOM - burst_h:.2f}" x2="{x_mid:.2f}" y2="{PLOT_BOTTOM:.2f}" '
                f'stroke="{ACCENT}" stroke-width="1.9" opacity="{op_burst:.3f}"/>'
            )

    path = []
    for i, v in enumerate(ma):
        x = x0 + i*bw + (bw*0.41)
        y = y_for(v)
        path.append((x, y))
    d = "M " + " L ".join([f"{x:.2f} {y:.2f}" for x, y in path]) if path else ""

    pips = []
    for v, i in events:
        x_mid = x0 + i*bw + (bw * 0.5)
        y = y_for(min(v, scale_max))
        pips.append(
            f'<g opacity="0.90">'
            f'<line x1="{x_mid:.2f}" y1="{PLOT_TOP:.2f}" x2="{x_mid:.2f}" y2="{PLOT_BOTTOM:.2f}" '
            f'stroke="{ACCENT}" stroke-width="1" opacity="0.22"/>'
            f'<circle cx="{x_mid:.2f}" cy="{y:.2f}" r="3.2" fill="{ACCENT}" filter="url(#softGlow)"/>'
            f'</g>'
        )

    hud_lines = [
        f"Streak {cur_streak}d  ·  Best {best_streak}d",
        f"Last 7d {last7}  ·  30d {last30}",
        f"Avg {avg_day:.2f}/d  ·  Peak {raw_max}  ·  Cap p85 {scale_max}",
    ]
    hud_w = 320
    hud_h = 18 + 14*len(hud_lines)
    hud_x = WIDTH - PAD_X - hud_w
    hud_y = PLOT_TOP + 10
    hud = (
        f'<g>'
        f'<rect x="{hud_x}" y="{hud_y}" width="{hud_w}" height="{hud_h}" rx="10" '
        f'fill="#0B1220" opacity="0.78" stroke="{GRID}" stroke-width="1"/>'
    )
    for j, line in enumerate(hud_lines):
        ty = hud_y + 18 + 14*j
        hud += (
            f'<text x="{hud_x + hud_w - 12}" y="{ty}" text-anchor="end" fill="{FG}" '
            f'font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" '
            f'font-size="11">{svg_escape(line)}</text>'
        )
    hud += '</g>'

    title = "SIGNAL // 365D"
    subtitle = f"{total} contributions · peak/day {raw_max} · cap@p85 {scale_max} · mode BARCODE"
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    # Avoid referencing path[-1] if path is empty
    area = ""
    if path:
        area = f'<path d="{d} L {path[-1][0]:.2f} {PLOT_BOTTOM:.2f} L {path[0][0]:.2f} {PLOT_BOTTOM:.2f} Z" fill="url(#fade)" opacity="0.42"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="fade" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.26"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>
    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="1.6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>

  <text x="{PAD_X}" y="32" fill="{ACCENT}" font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="18" letter-spacing="1.2">{svg_escape(title)}</text>
  <text x="{PAD_X}" y="52" fill="{FG}" font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="12">{svg_escape(subtitle)}</text>
  <text x="{WIDTH-PAD_X}" y="52" text-anchor="end" fill="{MUTED}" font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="12">{svg_escape(now)}</text>

  {"".join(grid_lines)}
  {"".join(week_lines)}
  {"".join(month_lines)}
  {streak_band}

  {area}

  {"".join(pulses)}

  <path d="{d}" fill="none" stroke="{ACCENT}" stroke-width="1.9" filter="url(#softGlow)" opacity="0.92"/>

  {"".join(pips)}

  {hud}

  {"".join(month_labels)}

  <rect x="{PAD_X}" y="{PLOT_TOP}" width="{WIDTH-PAD_X*2}" height="{PLOT_H}" fill="none" stroke="{GRID}" stroke-width="1" rx="10"/>
</svg>
'''
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
