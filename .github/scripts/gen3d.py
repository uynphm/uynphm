"""Draw the last year of GitHub contributions as a horizontal 3D strip.

Usage: python3 gen3d.py contributions.json out_dir
contributions.json is the output of the GraphQL query in .github/workflows/3d-contrib.yml.
Writes out_dir/contrib-3d.svg (light) and out_dir/contrib-3d-dark.svg (dark).
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
# file name: (bar colors by level, number color, label color)
THEMES = {
    "contrib-3d.svg": (["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "#1f2328", "#59636e"),
    "contrib-3d-dark.svg": (["#2a3038", "#0e4429", "#006d32", "#26a641", "#39d353"], "#e6edf3", "#9198a1"),
}
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
HEADER = 28  # room for the total above the bars

STEP = 14  # one week along x
TILE = 12  # bar width
DX, DY = 6, 7  # one weekday back into the picture
TD = 0.8  # bar depth, as a share of one weekday row
PAD = 6


def shade(hex_color: str, k: float) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (round(r * k), round(g * k), round(b * k))


def bar_height(count: int) -> float:
    return 2.0 if count == 0 else 4 + math.log10(count / 4 + 1) * 38


def render(weeks: list, total: int, colors: list[str], strong: str, muted: str) -> str:
    days = []
    for w, week in enumerate(weeks):
        for d in week["contributionDays"]:
            dow = (date.fromisoformat(d["date"][:10]).weekday() + 1) % 7  # Sunday = 0
            days.append((w, 6 - dow, d["contributionCount"], LEVELS[d["contributionLevel"]], d["date"][:10]))

    tall = max(bar_height(c) for *_, c, _, _ in days)
    width = PAD * 2 + len(weeks) * STEP + 6 * DX + DX * TD
    height = HEADER + PAD * 2 + tall + 6 * DY + DY * TD
    base = height - PAD
    dx, dy = DX * TD, DY * TD

    css = [
        ".b{animation:rise .8s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box;transform-origin:50% 100%}",
        "@keyframes rise{from{transform:scaleY(0)}}",
        "@media (prefers-reduced-motion:reduce){.b{animation:none}}",
        f".n{{font:600 16px {FONT};fill:{strong}}}.l{{font:400 14px {FONT};fill:{muted}}}",
    ]
    for lv, c in enumerate(colors):
        css.append(f".t{lv}{{fill:{c}}}.f{lv}{{fill:{shade(c, 0.85)}}}.s{lv}{{fill:{shade(c, 0.7)}}}")

    bars = []
    # Back rows first, left to right, so nearer bars paint over farther ones.
    for w, depth, count, lv, day in sorted(days, key=lambda t: (-t[1], t[0])):
        h = bar_height(count)
        x = PAD + w * STEP + depth * DX
        y = base - depth * DY
        top = f"{x:.1f},{y - h:.1f} {x + TILE:.1f},{y - h:.1f} {x + TILE + dx:.1f},{y - h - dy:.1f} {x + dx:.1f},{y - h - dy:.1f}"
        side = f"{x + TILE:.1f},{y:.1f} {x + TILE + dx:.1f},{y - dy:.1f} {x + TILE + dx:.1f},{y - h - dy:.1f} {x + TILE:.1f},{y - h:.1f}"
        label = f"{count} contribution{'s' if count != 1 else ''} on {day}"
        bars.append(
            f'<g class="b" style="animation-delay:{w * 18}ms"><title>{label}</title>'
            f'<rect class="f{lv}" x="{x:.1f}" y="{y - h:.1f}" width="{TILE}" height="{h:.1f}"/>'
            f'<polygon class="s{lv}" points="{side}"/><polygon class="t{lv}" points="{top}"/></g>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}" role="img" aria-label="3D contribution graph">'
        f"<style>{''.join(css)}</style>"
        f'<text x="{PAD}" y="{PAD + 14}"><tspan class="n">{total:,}</tspan>'
        f'<tspan class="l"> contributions in the last year</tspan></text>'
        f"{''.join(bars)}</svg>"
    )


def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text())
    calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, (colors, strong, muted) in THEMES.items():
        (out / name).write_text(render(calendar["weeks"], calendar["totalContributions"], colors, strong, muted))


if __name__ == "__main__":
    main()
