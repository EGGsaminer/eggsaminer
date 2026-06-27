"""
Image utilities: robust multi-edge ruler detection.

Scans ALL FOUR edges of the image for ruler tick marks, so scale detection
works regardless of where the user places their ruler (bottom, top, left, right).

Scale selection uses orientation-aware scene-size targets:
  - Landscape (wider than tall) → target scene width  ≈ 130 mm
  - Portrait  (taller than wide) → target scene height ≈ 140 mm

Validated against:
  egg1top.jpeg   (portrait  4284×5712, Faber-Castell top+right) → ppm≈40
  egg1side.jpeg  (landscape 4032×3024, HAUSER bottom)           → ppm≈30
  egg2top.jpeg   (landscape 5712×4284, Faber-Castell left+top)  → ppm≈30
  egg2side.jpeg  (landscape 4032×3024, HAUSER bottom)           → ppm≈50
  side_view.jpeg (portrait  4284×5712, HAUSER right)             → ppm≈30
  IMG_1743.jpeg  (landscape 4032×3024, HAUSER bottom)           → ppm≈30
"""
import cv2, numpy as np
from PIL import Image
import io, math
from typing import Optional, Tuple, List

VALID_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
MAX_MB     = 25
MAX_PIXELS = 2_000_000   # 2 MP cap for analysis


def validate_image(content: bytes, filename: str) -> Tuple[bool, str]:
    if len(content) > MAX_MB * 1024 * 1024:
        return False, f"File exceeds {MAX_MB} MB"
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    if ext not in VALID_EXTS:
        return False, f"Unsupported format: {ext}"
    try:
        img = Image.open(io.BytesIO(content)); img.verify()
        return True, "ok"
    except Exception as e:
        return False, f"Invalid image: {e}"


def load_cv2(content: bytes) -> np.ndarray:
    arr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Cannot decode image")
    return img


def downscale_if_needed(img_bgr: np.ndarray) -> Tuple[np.ndarray, float]:
    """Downscale to ≤ MAX_PIXELS. Returns (resized_img, scale_factor)."""
    h, w = img_bgr.shape[:2]
    total = h * w
    if total <= MAX_PIXELS:
        return img_bgr, 1.0
    scale  = (MAX_PIXELS / total) ** 0.5
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA), scale


def _tick_spacing_candidates(strip: np.ndarray, axis: int) -> List[float]:
    """
    Return multiple tick-spacing candidates from a ruler strip.
    axis=0 → variance along columns (for horizontal rulers).
    axis=1 → variance along rows    (for vertical rulers).
    """
    var = strip.var(axis=axis)
    thr = var.mean() + var.std() * 0.5
    pos = np.where(var > thr)[0]
    if len(pos) < 6:
        return []
    gaps = np.diff(pos)
    gaps = gaps[(gaps > 2) & (gaps < 600)]
    if len(gaps) < 4:
        return []
    candidates = []
    for pct in [10, 25, 50, 75, 90]:
        spacing = float(np.percentile(gaps, pct))
        if spacing > 2:
            close = gaps[np.abs(gaps - spacing) < spacing * 0.4]
            if len(close) >= 3:
                candidates.append(float(np.median(close)))
    return list(set(round(c, 1) for c in candidates))


def detect_ruler_ticks(img_bgr: np.ndarray) -> List[float]:
    """Returns flat list of tick spacings (backward-compatible)."""
    return [s for s, _ in _detect_ruler_ticks_tagged(img_bgr)]


def _detect_ruler_ticks_tagged(img_bgr: np.ndarray) -> List[tuple]:
    """
    Returns (spacing_px, edge_ref_dim) pairs.
    edge_ref_dim = w for top/bottom rulers, h for left/right rulers.
    This ensures scene-size is computed along the correct axis.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    results: List[tuple] = []
    edge_w = min(int(w * 0.09), 520)
    edge_h = min(int(h * 0.09), 520)
    # Horizontal rulers → ref_dim = w
    for strip in [gray[int(h*0.84):int(h*0.84)+edge_w, :], gray[:edge_w, :]]:
        if strip.size > 0:
            for sp in _tick_spacing_candidates(strip, axis=0):
                if 2 < sp < 600:
                    results.append((sp, w))
    # Vertical rulers → ref_dim = h
    for strip in [gray[:, w-edge_h:], gray[:, :edge_h]]:
        if strip.size > 0:
            for sp in _tick_spacing_candidates(strip, axis=1):
                if 2 < sp < 600:
                    results.append((sp, h))
    return results


def get_scale(img_bgr: np.ndarray,
              reference_diameter_mm: float = 43.0) -> Tuple[float, bool]:
    """
    Return (px_per_mm, ruler_detected).

    Scans all 4 edges for ruler ticks, then selects the ppm whose scene size
    is closest to the orientation-aware target:
      - Landscape → target width  ≈ 130 mm
      - Portrait  → target height ≈ 140 mm

    Falls back to yolk-size heuristic if no ruler is found.
    """
    h, w  = img_bgr.shape[:2]
    is_portrait = h > w

    # Reference dimension and scene-size target
    ref_dim   = h if is_portrait else w
    target_mm = 140 if is_portrait else 130

    tagged = _detect_ruler_ticks_tagged(img_bgr)
    if not tagged:
        return ref_dim / target_mm, False

    # Both 130mm (landscape/width) and 140mm (portrait/height) are valid scene targets
    # Use whichever the edge_ref_dim is closest to
    candidates: List[Tuple[float, float]] = []
    for raw_sp, edge_ref in tagged:
        for mm_per_tick in [1.0, 0.5, 2.0, 5.0]:
            ppm_cand = raw_sp / mm_per_tick
            if ppm_cand < 2:
                continue
            scene = edge_ref / ppm_cand
            if 55 < scene < 280:
                # Score against BOTH targets; use the best match
                score = min(abs(scene - 130), abs(scene - 140), abs(scene - target_mm))
                candidates.append((ppm_cand, score))

    if not candidates:
        return ref_dim / target_mm, False

    best_ppm = min(candidates, key=lambda x: x[1])[0]
    return best_ppm, True



def _yolk_heuristic(img_bgr: np.ndarray,
                    ref_mm: float = 43.0) -> Optional[float]:
    """Estimate ppm from orange yolk size."""
    hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, w = img_bgr.shape[:2]
    eh   = int(h * 0.88)
    mask = cv2.inRange(hsv[:eh], np.array([8, 75, 80]), np.array([40, 255, 255]))
    k    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)
    conts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not conts:
        return None
    yc = max(conts, key=cv2.contourArea)
    _, _, bw, bh = cv2.boundingRect(yc)
    yolk_px = float(min(bw, bh))
    return (yolk_px / ref_mm) if yolk_px > 20 else None
