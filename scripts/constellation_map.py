import os, math, datetime

OUT_PATH = os.environ.get("OUT_PATH", "assets/constellation.svg")

BG = "#0D1117"
FG = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"
GRID = "#1F2937"

WIDTH = 980
HEIGHT = 220
PAD = 28

# Node labels (identity only, not “projects”)
NODES = [
    ("SECURITY",        0.14, 0.55),
    ("INTELLIGENCE",    0.34, 0.26),
    ("AUTONOMY",        0.50, 0.62),
    ("LOW-INFRA",       0.70, 0.34),
    ("QUANTUM",         0.86, 0.60),
]

# Edges (minimal constellation lines)
EDGES = [
    ("SECURITY", "INTELLIGENCE"),
    ("INTELLIGENCE", "AUTONOMY"),
    ("AUTONOMY", "LOW-INFRA"),
    ("LOW-INFRA", "QUANTUM"),
    ("INTELLIGENCE", "LOW-INFRA"),
]

def svg_escape(s: str) -> str:
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
             .replace('"',"&quot;").replace("'","&#39;"))

def main():
    # Build lookup of positions
    pos = {}
    for name, nx, ny in NODES:
        x = PAD + nx * (WIDTH - PAD*2)
        y = PAD + ny * (HEIGHT - PAD*2)
        pos[name] = (x, y)

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    # Background micro-stars (deterministic pattern, no randomness)
    stars = []
    for i in range(0, 64):
        # a simple low-discrepancy-ish sequence
        t = i * 12.9898
        sx = PAD + (math.fmod(t * 78.233, 1.0)) * (WIDTH - PAD*2)
        sy = PAD + (math.fmod((t + 0.37) * 19.1919, 1.0)) * (HEIGHT - PAD*2)
        r = 0.6 + (i % 5) * 0.12
        a = 0.08 + (i % 7) * 0.01
        stars.append(f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="{r:.2f}" fill="{FG}" opacity="{a:.3f}"/>')

    # Edges
    lines = []
    for a, b in EDGES:
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{ACCENT}" stroke-width="1" opacity="0.22"/>'
        )

    # Nodes: glow + core
    nodes = []
    for name, _, _ in NODES:
        x, y = pos[name]
        # glow ring
        nodes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="10" fill="{ACCENT}" opacity="0.10" filter="url(#softGlow)"/>')
        nodes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.2" fill="{ACCENT}" opacity="0.95"/>')
        nodes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.2" fill="{BG}" opacity="0.85"/>')

        # label
        nodes.append(
            f'<text x="{x+12:.2f}" y="{y+4:.2f}" fill="{FG}" font-size="12" '
            f'font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" '
            f'letter-spacing="0.8">{svg_escape(name)}</text>'
        )

    # Title
    title = "CONSTELLATION // FOCUS"
    subtitle = "Security · Intelligence · Autonomy"
    footer = f"{now}"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="2.4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <linearGradient id="fade" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.00"/>
      <stop offset="0.5" stop-color="{ACCENT}" stop-opacity="0.08"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>

  <!-- Header -->
  <text x="{PAD}" y="34" fill="{ACCENT}" font-size="18" letter-spacing="1.2"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{svg_escape(title)}</text>
  <text x="{PAD}" y="54" fill="{FG}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{svg_escape(subtitle)}</text>
  <text x="{WIDTH-PAD}" y="54" text-anchor="end" fill="{MUTED}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{svg_escape(footer)}</text>

  <!-- Subtle scan band -->
  <rect x="{PAD}" y="{HEIGHT-86}" width="{WIDTH-PAD*2}" height="1.5" fill="url(#fade)" opacity="0.9"/>

  <!-- Micro stars -->
  {"".join(stars)}

  <!-- Constellation edges -->
  {"".join(lines)}

  <!-- Nodes + labels -->
  {"".join(nodes)}

  <!-- Frame -->
  <rect x="{PAD}" y="{PAD+44}" width="{WIDTH-PAD*2}" height="{HEIGHT-(PAD+44)-PAD}" fill="none" stroke="{GRID}" stroke-width="1" rx="12"/>
</svg>
'''
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
