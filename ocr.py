"""Text detection + recognition backends. Each returns a list of Word(text, box, conf)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Word:
    text: str
    box: tuple[float, float, float, float]   # x1, y1, x2, y2
    conf: float


class PaddleBackend:
    """PaddleOCR: DB text detection followed by CRNN/SVTR recognition."""

    def __init__(self, lang: str = "en"):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def __call__(self, img: np.ndarray) -> list[Word]:
        result = self.ocr.ocr(img, cls=True)
        words = []
        for quad, (text, conf) in (result[0] or []):
            xs, ys = [p[0] for p in quad], [p[1] for p in quad]
            words.append(Word(text.strip(), (min(xs), min(ys), max(xs), max(ys)), float(conf)))
        return [w for w in words if w.text]


class TesseractBackend:
    """Tesseract LSTM: detection and recognition in one call, word-level boxes."""

    def __init__(self, lang: str = "eng+fra"):
        import pytesseract
        self.pt = pytesseract
        self.lang = lang

    def __call__(self, img: np.ndarray) -> list[Word]:
        d = self.pt.image_to_data(img, lang=self.lang, config="--psm 6", output_type=self.pt.Output.DICT)
        words = []
        for i, text in enumerate(d["text"]):
            conf = float(d["conf"][i])
            if text.strip() and conf >= 0:
                x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
                words.append(Word(text.strip(), (x, y, x + w, y + h), conf / 100))
        return words


def get_backend(name: str, lang: str | None = None):
    if name == "paddle":
        return PaddleBackend(lang or "en")
    if name == "tesseract":
        return TesseractBackend(lang or "eng+fra")
    raise ValueError(f"unknown backend {name}")
