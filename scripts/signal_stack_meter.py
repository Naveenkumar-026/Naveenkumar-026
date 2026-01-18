#!/usr/bin/env python3
import os
import datetime as dt
from html import escape as esc

# Theme palette (dark HUD + heat bars)
BG = "#000000"
PANEL = "#000000"
STROKE = "#1f1f1f"
MUTED = "#7f8ea3"
TEXT = "#c9d4e5"

# Heat gradient (orange -> red) tuned to your theme
HEAT_L = "#f59e0b"  # amber
HEAT_M = "#f97316"  # orange
HEAT_R = "#ef4444"  # red

FONT = "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"

def now_utc():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def parse_levels(s: str, n: int):
    try:
        parts = [int(x.strip()) for x in s.split(",") if x.strip()]
        if len(parts) < n:
            parts += [70] * (n - len(parts))
        return [max(0, min(100, v)) for v in parts[:n]]
    except Exception:
        return [74, 78, 74, 70, 73][:n]

def main():
    out_path = os.getenv("OUT_PATH", "assets/signal_stack.svg")
    user = os.getenv("GITHUB_USER", "Naveenkumar-026")
    levels = parse_levels(os.getenv("STACK_LEVELS", "74,78,74,70,73"), 5)

    rows = [
        ("Cyber Defense", "defensive architectures, response automation, hardening"),
        ("Agent Systems", "orchestration, evaluation harnesses, safety rails"),
        ("Low-Infra", "privacy-first, edge/off-grid constraints"),
        ("Quantum", "practical integration paths, disciplined learning"),
        ("Long-Horizon", "durable primitives before scale"),
    ]

    # Canvas (auto-sized so rows never clip)
    W = 1200
    PAD = 26
    HEADER_H = 56
    ROW_H = 38
    ROW_GAP = 10
    INNER_BOTTOM = 18

    N = len(rows)
    H = PAD * 2 + HEADER_H + (N * ROW_H) + ((N - 1) * ROW_GAP) + INNER_BOTTOM

    # Layout columns
    name_x = PAD + 34
    name_w = 210
    desc_x = name_x + name_w
    # Right side bar area
    bar_w = 290
    num_w = 0
    bar_x = W - PAD - 18 - bar_w


    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{BG}"/>
      <stop offset="1" stop-color="#070b10"/>
    </linearGradient>

    <!-- Heat fill -->
    <linearGradient id="heat" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="{HEAT_L}"/>
      <stop offset="55%" stop-color="{HEAT_M}"/>
      <stop offset="100%" stop-color="{HEAT_R}"/>
    </linearGradient>

    <!-- Subtle scanline texture -->
    <pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse">
      <rect width="6" height="6" fill="transparent"/>
      <rect y="0" width="6" height="1" fill="#0a1220" opacity="0.35"/>
    </pattern>

    <filter id="heatGlow" x="-40%" y="-80%" width="200%" height="260%">
      <feGaussianBlur stdDeviation="3.2" result="b"/>
      <feColorMatrix in="b" type="matrix"
        values="1 0 0 0 0
                0 0.55 0 0 0
                0 0 0.2 0 0
                0 0 0 0.85 0" result="c"/>
      <feMerge>
        <feMergeNode in="c"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="url(#bg)"/>
  <rect x="{PAD}" y="{PAD}" width="{W-2*PAD}" height="{H-2*PAD}" rx="14" fill="{PANEL}" stroke="{STROKE}" opacity="0.98"/>
  <rect x="{PAD}" y="{PAD}" width="{W-2*PAD}" height="{H-2*PAD}" rx="14" fill="url(#scan)" opacity="0.35"/>

  <!-- Header -->
  <text x="{PAD+18}" y="{PAD+32}" fill="{TEXT}" font-size="14" font-family="{FONT}" font-weight="700">OPERATOR STACK // HEAT BARS</text>
  <text x="{PAD+18}" y="{PAD+50}" fill="{MUTED}" font-size="12" font-family="{FONT}">{esc("Focus intensity · described primitives + measured levels")}</text>

  <text x="{W-PAD-18}" y="{PAD+32}" text-anchor="end" fill="{MUTED}" font-size="12" font-family="{FONT}">{esc(now_utc())}</text>
  <text x="{W-PAD-18}" y="{PAD+50}" text-anchor="end" fill="{MUTED}" font-size="12" font-family="{FONT}">user: {esc(user)}</text>
'''

    y0 = PAD + HEADER_H
    track_h = 14
    track_r = 7

    for i, ((name, desc), lvl) in enumerate(zip(rows, levels)):
        y = y0 + i * (ROW_H + ROW_GAP)
        y_mid = y + (ROW_H // 2)
        track_y = y_mid - (track_h // 2)
        fill_y = track_y + 2

        # Row background
        svg += f'''
  <rect x="{PAD+18}" y="{y}" width="{W-2*PAD-36}" height="{ROW_H}" rx="10" fill="#0b1220" stroke="#162233" opacity="0.95"/>

  <text x="{name_x}" y="{y_mid}" dominant-baseline="middle" fill="{TEXT}" font-size="13" font-family="{FONT}" font-weight="700">{esc(name)}</text>
  <text x="{desc_x}" y="{y_mid}" dominant-baseline="middle" fill="{MUTED}" font-size="12.5" font-family="{FONT}">— {esc(desc)}</text>

  <!-- Horizontal track -->
  <rect x="{bar_x}" y="{track_y}" width="{bar_w}" height="{track_h}" rx="{track_r}" fill="#08101a" stroke="#1a2a3e"/>
'''

        fill_w = int((lvl / 100.0) * (bar_w - 4))
        svg += f'''
  <!-- Heat fill -->
  <rect x="{bar_x+2}" y="{fill_y}" width="{fill_w}" height="{track_h-4}" rx="{track_r-2}" fill="url(#heat)" filter="url(#heatGlow)"/>

'''

    svg += "\n</svg>\n"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
