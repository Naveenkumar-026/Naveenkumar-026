import os, math, datetime

OUT_PATH = os.environ.get("OUT_PATH", "assets/hero_sweep.svg")

# GitHub dark canvas + your neon green
BG = "#0D1117"
PANEL = "#0B1220"
GRID = "#1F2937"
GRID_SOFT = "#172033"
TEXT = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"
ACCENT_DIM = "#16A34A"

W, H = 980, 240
PAD = 26

def esc(s: str) -> str:
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
             .replace('"',"&quot;").replace("'","&#39;"))

def clamp(x, a, b):
    return a if x < a else b if x > b else x

def pseudo(i: float) -> float:
    # deterministic pseudo-noise in [0,1)
    return math.fmod(math.sin(i * 12.9898 + 78.233) * 43758.5453, 1.0)

def main():
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d UTC")

    # Header text (professional intro line)
    intro = "Signal acquired. Operator online."
    title = "SPECTRUM CAPTURE // LIVE"
    subtitle = "Security · Intelligence · Autonomy"

    callsign = "CALLSIGN: SILENCIO"
    build = "BUILD CHANNEL: MAIN · MODE: PUBLIC"

    # Plot frame
    frame_y = PAD + 62
    frame_h = H - frame_y - PAD
    frame_x = PAD
    frame_w = W - PAD * 2

    # Spectrum parameters (feel free to change labels)
    f_left = "0 kHz"
    f_mid = "24 kHz"
    f_right = "48 kHz"

    db_top = "0 dB"
    db_mid = "-45 dB"
    db_bot = "-90 dB"

    # Generate a realistic noise floor + peaks (deterministic)
    N = 220
    xs = []
    ys = []
    # baseline noise floor (in dB, negative)
    base = -72.0
    for i in range(N):
        t = i / (N - 1)
        x = frame_x + t * frame_w

        # shaped noise floor + slight slope + ripple
        nf = base + (t - 0.5) * 6.0
        nf += math.sin(t * 9.0) * 1.6
        nf += (pseudo(i * 0.45) - 0.5) * 1.2

        # add a few narrowband peaks like an FFT capture
        def peak(center, width, height):
            return height * math.exp(-((t - center) ** 2) / (2 * width ** 2))

        p = 0.0
        p += peak(0.18, 0.016, 22.0)
        p += peak(0.52, 0.022, 15.0)
        p += peak(0.80, 0.014, 26.0)

        db = nf + p  # still negative but with peaks lifting

        # map dB (-90..0) to y (bottom..top)
        db = clamp(db, -90.0, 0.0)
        y = frame_y + (1.0 - ((db + 90.0) / 90.0)) * frame_h

        xs.append(x)
        ys.append(y)

    # Light smoothing to reduce harsh jaggedness (keeps peaks sharp)
    ys2 = ys[:]
    for i in range(2, N - 2):
        ys2[i] = (ys[i-2]*0.08 + ys[i-1]*0.22 + ys[i]*0.40 + ys[i+1]*0.22 + ys[i+2]*0.08)
    ys = ys2
    pts = " ".join(f"{xs[i]:.2f},{ys[i]:.2f}" for i in range(N))

    # Compute a simple peak marker (for readout)
    min_y = min(ys)
    peak_idx = ys.index(min_y)
    peak_x = xs[peak_idx]
    peak_y = ys[peak_idx]

    # Readout values (synthetic but plausible)
    peak_db = -28.0
    noise_db = -72.0
    snr = 44.0
    marker_freq = "38.2 kHz"
    df = "+0.4 kHz"

    # Waterfall: render stripes and animate vertical translation
    # (This is the main “realism” cue.)
    wf_h = 48
    wf_y = frame_y + frame_h - wf_h
    rows = 18
    cols = 120

    # Precompute small rectangles for waterfall intensity
    wf_cells = []
    cell_w = frame_w / cols
    cell_h = wf_h / rows

    for r in range(rows):
        for c in range(cols):
            t = c / (cols - 1)
            # intensity derived from spectrum peaks + noise
            intensity = 0.06
            intensity += 0.25 * math.exp(-((t - 0.18) ** 2) / (2 * 0.020 ** 2))
            intensity += 0.18 * math.exp(-((t - 0.52) ** 2) / (2 * 0.028 ** 2))
            intensity += 0.30 * math.exp(-((t - 0.80) ** 2) / (2 * 0.018 ** 2))
            # time variation per row (deterministic)
            intensity += (pseudo(r * 9.1 + c * 0.17) - 0.5) * 0.06
            intensity = clamp(intensity, 0.02, 0.32)

            x = frame_x + c * cell_w
            y = wf_y + r * cell_h

            wf_cells.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_w+0.10:.2f}" height="{cell_h+0.10:.2f}" '
                f'fill="{ACCENT}" opacity="{intensity:.3f}"/>'
            )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="1.6" result="b"/>
      <feMerge>
        <feMergeNode in="b"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <linearGradient id="panelGrad" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{PANEL}" stop-opacity="0.95"/>
      <stop offset="1" stop-color="{BG}" stop-opacity="1"/>
    </linearGradient>

    <linearGradient id="specFill" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.18"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0.00"/>
    </linearGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}"/>

  <!-- Intro / Title -->
  <text x="{PAD}" y="28" fill="{TEXT}" font-size="14"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(intro)}</text>

  <text x="{PAD}" y="52" fill="{ACCENT}" font-size="18" letter-spacing="1.2"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(title)}</text>

  <text x="{PAD}" y="70" fill="{TEXT}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(subtitle)}</text>

  <text x="{W-PAD}" y="70" text-anchor="end" fill="{MUTED}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(now)}</text>

  <!-- Panel -->
  <rect x="{frame_x}" y="{frame_y}" width="{frame_w}" height="{frame_h}" rx="12" fill="url(#panelGrad)" stroke="{GRID}" stroke-width="1"/>

  <!-- Grid (vertical freq, horizontal dB) -->
  {"".join([f'<line x1="{frame_x + frame_w*k/8:.2f}" y1="{frame_y}" x2="{frame_x + frame_w*k/8:.2f}" y2="{frame_y + frame_h}" stroke="{GRID_SOFT}" stroke-width="1" opacity="0.55"/>'
            for k in range(1, 8)])}

  {"".join([f'<line x1="{frame_x}" y1="{frame_y + frame_h*k/6:.2f}" x2="{frame_x + frame_w}" y2="{frame_y + frame_h*k/6:.2f}" stroke="{GRID_SOFT}" stroke-width="1" opacity="0.55"/>'
            for k in range(1, 6)])}

  <!-- Axis labels -->
  <!-- dB labels (kept inside plot area, aligned) -->
  <text x="{frame_x + 8}" y="{frame_y + 14}" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(db_top)}</text>
  <text x="{frame_x + 8}" y="{frame_y + frame_h/2 + 4:.2f}" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(db_mid)}</text>
  <text x="{frame_x + 8}" y="{frame_y + frame_h - 8:.2f}" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(db_bot)}</text>

  <text x="{frame_x}" y="{frame_y + frame_h + 18}" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(f_left)}</text>
  <text x="{frame_x + frame_w/2:.2f}" y="{frame_y + frame_h + 18}" text-anchor="middle" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(f_mid)}</text>
  <text x="{frame_x + frame_w}" y="{frame_y + frame_h + 18}" text-anchor="end" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(f_right)}</text>

  <!-- Waterfall (animated scroll) -->
  <clipPath id="wfClip">
    <rect x="{frame_x}" y="{wf_y}" width="{frame_w}" height="{wf_h}" rx="10"/>
  </clipPath>

  <g clip-path="url(#wfClip)" opacity="0.78">
    <g>
      {"".join(wf_cells)}
      <animateTransform attributeName="transform" type="translate"
                        from="0 0" to="0 {cell_h:.2f}"
                        dur="1.2s" repeatCount="indefinite"/>
    </g>
  </g>

  <!-- Spectrum fill + trace -->
  <polygon points="{frame_x:.2f},{frame_y + frame_h:.2f} {pts} {frame_x + frame_w:.2f},{frame_y + frame_h:.2f}"
           fill="url(#specFill)" opacity="0.55"/>

  <polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="2.2" filter="url(#glow)" opacity="0.62"/>

  <!-- Peak marker -->
  <line x1="{peak_x:.2f}" y1="{frame_y}" x2="{peak_x:.2f}" y2="{frame_y + frame_h}" stroke="{ACCENT_DIM}" stroke-width="1.4" opacity="0.65" stroke-dasharray="4 6"/>
  <circle cx="{peak_x:.2f}" cy="{peak_y:.2f}" r="3.2" fill="{ACCENT}" opacity="0.85"/>

  <!-- HUD box (top-right) -->
  <g opacity="0.92">
    <rect x="{frame_x + frame_w - 290}" y="{frame_y + 10}" width="276" height="44"
          rx="8" fill="{BG}" opacity="0.55" stroke="{GRID}" stroke-width="1"/>
    <text x="{frame_x + frame_w - 18}" y="{frame_y + 28}" text-anchor="end" fill="{TEXT}" font-size="11"
          font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">
      MKR {esc(marker_freq)}  Δf {esc(df)}
    </text>
    <text x="{frame_x + frame_w - 18}" y="{frame_y + 44}" text-anchor="end" fill="{MUTED}" font-size="11"
          font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">
      Peak {peak_db:.1f} dB   Noise {noise_db:.1f} dB   SNR {snr:.1f} dB
    </text>
  </g>

  <!-- Footer identity (subtle, personal) -->
  <text x="{PAD}" y="{H-12}" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(callsign)}</text>

  <text x="{W-PAD}" y="{H-12}" text-anchor="end" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(build)}</text>

</svg>
'''
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    main()
