"""hero_sweep.py

Generates assets/hero_sweep.svg for your GitHub profile README.

Design goal:
  "SPECTRUM CAPTURE // LIVE" should be *useful*, not just aesthetic.
  This renders a two-column HUD card:
    - Left: spectrum trace (synthetic but consistent)
    - Right: aligned Live Ops Snapshot (operator, focus, build, computed signal stats)

Customise via environment variables (see CONFIG section).
"""

from __future__ import annotations

import datetime
import math
import os


# =============================
# CONFIG (set via env vars)
# =============================
OUT_PATH = os.environ.get("OUT_PATH", "assets/hero_sweep.svg")

CALLSIGN = os.environ.get("CALLSIGN", "SILENCIO")
HANDLE = os.environ.get("HANDLE", os.environ.get("GH_USER", "Naveenkumar-026"))
MODE = os.environ.get("MODE", "PUBLIC")
STATUS = os.environ.get("STATUS", "ONLINE")
BUILD_CHANNEL = os.environ.get("BUILD_CHANNEL", "MAIN")
TIMEBASE = os.environ.get("TIMEBASE", "UTC")

# One-line directive; keep it short (fits in one line).
DIRECTIVE = os.environ.get("DIRECTIVE", "Build durable systems. Release deliberately.")

# Comma-separated list shown as an aligned mini-list.
ACTIVE_SIGNALS = os.environ.get(
    "ACTIVE_SIGNALS",
    "CurtainDrop, Cytoguard, WhisperNet",
)

# Optional: override marker frequency label and delta-f display
MARKER_FREQ = os.environ.get("MARKER_FREQ", "38.2 kHz")
DF_LABEL = os.environ.get("DF_LABEL", "+0.4 kHz")


# =============================
# THEME
# =============================
BG = "#0D1117"          # GitHub dark
PANEL = "#000000"       # pure black
PANEL_2 = "#000000"     # pure black (keeps panelGrad solid)
GRID = "#1F2937"
GRID_SOFT = "#172033"
TEXT = "#C7D2FE"        # cool ink
MUTED = "#94A3B8"       # slate
DIM = "#64748B"         # dim slate
ACCENT = "#22C55E"      # neon green
ACCENT_DIM = "#16A34A"

FONT = "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"


def esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def wrap_mono(text: str, max_chars: int) -> list[str]:
    """Simple wrap tuned for monospace HUD lines."""
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def main() -> None:
    # Canvas (slightly taller than before to comfortably fit the snapshot)
    W, H = 1000, 320
    PAD = 24

    now = datetime.datetime.utcnow()
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")

    # Deterministic pseudo-spectrum (consistent shape; reads as a live sweep)
    n = 160
    xs = [i / (n - 1) for i in range(n)]
    base = []
    for x in xs:
        # 3 peaks
        p1 = math.exp(-((x - 0.18) / 0.045) ** 2)
        p2 = 0.72 * math.exp(-((x - 0.56) / 0.055) ** 2)
        p3 = 1.05 * math.exp(-((x - 0.83) / 0.030) ** 2)
        # subtle floor ripple
        ripple = 0.07 * math.sin(18.0 * x) + 0.04 * math.sin(43.0 * x)
        v = 0.14 + 0.62 * (0.55 * p1 + 0.65 * p2 + 0.9 * p3) + ripple
        base.append(clamp(v, 0.06, 0.98))

    peak_i = max(range(n), key=lambda i: base[i])
    peak_v = base[peak_i]

    # Synthetic dB stats (stable + plausible)
    peak_db = -28.0 + (peak_v - 0.6) * 8.0
    noise_db = -72.0 + 1.4 * math.sin(3.0)
    snr = peak_db - noise_db

    # Panel geometry
    panel_x, panel_y = PAD, PAD
    panel_w, panel_h = W - 2 * PAD, H - 2 * PAD
    header_h = 52
    body_x = panel_x + 14
    body_y = panel_y + header_h + 10
    body_w = panel_w - 28
    body_h = panel_h - header_h - 22

    # Two-column split
    gap = 14
    chart_w = int(body_w * 0.62)
    info_w = body_w - chart_w - gap
    chart_x = body_x
    info_x = body_x + chart_w + gap

    # Chart frame inside the left column
    frame_x, frame_y = chart_x, body_y
    frame_w, frame_h = chart_w, body_h
    # Reserve a little space at the bottom for freq labels
    label_pad = 22
    plot_h = frame_h - label_pad

    # Map to points
    pts = []
    for i, v in enumerate(base):
        px = frame_x + xs[i] * frame_w
        py = frame_y + (1.0 - v) * (plot_h - 12) + 6
        pts.append(f"{px:.2f},{py:.2f}")
    pts_str = " ".join(pts)

    peak_x = frame_x + xs[peak_i] * frame_w
    peak_y = frame_y + (1.0 - peak_v) * (plot_h - 12) + 6

    # Info layout helpers
    kv_left = info_x + 12
    kv_mid = info_x + int(info_w * 0.52)
    kv_val_dx = 92
    kv_right_val_x = info_x + info_w - 12
    kv_row_h = 18
    kv_right_min_x = kv_mid + 72 
    kv_right_fit = max(90, kv_right_val_x - kv_right_min_x)

    # Build a compact “signal packet” line derived from the stats
    packet = f"Peak {peak_db:.1f} dB · Noise {noise_db:.1f} dB · SNR {snr:.1f} dB"

    # Wrap directive and keep it clean
    directive_lines = wrap_mono(DIRECTIVE, 44)[:2]
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="panelGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{PANEL}"/>
      <stop offset="1" stop-color="{PANEL_2}"/>
    </linearGradient>
    <linearGradient id="specFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.32"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="10" result="b"/>
      <feMerge>
        <feMergeNode in="b"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="g"/>
      <feMerge>
        <feMergeNode in="g"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>

  <!-- Soft outer aura -->
  <rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="18" fill="{PANEL}" opacity="0.0" filter="url(#soft)"/>

  <!-- Main card -->
  <rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="18" fill="url(#panelGrad)" stroke="{GRID}" stroke-width="1"/>

  <!-- Header -->
  <text x="{panel_x + 18}" y="{panel_y + 26}" fill="{DIM}" font-size="12" font-family="{FONT}">
    Signal acquired. Operator online.
  </text>
  <text x="{panel_x + 18}" y="{panel_y + 46}" fill="{ACCENT}" font-size="18" font-family="{FONT}" font-weight="700" letter-spacing="1">
    SPECTRUM CAPTURE // LIVE
  </text>
  <text x="{panel_x + 18}" y="{panel_y + 66}" fill="{MUTED}" font-size="12" font-family="{FONT}">
    Security · Intelligence · Autonomy
  </text>

  <text x="{panel_x + panel_w - 18}" y="{panel_y + 28}" text-anchor="end" fill="{MUTED}" font-size="12" font-family="{FONT}">
    {esc(stamp)}
  </text>
  <text x="{panel_x + panel_w - 18}" y="{panel_y + 46}" text-anchor="end" fill="{DIM}" font-size="11" font-family="{FONT}">
    BUILD {esc(BUILD_CHANNEL)}  ·  MODE {esc(MODE)}  ·  STATUS {esc(STATUS)}
  </text>

  <!-- Divider under header -->
  <line x1="{panel_x + 14}" y1="{panel_y + header_h}" x2="{panel_x + panel_w - 14}" y2="{panel_y + header_h}" stroke="{GRID_SOFT}" stroke-width="1"/>

  <!-- LEFT: Spectrum frame -->
  <g>
    <rect x="{frame_x}" y="{frame_y}" width="{frame_w}" height="{frame_h}" rx="14" fill="{PANEL}" opacity="0.18" stroke="{GRID_SOFT}" stroke-width="1"/>

    <!-- grid -->
    <g opacity="0.60">
      {''.join([f'<line x1="{frame_x + (frame_w/10)*i:.2f}" y1="{frame_y}" x2="{frame_x + (frame_w/10)*i:.2f}" y2="{frame_y + plot_h:.2f}" stroke="{GRID_SOFT}" stroke-width="1"/>' for i in range(1,10)])}
      {''.join([f'<line x1="{frame_x}" y1="{frame_y + (plot_h/5)*j:.2f}" x2="{frame_x + frame_w}" y2="{frame_y + (plot_h/5)*j:.2f}" stroke="{GRID_SOFT}" stroke-width="1"/>' for j in range(1,5)])}
    </g>

    <!-- axis labels -->
    <text x="{frame_x + 10}" y="{frame_y + 16}" fill="{DIM}" font-size="11" font-family="{FONT}">0 dB</text>
    <text x="{frame_x + 10}" y="{frame_y + plot_h/2:.2f}" fill="{DIM}" font-size="11" font-family="{FONT}">-45 dB</text>
    <text x="{frame_x + 10}" y="{frame_y + plot_h - 6:.2f}" fill="{DIM}" font-size="11" font-family="{FONT}">-90 dB</text>

    <!-- spectrum fill + trace -->
    <polygon points="{frame_x:.2f},{frame_y + plot_h:.2f} {pts_str} {frame_x + frame_w:.2f},{frame_y + plot_h:.2f}" fill="url(#specFill)" opacity="0.75"/>
    <polyline points="{pts_str}" fill="none" stroke="{ACCENT}" stroke-width="2.3" filter="url(#glow)" opacity="0.78"/>

    <!-- peak marker -->
    <line x1="{peak_x:.2f}" y1="{frame_y}" x2="{peak_x:.2f}" y2="{frame_y + plot_h:.2f}" stroke="{ACCENT_DIM}" stroke-width="1.4" opacity="0.60" stroke-dasharray="4 6"/>
    <circle cx="{peak_x:.2f}" cy="{peak_y:.2f}" r="3.4" fill="{ACCENT}" opacity="0.92"/>

    <!-- frequency ticks (bottom) -->
    <text x="{frame_x + 6}" y="{frame_y + frame_h - 6}" fill="{DIM}" font-size="11" font-family="{FONT}">0 kHz</text>
    <text x="{frame_x + frame_w/2:.2f}" y="{frame_y + frame_h - 6}" text-anchor="middle" fill="{DIM}" font-size="11" font-family="{FONT}">24 kHz</text>
    <text x="{frame_x + frame_w - 6}" y="{frame_y + frame_h - 6}" text-anchor="end" fill="{DIM}" font-size="11" font-family="{FONT}">48 kHz</text>

    <!-- marker readout pill (top-right inside chart) -->
    <g opacity="0.94">
      <rect x="{frame_x + frame_w - 300}" y="{frame_y + 10}" width="{286}" height="{44}" rx="10" fill="{PANEL}" opacity="0.55" stroke="{GRID_SOFT}" stroke-width="1"/>
      <text x="{frame_x + frame_w - 18}" y="{frame_y + 28}" text-anchor="end" fill="{TEXT}" font-size="11" font-family="{FONT}">
        MKR {esc(MARKER_FREQ)}  Δf {esc(DF_LABEL)}
      </text>
      <text x="{frame_x + frame_w - 18}" y="{frame_y + 44}" text-anchor="end" fill="{MUTED}" font-size="11" font-family="{FONT}">
        {esc(packet)}
      </text>
    </g>
  </g>

  <!-- RIGHT: Live Ops Snapshot -->
  <g>
    <rect x="{info_x}" y="{body_y}" width="{info_w}" height="{body_h}" rx="14" fill="{PANEL}" opacity="0.18" stroke="{GRID_SOFT}" stroke-width="1"/>

    <text x="{info_x + 12}" y="{body_y + 20}" fill="{TEXT}" font-size="12" font-family="{FONT}" font-weight="700" letter-spacing="1">
      LIVE OPS SNAPSHOT
    </text>
    <text x="{info_x + info_w - 12}" y="{body_y + 20}" text-anchor="end" fill="{DIM}" font-size="11" font-family="{FONT}">
      {esc(TIMEBASE)}
    </text>

    <line x1="{info_x + 10}" y1="{body_y + 28}" x2="{info_x + info_w - 10}" y2="{body_y + 28}" stroke="{GRID_SOFT}" stroke-width="1"/>

    <!-- key/values (two columns) -->
    <g font-family="{FONT}" font-size="11">
      <text x="{kv_left}" y="{body_y + 46}" fill="{DIM}">CALLSIGN</text>
      <text x="{kv_left + kv_val_dx}" y="{body_y + 46}" fill="{TEXT}">{esc(CALLSIGN)}</text>

      <text x="{kv_mid}" y="{body_y + 46}" fill="{DIM}">HANDLE</text>
      <text x="{kv_right_val_x}" y="{body_y + 46}" text-anchor="end" fill="{TEXT}" textLength="{kv_right_fit}" lengthAdjust="spacingAndGlyphs"> {esc(HANDLE)} </text>

      <text x="{kv_left}" y="{body_y + 46 + kv_row_h}" fill="{DIM}">MODE</text>
      <text x="{kv_left + kv_val_dx}" y="{body_y + 46 + kv_row_h}" fill="{TEXT}">{esc(MODE)}</text>

      <text x="{kv_mid}" y="{body_y + 46 + kv_row_h}" fill="{DIM}">STATUS</text>
      <text x="{kv_right_val_x}" y="{body_y + 46 + kv_row_h}" text-anchor="end" fill="{TEXT}">{esc(STATUS)}</text>

      <text x="{kv_left}" y="{body_y + 46 + 2*kv_row_h}" fill="{DIM}">BUILD</text>
      <text x="{kv_left + kv_val_dx}" y="{body_y + 46 + 2*kv_row_h}" fill="{TEXT}">{esc(BUILD_CHANNEL)}</text>

      <text x="{kv_mid}" y="{body_y + 46 + 2*kv_row_h}" fill="{DIM}">MARKER</text>
      <text x="{kv_right_val_x}" y="{body_y + 46 + 2*kv_row_h}" text-anchor="end" fill="{TEXT}">{esc(MARKER_FREQ)}</text>
    </g>

    <line x1="{info_x + 10}" y1="{body_y + 46 + 2*kv_row_h + 10}" x2="{info_x + info_w - 10}" y2="{body_y + 46 + 2*kv_row_h + 10}" stroke="{GRID_SOFT}" stroke-width="1"/>

    <!-- Directive -->
    <text x="{info_x + 12}" y="{body_y + 46 + 2*kv_row_h + 30}" fill="{DIM}" font-size="11" font-family="{FONT}">DIRECTIVE</text>
    <text x="{info_x + 12}" y="{body_y + 46 + 2*kv_row_h + 48}" fill="{TEXT}" font-size="12" font-family="{FONT}" font-weight="600">{esc(directive_lines[0])}</text>
    <text x="{info_x + 12}" y="{body_y + 46 + 2*kv_row_h + 66}" fill="{MUTED}" font-size="12" font-family="{FONT}">{esc(directive_lines[1] if len(directive_lines) > 1 else "")}</text>
>
  </g>

</svg>
'''

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
