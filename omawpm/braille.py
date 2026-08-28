"""btop-style braille graphs: two samples per cell, five vertical levels."""

from __future__ import annotations

# Left level (rows) × right level (cols). Empty cell is braille blank, not space,
# so a proportional UI font still reserves a slot.
BRAILLE_5X5 = (
    ("⠀", "⢀", "⢠", "⢰", "⢸"),
    ("⡀", "⣀", "⣠", "⣰", "⣸"),
    ("⡄", "⣄", "⣤", "⣴", "⣼"),
    ("⡆", "⣆", "⣦", "⣶", "⣾"),
    ("⡇", "⣇", "⣧", "⣷", "⣿"),
)


def trim_leading_zeros(points: list[float], pad: int = 2) -> tuple[list[float], int]:
    values = [max(0.0, float(v or 0)) for v in points]
    start = 0
    while start < len(values) and values[start] <= 0:
        start += 1
    if start >= len(values):
        return values, 0
    start = max(0, start - pad)
    return values[start:], start


def downsample_max(points: list[float], n: int) -> list[float]:
    if n <= 0:
        return []
    values = [max(0.0, float(v or 0)) for v in points]
    if not values:
        return [0.0] * n
    if len(values) >= n:
        out: list[float] = []
        for i in range(n):
            start = int(i * len(values) / n)
            end = max(start + 1, int((i + 1) * len(values) / n))
            out.append(max(values[start:end]))
        return out
    pad = n - len(values)
    return [0.0] * pad + values


def _level(value: float, lo: float, hi: float) -> int:
    if value <= lo:
        return 0
    if value >= hi:
        return 4
    span = hi - lo
    if span <= 0:
        return 4
    return int(round((value - lo) / span * 4))


def braille_graph(
    points: list[float],
    cols: int,
    rows: int,
    peak: float | None = None,
) -> list[str]:
    cols = max(1, int(cols))
    rows = max(1, int(rows))
    trimmed, _ = trim_leading_zeros(points)
    samples = downsample_max(trimmed, cols * 2)
    if peak is None:
        peak = max(samples) if samples else 0.0
    peak = max(float(peak or 0.0), 0.01)
    norm = [min(1.0, v / peak) for v in samples]
    lines: list[str] = []
    for row in range(rows):
        lo = (rows - 1 - row) / rows
        hi = (rows - row) / rows
        chars: list[str] = []
        for col in range(cols):
            left = _level(norm[col * 2], lo, hi)
            right = _level(norm[col * 2 + 1], lo, hi)
            chars.append(BRAILLE_5X5[left][right])
        lines.append("".join(chars))
    return lines
