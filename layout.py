"""Group word boxes into reading-order lines (receipts are column-aligned: NAME ...... PRICE)."""
from __future__ import annotations

from dataclasses import dataclass

from ocr import Word


@dataclass
class Line:
    text: str
    conf: float          # minimum word confidence on the line
    y: float


def _v_overlap(a: Word, b: Word) -> float:
    top, bottom = max(a.box[1], b.box[1]), min(a.box[3], b.box[3])
    h = min(a.box[3] - a.box[1], b.box[3] - b.box[1])
    return max(0.0, bottom - top) / h if h > 0 else 0.0


def group_lines(words: list[Word], min_overlap: float = 0.5) -> list[Line]:
    """Words whose vertical extents overlap by > min_overlap belong to the same line."""
    rows: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.box[1] + w.box[3]) / 2):
        for row in rows:
            if _v_overlap(row[-1], w) > min_overlap:
                row.append(w)
                break
        else:
            rows.append([w])
    lines = []
    for row in rows:
        row.sort(key=lambda w: w.box[0])
        lines.append(Line(" ".join(w.text for w in row), min(w.conf for w in row),
                          sum((w.box[1] + w.box[3]) / 2 for w in row) / len(row)))
    return sorted(lines, key=lambda l: l.y)
