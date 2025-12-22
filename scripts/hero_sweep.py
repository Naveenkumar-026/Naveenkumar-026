import os, math, datetime

OUT_PATH = os.environ.get("OUT_PATH", "assets/hero_sweep.svg")

BG = "#0D1117"
FG = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"
GRID = "#1F2937"

WIDTH = 980
HEIGHT = 240
PAD = 28

def svg_escape(s: str) -> str:
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
             .replace('"',"&quot;").replace("'","&#39;"))

def main():
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    # Deterministic micro-stars (no randomness; stable output)
    stars = []
    frame_y = PAD + 56
    frame_h = HEIGHT - frame_y - PAD
    for i in range(0, 72):
        t = i * 12.9898
        sx = PAD + (math.fmod(t * 78.233, 1.0)) * (WIDTH - PAD*2)
        sy = frame_y + (math.fmod((t + 0.37) * 19.1919, 1.0)) * frame_h
        r = 0.6 + (i % 5) * 0.12
        a = 0.05 + (i % 9) * 0.012
        # Subtle twinkle (SMIL) — lightweight: only a fraction twinkles
        if i % 6 == 0:
            stars.append(
                f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r:.2f}" fill="{FG}" opacity="{a:.3f}">'
                f'  <animate attributeName="opacity" values="{a:.3f};{min(a+0.10,0.20):.3f};{a:.3f}" dur="{3.4 + (i%5)*0.4:.1f}s" repeatCount="indefinite"/>'
                f'</circle>'
            )
        else:
            stars.append(f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r:.2f}" fill="{FG}" opacity="{a:.3f}"/>')

    # Subtle grid
    grid = []
    gx0 = PAD
    gx1 = WIDTH - PAD
    gy0 = frame_y
    gy1 = frame_y + frame_h
    # Horizontal lines
    for k in range(5):
        y = gy0 + (frame_h * k / 4.0)
        grid.append(f'<line x1="{gx0}" y1="{y:.2f}" x2="{gx1}" y2="{y:.2f}" stroke="{GRID}" stroke-width="1" opacity="0.55"/>')
    # Vertical lines
    for k in range(9):
        x = gx0 + ((gx1 - gx0) * k / 8.0)
        grid.append(f'<line x1="{x:.2f}" y1="{gy0}" x2="{x:.2f}" y2="{gy1}" stroke="{GRID}" stroke-width="1" opacity="0.35"/>')

    # Wave path (signal trace) — animated dash motion
    wave_pts = []
    for i in range(0, 140):
        x = gx0 + (i / 139.0) * (gx1 - gx0)
        # layered sines for a “telemetry” look
        t = i / 10.0
        y = gy0 + frame_h * 0.55 + math.sin(t) * 10 + math.sin(t * 0.33) * 6
        wave_pts.append(f"{x:.2f},{y:.2f}")
    wave_poly = " ".join(wave_pts)

    # Sweep beam geometry
    beam_w = 180
    sweep_from = -beam_w
    sweep_to = WIDTH + beam_w

    title = "SIGNAL SWEEP // HEADER"
    subtitle = "Security · Intelligence · Autonomy"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="2.4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <linearGradient id="beamGrad" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0"   stop-color="{ACCENT}" stop-opacity="0.00"/>
      <stop offset="0.40" stop-color="{ACCENT}" stop-opacity="0.10"/>
      <stop offset="0.50" stop-color="{ACCENT}" stop-opacity="0.38"/>
      <stop offset="0.60" stop-color="{ACCENT}" stop-opacity="0.10"/>
      <stop offset="1"   stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>

    <linearGradient id="scanBand" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.00"/>
      <stop offset="0.50" stop-color="{ACCENT}" stop-opacity="0.10"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>

  <!-- Header text -->
  <text x="{PAD}" y="34" fill="{ACCENT}" font-size="18" letter-spacing="1.2"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{svg_escape(title)}</text>
  <text x="{PAD}" y="54" fill="{FG}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{svg_escape(subtitle)}</text>
  <text x="{WIDTH-PAD}" y="54" text-anchor="end" fill="{MUTED}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{svg_escape(now)}</text>

  <!-- Frame -->
  <rect x="{PAD}" y="{frame_y}" width="{WIDTH-PAD*2}" height="{frame_h}" fill="none" stroke="{GRID}" stroke-width="1" rx="12"/>

  <!-- Grid -->
  {"".join(grid)}

  <!-- Micro-stars -->
  {"".join(stars)}

  <!-- Signal trace -->
  <polyline points="{wave_poly}" fill="none" stroke="{ACCENT}" stroke-width="2" opacity="0.28"
            stroke-dasharray="10 10">
    <animate attributeName="stroke-dashoffset" from="0" to="-120" dur="6.5s" repeatCount="indefinite"/>
  </polyline>

  <!-- Subtle horizontal scan band -->
  <rect x="{PAD}" y="{frame_y + frame_h*0.62:.2f}" width="{WIDTH-PAD*2}" height="2" fill="url(#scanBand)" opacity="0.9"/>

  <!-- Moving sweep beam -->
  <g filter="url(#softGlow)">
    <g>
      <rect x="0" y="{frame_y}" width="{beam_w}" height="{frame_h}" fill="url(#beamGrad)" opacity="0.95"/>
      <line x1="{beam_w*0.5:.2f}" y1="{frame_y}" x2="{beam_w*0.5:.2f}" y2="{frame_y + frame_h}" stroke="{ACCENT}" stroke-width="2.2" opacity="0.55"/>
      <animateTransform attributeName="transform" type="translate"
                        from="{sweep_from} 0" to="{sweep_to} 0"
                        dur="7.2s" repeatCount="indefinite"/>
    </g>
  </g>
</svg>
'''
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
