import os
import datetime
import hashlib


OUT_PATH = os.environ.get("OUT_PATH", "assets/operator_id.svg")

# Theme (aligned with GitHub dark + neon accent)
BG = "#0D1117"
PANEL = "#0B1220"
GRID = "#1F2937"
TEXT = "#9CA3AF"
MUTED = "#6B7280"
ACCENT = "#22C55E"

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


def checksum(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest().upper()
    return h[:10]


def main() -> None:
    user = os.environ.get("GH_USER") or os.environ.get("GITHUB_ACTOR") or "Naveenkumar-026"
    callsign = os.environ.get("CALLSIGN") or "SILENCIO"

    # Keep it short and timeless; avoid claims.
    role = os.environ.get("OP_ROLE") or "Systems security · intelligence · autonomy"
    build = os.environ.get("BUILD_CHANNEL") or "MAIN"
    mode = os.environ.get("MODE") or "PUBLIC"

    now_utc = datetime.datetime.utcnow().replace(microsecond=0)
    ts = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    cs = checksum(callsign, user, now_utc.strftime("%Y-%m-%d"))

    # Layout
    x0 = PAD
    y0 = PAD
    w0 = W - PAD * 2
    h0 = H - PAD * 2

    # Field column positions
    col1_x = x0 + 28
    col2_x = x0 + int(w0 * 0.54)
    row_y = y0 + 78
    row_gap = 26

    def field(x: int, y: int, k: str, v: str) -> str:
        return (
            f'<text x="{x}" y="{y}" fill="{MUTED}" font-size="12" '
            f'font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">'
            f'{esc(k)}</text>\n'
            f'<text x="{x+120}" y="{y}" fill="{TEXT}" font-size="12" '
            f'font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">'
            f'{esc(v)}</text>'
        )

    # Subtle grid
    grid_lines = []
    for i in range(1, 10):
        gx = x0 + int(w0 * i / 10)
        grid_lines.append(
            f'<line x1="{gx}" y1="{y0}" x2="{gx}" y2="{y0+h0}" stroke="{GRID}" stroke-opacity="0.35" stroke-width="1" />'
        )
    for i in range(1, 6):
        gy = y0 + int(h0 * i / 6)
        grid_lines.append(
            f'<line x1="{x0}" y1="{gy}" x2="{x0+w0}" y2="{gy}" stroke="{GRID}" stroke-opacity="0.28" stroke-width="1" />'
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

  <!-- Background -->
  <rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>
  <rect x="{x0}" y="{y0}" width="{w0}" height="{h0}" rx="{R}" fill="url(#panel)" stroke="{GRID}" stroke-opacity="0.7" />
  <rect x="{x0+10}" y="{y0+10}" width="{w0-20}" height="{h0-20}" rx="{R-6}" fill="none" stroke="{GRID}" stroke-opacity="0.35" />

  <!-- Accent spine -->
  <rect x="{x0}" y="{y0}" width="3" height="{h0}" fill="{ACCENT}" filter="url(#glow)" />

  <!-- Grid -->
  {''.join(grid_lines)}

  <!-- Header -->
  <text x="{col1_x}" y="{y0+34}" fill="{TEXT}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">OPERATOR ID // ACTIVE</text>

  <text x="{x0+w0-28}" y="{y0+34}" text-anchor="end" fill="{MUTED}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(ts)}</text>

  <!-- Status pill -->
  <rect x="{x0+w0-210}" y="{y0+50}" width="182" height="24" rx="12" fill="none" stroke="{GRID}" stroke-opacity="0.65" />
  <circle cx="{x0+w0-194}" cy="{y0+62}" r="4" fill="{ACCENT}" filter="url(#glow)" />
  <text x="{x0+w0-184}" y="{y0+66}" fill="{TEXT}" font-size="12"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">STATUS: ONLINE</text>

  <!-- Callsign -->
  <text x="{col1_x}" y="{y0+70}" fill="{ACCENT}" font-size="18" filter="url(#glow)"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">{esc(callsign)}</text>

  <!-- Fields -->
  {field(col1_x, row_y, 'HANDLE:', user)}
  {field(col1_x, row_y + row_gap, 'ROLE:', role)}
  {field(col1_x, row_y + row_gap*2, 'BUILD:', build)}

  {field(col2_x, row_y, 'MODE:', mode)}
  {field(col2_x, row_y + row_gap, 'CHECKSUM:', cs)}
  {field(col2_x, row_y + row_gap*2, 'TIMEBASE:', 'UTC')}

  <!-- Footer microtext -->
  <text x="{col1_x}" y="{y0+h0-16}" fill="{MUTED}" font-size="11"
        font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">Structure precedes implementation.</text>
</svg>
'''

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
