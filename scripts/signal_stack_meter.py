#!/usr/bin/env python3
import os
import datetime as dt
from html import escape as esc

# Palette tuned to your existing HUD style
BG = "#0b0f14"
PANEL = "#0f1622"
STROKE = "#243244"
MUTED = "#7f8ea3"
TEXT = "#c9d4e5"
GREEN = "#22c55e"
GLOW = "#1faa55"

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

    W, H = 1200, 260
    PAD = 26
    HEADER_H = 54
    ROW_H = 38
    ROW_GAP = 10

    # Meter geometry
    meter_w = 18
    meter_h = 30
    meter_r = 5

    # Text column widths
    name_w = 220
    # description uses remaining width
    right_pad = PAD
    meter_x = W - PAD - meter_w
    desc_x = PAD + name_w

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{BG}"/>
      <stop offset="1" stop-color="#070b10"/>
    </linearGradient>
    <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="b"/>
      <feMerge>
        <feMergeNode in="b"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" fill="url(#bg)"/>
  <rect x="{PAD}" y="{PAD}" width="{W-2*PAD}" height="{H-2*PAD}" rx="14" fill="{PANEL}" stroke="{STROKE}" opacity="0.98"/>

  <!-- Header -->
  <text x="{PAD+18}" y="{PAD+30}" fill="{TEXT}" font-size="14" font-family="{FONT}" font-weight="700">OPERATING STACK // METER</text>
  <text x="{PAD+18}" y="{PAD+48}" fill="{MUTED}" font-size="12" font-family="{FONT}">
    {esc("Cyber Defense · Agent Systems · Low-Infra · Quantum · Long-Horizon")}
  </text>
  <text x="{W-PAD-18}" y="{PAD+30}" text-anchor="end" fill="{MUTED}" font-size="12" font-family="{FONT}">{esc(now_utc())}</text>
  <text x="{W-PAD-18}" y="{PAD+48}" text-anchor="end" fill="{MUTED}" font-size="12" font-family="{FONT}">user: {esc(user)}</text>

  <!-- Rows -->
'''

    y0 = PAD + HEADER_H
    for i, ((name, desc), lvl) in enumerate(zip(rows, levels)):
        y = y0 + i * (ROW_H + ROW_GAP)

        # Row container (subtle)
        svg += f'''
  <rect x="{PAD+18}" y="{y}" width="{W-2*PAD-36}" height="{ROW_H}" rx="10" fill="#0b1220" stroke="#162233" opacity="0.95"/>
  <text x="{PAD+34}" y="{y+24}" fill="{TEXT}" font-size="13" font-family="{FONT}" font-weight="700">{esc(name)}</text>
  <text x="{desc_x}" y="{y+24}" fill="{MUTED}" font-size="12.5" font-family="{FONT}">— {esc(desc)}</text>

  <!-- Vertical level meter -->
  <rect x="{meter_x}" y="{y+4}" width="{meter_w}" height="{meter_h}" rx="{meter_r}" fill="#0a111b" stroke="#1a2a3e"/>
'''

        # Fill height
        fill_h = int((lvl / 100.0) * (meter_h - 4))
        fill_y = (y + 4) + (meter_h - 2) - fill_h

        svg += f'''
  <rect x="{meter_x+2}" y="{fill_y}" width="{meter_w-4}" height="{fill_h}" rx="{meter_r-2}" fill="{GREEN}" filter="url(#softGlow)"/>
  <text x="{meter_x-10}" y="{y+24}" text-anchor="end" fill="{MUTED}" font-size="12" font-family="{FONT}">{lvl}</text>
'''

    svg += "\n</svg>\n"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
