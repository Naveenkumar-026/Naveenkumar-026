import os
import datetime
import hashlib


OUT_PATH = os.environ.get("OUT_PATH", "assets/signal_stack.svg")

# Theme (match existing assets)
BG = "#0D1117"
PANEL = "#0B1220"
GRID = "#1F2937"
TEXT = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"
ACCENT_DIM = "#16A34A"

W, H = 980, 220
PAD = 24
R = 14


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _day_hash(user: str, day: str) -> int:
    return int(hashlib.sha1(f"{user}|{day}".encode("utf-8")).hexdigest()[:8], 16)


def parse_levels(s: str):
    # "80,72,65,60,75"
    out = []
    for p in s.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            v = int(float(p))
        except ValueError:
            continue
        out.append(max(0, min(100, v)))
    return out


def main() -> None:
    user = os.environ.get("GH_USER") or os.environ.get("GITHUB_ACTOR") or "Naveenkumar-026"
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    ts = datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%d %H:%M UTC")

    labels = [
        "Cyber Defense",
        "Agent Systems",
        "Low-Infra",
        "Quantum",
        "Long-Horizon",
    ]

    # If you want explicit control, set STACK_LEVELS="80,74,68,62,72" in Actions.
    levels_env = os.environ.get("STACK_LEVELS", "").strip()
    levels = parse_levels(levels_env) if levels_env else []

    base = [78, 74, 70, 66, 72]
    if len(levels) != len(labels):
        # Gentle daily movement, deterministic per user/day.
        h = _day_hash(user, today)
        jitter = [((h >> (i * 5)) & 0x1F) - 16 for i in range(len(labels))]  # -16..15
        levels = [max(35, min(95, base[i] + int(jitter[i] * 0.35))) for i in range(len(labels))]

    x0 = PAD
    y0 = PAD
    w0 = W - PAD * 2
    h0 = H - PAD * 2

    # Plot area
    plot_x = x0 + 18
    plot_y = y0 + 64
    plot_w = w0 - 36
    plot_h = h0 - 92

    # Meter geometry
    n = len(labels)
    gap = 18
    bar_w = int((plot_w - gap * (n - 1)) / n)
    bar_max_h = plot_h

    # Subtle grid
    grid_lines = []
    for i in range(1, 10):
        gx = plot_x + int(plot_w * i / 10)
        grid_lines.append(
            f'<line x1="{gx}" y1="{plot_y}" x2="{gx}" y2="{plot_y+plot_h}" stroke="{GRID}" stroke-opacity="0.30" stroke-width="1" />'
        )
    for i in range(1, 5):
        gy = plot_y + int(plot_h * i / 5)
        grid_lines.append(
            f'<line x1="{plot_x}" y1="{gy}" x2="{plot_x+plot_w}" y2="{gy}" stroke="{GRID}" stroke-opacity="0.24" stroke-width="1" />'
        )

    bars = []
    for i, (lab, v) in enumerate(zip(labels, levels)):
        bx = plot_x + i * (bar_w + gap)
        by = plot_y

        fill_h = int((v / 100.0) * bar_max_h)
        fy = by + (bar_max_h - fill_h)

        # Track
        bars.append(
            f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bar_max_h}" rx="10" fill="none" stroke="{GRID}" stroke-opacity="0.65" />'
        )

        # Fill (stacked subtle gradient effect)
        bars.append(
            f'<rect x="{bx+2}" y="{fy+2}" width="{bar_w-4}" height="{fill_h-4 if fill_h>6 else max(2, fill_h)}" rx="9" fill="{ACCENT_DIM}" fill-opacity="0.35" />'
        )
        bars.append(
            f'<rect x="{bx+3}" y="{fy+3}" width="{bar_w-6}" height="{fill_h-6 if fill_h>10 else max(2, fill_h-2)}" rx="8" fill="{ACCENT}" fill-opacity="0.80" />'
        )

        # Value label
        bars.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{fy-8}" text-anchor="middle" fill="{TEXT}" font-size="11" '
            f'font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{v:02d}</text>'
        )

        # Name label
        bars.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{plot_y+plot_h+18}" text-anchor="middle" fill="{MUTED}" font-size="11" '
            f'font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(lab)}</text>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{PANEL}"/>
      <stop offset="1" stop-color="{BG}"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2" result="b"/>
      <feMerge>
        <feMergeNode in="b"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>
  <rect x="{x0}" y="{y0}" width="{w0}" height="{h0}" rx="{R}" fill="url(#panel)" stroke="{GRID}" stroke-opacity="0.7"/>
  <rect x="{x0+10}" y="{y0+10}" width="{w0-20}" height="{h0-20}" rx="{R-6}" fill="none" stroke="{GRID}" stroke-opacity="0.35"/>

  <text x="{x0+28}" y="{y0+34}" fill="{TEXT}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">SIGNAL STACK // METER</text>
  <text x="{x0+w0-28}" y="{y0+34}" text-anchor="end" fill="{MUTED}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(ts)}</text>

  <text x="{x0+28}" y="{y0+54}" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">Focus intensity · stable daily hash · user: {esc(user)}</text>

  <!-- Plot -->
  {''.join(grid_lines)}
  {''.join(bars)}

  <!-- Axis hints -->
  <text x="{plot_x-4}" y="{plot_y+12}" text-anchor="end" fill="{MUTED}" font-size="10"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">100</text>
  <text x="{plot_x-4}" y="{plot_y+plot_h}" text-anchor="end" fill="{MUTED}" font-size="10"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">0</text>

</svg>
'''

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
