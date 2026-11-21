"""Image pre-processing for receipts: grayscale, denoise, contrast, deskew."""
import cv2
import numpy as np


def deskew(gray: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """Estimate the dominant text angle from the minimum-area rectangle of dark pixels and rotate."""
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if len(coords) < 50:
        return gray
    angle = cv2.minAreaRect(coords[:, ::-1].astype(np.float32))[-1]
    if angle > 45:
        angle -= 90
    if abs(angle) < 0.3 or abs(angle) > max_angle:
        return gray
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess(img_bgr: np.ndarray, min_width: int = 800) -> np.ndarray:
    """Return a cleaned 3-channel image (OCR engines expect BGR/RGB input)."""
    h, w = img_bgr.shape[:2]
    if w < min_width:  # small phone crops: upscale so characters are tall enough for recognition
        f = min_width / w
        img_bgr = cv2.resize(img_bgr, (min_width, int(h * f)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    gray = deskew(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
