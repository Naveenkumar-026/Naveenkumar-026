#!/usr/bin/env python3
import os, json, datetime, urllib.request

USER = os.environ.get("GH_USER", "Naveenkumar-026")
TOKEN = os.environ.get("GH_TOKEN")

OUT_PATH = os.environ.get("OUT_PATH", "assets/signal.svg")

BG = "#0D1117"
FG = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"
GRID = "#1F2937"

WIDTH = 980
HEIGHT = 220
PAD_X = 24
PAD_Y = 24
PLOT_TOP = 64
PLOT_BOTTOM = HEIGHT - 38
PLOT_H = PLOT_BOTTOM - PLOT_TOP

def gql(query, variables):
    url = "https://api.github.com/graphql"
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "signal-telemetry")
    req.add_header("Authorization", f"bearer {TOKEN}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def moving_avg(vals, w=14):
    out = []
    for i in range(len(vals)):
        a = max(0, i - w + 1)
        window = vals[a:i+1]
        out.append(sum(window) / len(window))
    return out
    
def percentile(values, p: float) -> int:
    """Nearest-rank percentile (p in [0,100]). Returns int cap >= 1 when possible."""
    if not values:
        return 1
    s = sorted(values)
    n = len(s)
    if n == 1:
        return max(1, int(s[0]))
    idx = int(round((p / 100.0) * (n - 1)))
    idx = clamp(idx, 0, n - 1)
    return max(1, int(s[idx]))

def svg_escape(s):
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
             .replace('"',"&quot;").replace("'","&#39;"))

def main():
    if not TOKEN:
        raise SystemExit("Missing GH_TOKEN. Provide it via env in GitHub Actions.")

    to_dt = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    from_dt = to_dt - datetime.timedelta(days=365)

    query = """
    query($user:String!, $from:DateTime!, $to:DateTime!) {
      user(login: $user) {
        contributionsCollection(from: $from, to: $to) {
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

    data = gql(query, {
        "user": USER,
        "from": from_dt.isoformat() + "Z",
        "to": to_dt.isoformat() + "Z"
    })

    if "errors" in data:
        raise SystemExit(json.dumps(data["errors"], indent=2))

    cc = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    total = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    days = []
    for w in cc:
        for d in w["contributionDays"]:
            days.append((d["date"], int(d["contributionCount"])))

    # exactly 365-ish days; keep last 365 entries
    days = days[-365:]
    counts = [c for _, c in days]
    raw_max = max(counts) if counts else 1

    # Normalize: cap extreme spikes to keep the year readable
    cap = percentile(counts, 95)  # p95 cap; change to 90/97 if you want
    scale_max = max(1, cap)

    # Plot geometry
    n = len(counts)
    plot_w = WIDTH - PAD_X*2
    # bar width tuned for 365 days
    bw = plot_w / n
    bw = clamp(bw, 1.2, 3.2)  # keep elegant
    # recompute plot_w actually used
    used_w = bw * n
    x0 = (WIDTH - used_w) / 2

    # Scale values
    def y_for(v):
        # v=0 -> bottom, v=scale_max -> top (normalized)
        v = min(v, scale_max)
        t = (v / scale_max) if scale_max else 0
        return PLOT_BOTTOM - t * PLOT_H

    ma = moving_avg(counts, w=21)

    # Grid lines (subtle)
    grid_lines = []
    for k in range(5):
        y = PLOT_TOP + (PLOT_H * k / 4.0)
        grid_lines.append(f'<line x1="{PAD_X}" y1="{y:.2f}" x2="{WIDTH-PAD_X}" y2="{y:.2f}" stroke="{GRID}" stroke-width="1"/>')

    # Bars (signal)
    bars = []
    for i, v in enumerate(counts):
        x = x0 + i*bw
        y = y_for(v)
        h = PLOT_BOTTOM - y
        # faint when zero, stronger when active
        op = 0.22 if v == 0 else 0.85
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bw*0.82:.2f}" height="{h:.2f}" rx="1.2" fill="{ACCENT}" opacity="{op}"/>'
        )

    # Moving-average line (telemetry feel)
    path = []
    for i, v in enumerate(ma):
        x = x0 + i*bw + (bw*0.41)
        y = y_for(v)
        path.append((x, y))
    d = "M " + " L ".join([f"{x:.2f} {y:.2f}" for x,y in path])

    title = "SIGNAL // 365D"
    subtitle = f"{total} contributions · peak/day {raw_max} · normalized@p95 {scale_max}"
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="fade" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.30"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>
    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.2" result="blur"/>
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

  <!-- Area under moving avg -->
  <path d="{d} L {path[-1][0]:.2f} {PLOT_BOTTOM:.2f} L {path[0][0]:.2f} {PLOT_BOTTOM:.2f} Z" fill="url(#fade)" opacity="0.55"/>

  <!-- Bars -->
  {"".join(bars)}

  <!-- Moving avg line -->
  <path d="{d}" fill="none" stroke="{ACCENT}" stroke-width="2.2" filter="url(#softGlow)" opacity="0.95"/>

  <!-- Frame -->
  <rect x="{PAD_X}" y="{PLOT_TOP}" width="{WIDTH-PAD_X*2}" height="{PLOT_H}" fill="none" stroke="{GRID}" stroke-width="1" rx="10"/>
</svg>
'''
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
