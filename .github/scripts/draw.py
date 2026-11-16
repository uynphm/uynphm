"""Draw the profile stats images from fetch_stats.py output.

Usage: python3 draw.py stats.json out_dir
Writes activity.svg (weekly contributions chart + activity radar) to out_dir, with a -dark twin.
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
WIDTH = 795

# file suffix: theme colors
THEMES = {
    "": {
        "strong": "#1f2328", "muted": "#59636e", "line": "#d1d9e0", "accent": "#6a45bf",
    },
    "-dark": {
        "strong": "#e6edf3", "muted": "#9198a1", "line": "#3d444d", "accent": "#b08cfa",
    },
}


def fmt_day(iso: str, year: bool = False) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%b %-d, %Y") if year else d.strftime("%b %-d")


def svg(height: int, label: str, css: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'role="img" aria-label="{label}"><style>{css}</style>{body}</svg>'
    )


RADAR_AXES = [("Commit", "commits"), ("Issue", "issues"), ("PullReq", "prs"), ("Review", "reviews"), ("Active days", "active_days")]
RINGS = 3  # log scale, relative to the largest value, so the biggest axis reaches the edge


def render_activity(stats: dict, c: dict) -> str:
    parts = []

    # Weekly contributions as a smooth area chart, total in the title
    weeks = stats["weeks"]
    x0, x1, top, base = 20, 380, 62, 196
    peak = max(w["count"] for w in weeks) or 1
    pts = [(x0 + i * (x1 - x0) / (len(weeks) - 1), base - w["count"] / peak * (base - top)) for i, w in enumerate(weeks)]
    curve = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):  # Catmull-Rom through the points, as cubic Beziers
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, min(base, p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, min(base, p2[1] - (p3[1] - p1[1]) / 6))
        curve += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    parts.append(
        f'<defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{c["accent"]}" stop-opacity=".45"/>'
        f'<stop offset="1" stop-color="{c["accent"]}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="reveal"><rect x="0" y="0" width="0" height="{base + 1}">'
        f'<animate attributeName="width" from="0" to="{x1 + 10}" dur="1.2s" fill="freeze"/></rect></clipPath></defs>'
    )
    parts.append(
        f'<g clip-path="url(#reveal)"><path d="{curve} L{x1},{base} L{x0},{base} Z" fill="url(#fade)"/>'
        f'<path d="{curve}" fill="none" stroke="{c["accent"]}" stroke-width="2" stroke-linejoin="round"/></g>'
    )
    parts.append(f'<line x1="{x0}" y1="{base + 0.5}" x2="{x1}" y2="{base + 0.5}" stroke="{c["line"]}"/>')
    seen = set()
    for i, w in enumerate(weeks):  # a month label at the first week of every other month
        d = date.fromisoformat(w["start"])
        if d.month % 2 == 0 and d.month not in seen and 0 < i < len(weeks) - 2:
            seen.add(d.month)
            parts.append(f'<text x="{pts[i][0]:.1f}" y="{base + 18}" text-anchor="middle" class="d">{d.strftime("%b")}</text>')
    parts.append(
        f'<text x="{x0}" y="26"><tspan class="v">{stats["total"]:,} </tspan><tspan class="a">contributions</tspan></text>'
    )
    window = f"{fmt_day(stats['since'], year=True)} \u2013 {fmt_day(stats['until'], year=True)}"
    parts.append(f'<text x="{WIDTH / 2:.0f}" y="250" text-anchor="middle" class="d">{window}</text>')

    # Activity radar
    R, rx, ry = 80, 590, 118

    def point(i: int, rad: float) -> tuple[float, float]:
        a = -math.pi / 2 + i * 2 * math.pi / len(RADAR_AXES)
        return rx + rad * math.cos(a), ry + rad * math.sin(a)

    top = math.log10(max(stats[k] for _, k in RADAR_AXES) + 1) or 1

    def radius(v: int) -> float:
        return R * math.log10(v + 1) / top

    for k in range(1, RINGS + 1):
        ring = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, R * k / RINGS) for i in range(len(RADAR_AXES))))
        parts.append(f'<polygon points="{ring}" fill="none" stroke="{c["muted"]}" stroke-opacity=".35" stroke-dasharray="3 3"/>')
    for i, (label, key) in enumerate(RADAR_AXES):
        x, y = point(i, R)
        parts.append(f'<line x1="{rx}" y1="{ry}" x2="{x:.1f}" y2="{y:.1f}" stroke="{c["muted"]}" stroke-opacity=".35"/>')
        lx, ly = point(i, R + 26)
        anchor = "middle" if abs(lx - rx) < 5 else ("start" if lx > rx else "end")
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" dominant-baseline="middle">'
            f'<tspan class="a">{label} </tspan><tspan class="v">{stats[key]:,}</tspan></text>'
        )
    shape = " ".join(f"{x - rx:.1f},{y - ry:.1f}" for x, y in (point(i, radius(stats[k])) for i, (_, k) in enumerate(RADAR_AXES)))
    parts.append(
        f'<g transform="translate({rx} {ry})"><g>'
        '<animateTransform attributeName="transform" type="scale" from="0" to="1" dur=".8s" fill="freeze"/>'
        f'<polygon points="{shape}" fill="{c["accent"]}" fill-opacity=".3" stroke="{c["accent"]}" stroke-width="2" stroke-linejoin="round"/>'
        "</g></g>"
    )

    css = (
        f".a{{font:400 14px {FONT};fill:{c['muted']}}}.v{{font:600 14px {FONT};fill:{c['strong']}}}"
        f".d{{font:400 12px {FONT};fill:{c['muted']}}}"
    )
    return svg(258, "Contributions and activity in the last year", css, "".join(parts))


def main() -> None:
    stats = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for suffix, colors in THEMES.items():
        (out / f"activity{suffix}.svg").write_text(render_activity(stats, colors))


if __name__ == "__main__":
    main()
