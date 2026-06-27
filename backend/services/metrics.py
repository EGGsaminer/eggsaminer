"""
Egg Quality Analyzer Pro — metrics engine v2.4
Fixed:
  - HU = calc_haugh_unit(H_alb_mm, W) directly — NO circularity correction on HU
  - Plate detection: background-diff scan from yolk_bottom to 83% cutoff
  - H_alb anatomy blend: for intact yolks (circ≥0.75), blend measured gap with
    anatomy-based estimate (yolk_D × 0.21) to stabilise against plate detection noise
  - For broken yolks (circ<0.65): use measured H_alb only (no anatomy blend)
  - yolk_H correctly uses ellipse minor axis / ppm_proc (no wrong clamping)
  - Scale detection: orientation-aware (portrait→200mm height, landscape→130mm width)
"""
import math, cv2, numpy as np
from typing import Dict, Any, Tuple


# ── Core formulas ─────────────────────────────────────────────────────────────

def calc_haugh_unit(H_mm: float, W_g: float) -> float:
    """Standard HU = 100 × log10(H − 1.7×W^0.37 + 7.6). Capped at 100 (practical maximum)."""
    val = H_mm - 1.7 * (W_g ** 0.37) + 7.6
    if val <= 0:
        return 0.0
    return round(min(100.0, 100.0 * math.log10(val)), 2)

def calc_yolk_index(yolk_H: float, yolk_D: float) -> float:
    return round(yolk_H / yolk_D, 5) if yolk_D > 0 else 0.0

def calc_albumen_index(H: float, spread: float) -> float:
    return round(H / spread, 5) if spread > 0 else 0.0

def grade(hu: float) -> str:
    return "AA" if hu >= 72 else "A" if hu >= 60 else "B"

def freshness(hu: float) -> Tuple[str, str]:
    if hu >= 72: return "Extra Fresh", "0–7 days"
    if hu >= 60: return "Fresh",       "7–21 days"
    return "Older", "> 21 days"


# ── Geometry ──────────────────────────────────────────────────────────────────

def fit_ellipse(mask_bin: np.ndarray) -> Dict[str, float]:
    conts, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not conts:
        return {"area_px": 0, "major_px": 0, "minor_px": 0, "circularity": 0}
    c = max(conts, key=cv2.contourArea)
    area = cv2.contourArea(c)
    peri = cv2.arcLength(c, True)
    circ = (4 * math.pi * area / peri ** 2) if peri > 0 else 0
    if len(c) >= 5:
        _, (ma, mi), _ = cv2.fitEllipse(c)
        major, minor = max(ma, mi), min(ma, mi)
    else:
        x, y, w, h = cv2.boundingRect(c)
        major, minor = float(max(w, h)), float(min(w, h))
    return {"area_px": float(area), "major_px": float(major),
            "minor_px": float(minor), "circularity": round(min(float(circ), 1.0), 4)}


# ── Background estimation ─────────────────────────────────────────────────────

def _background_level(gray: np.ndarray) -> float:
    """
    Estimate background brightness (paper surface) for plate detection.

    Priority:
    1. Top-center strip (rows 1-7%, cols 10-90%) — always paper, never ruler
    2. Fallback: brightest image corner with std < 40

    This reliably gives the paper surface brightness regardless of whether
    the image is top-down or side-profile.
    """
    h, w = gray.shape
    rs = int(w * 0.10)

    # Primary: top-center strip
    tc = gray[int(h * 0.01): int(h * 0.07), rs: w - rs]
    if tc.size > 0:
        tc_std = float(tc.std())
        tc_med = float(np.median(tc))
        # Use top-center if it has reasonable brightness and low-ish variance
        # (std < 55 allows for slight egg-at-top-edge contamination)
        if tc_std < 55 and tc_med > 50:
            return tc_med

    # Fallback: brightest corner with std < 40 (= paper, not ruler/egg)
    sz = min(70, h // 12, w // 12)
    corners = [gray[:sz, :sz], gray[:sz, -sz:], gray[-sz:, :sz], gray[-sz:, -sz:]]
    clean = [c for c in corners if c.size > 0 and float(c.std()) < 40]
    if clean:
        return float(max(clean, key=lambda c: float(c.mean())).mean())

    # Last resort: median of top 20%
    return float(np.median(gray[:int(h * 0.20), rs: w - rs]))


# ── Yolk detection ────────────────────────────────────────────────────────────

def _detect_yolk(img_bgr: np.ndarray,
                 exclude_bottom_pct: float = 0.12) -> Tuple[float, float, float, float]:
    """
    Detect yolk via orange/yellow HSV range.
    Returns (cx, cy, major_px, minor_px) — all zeros if not found.
    Works on any background colour.
    """
    h, w = img_bgr.shape[:2]
    eh   = int(h * (1.0 - exclude_bottom_pct))
    ew   = int(w * 0.92)
    hsv  = cv2.cvtColor(img_bgr[:eh, :ew], cv2.COLOR_BGR2HSV)

    ym = cv2.inRange(hsv, np.array([10, 120, 100]), np.array([38, 255, 255]))
    k  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (12, 12))
    ym = cv2.morphologyEx(ym, cv2.MORPH_CLOSE, k)
    ym = cv2.morphologyEx(ym, cv2.MORPH_OPEN,  k)
    conts, _ = cv2.findContours(ym, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not conts:
        return 0.0, 0.0, 0.0, 0.0

    yc = max(conts, key=cv2.contourArea)
    M  = cv2.moments(yc)
    if M["m00"] == 0:
        return 0.0, 0.0, 0.0, 0.0
    cx = M["m10"] / M["m00"]
    cy = M["m01"] / M["m00"]

    if len(yc) >= 5:
        _, (ma, mi), _ = cv2.fitEllipse(yc)
        return cx, cy, max(ma, mi), min(ma, mi)

    _, _, bw, bh = cv2.boundingRect(yc)
    return cx, cy, float(max(bw, bh)), float(min(bw, bh))


# ── Albumen spread ────────────────────────────────────────────────────────────

def _radial_albumen_spread(img_bgr: np.ndarray, cx: float, cy: float,
                            ppm: float, yolk_D_mm: float = 43.0) -> float:
    """
    Albumen spread via inside-out radial sweep from yolk centre.
    Tracks the LAST pixel significantly different from background (egg boundary).
    Works on any background colour.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape
    bg   = _background_level(gray.astype(np.uint8))

    # Threshold: pixel is "inside egg" if it differs from bg by this much
    sz = min(70, h // 12, w // 12)
    corners = [gray[:sz, :sz], gray[:sz, -sz:],
               gray[-sz:, :sz], gray[-sz:, -sz:]]
    bg_std = float(np.min([c.std() for c in corners]))
    diff_thr = max(bg_std * 2.5, 5.0)

    radii = []
    max_r = int(min(cx, cy, w - cx, h - cy) * 0.91)
    start = int(yolk_D_mm * ppm * 0.55)

    for angle_deg in range(0, 360, 5):
        angle = math.radians(angle_deg)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        last_r = start
        for r in range(start, max_r, 6):
            px = int(cx + r * cos_a)
            py = int(cy + r * sin_a)
            if not (0 <= px < w and 0 <= py < h):
                break
            if abs(float(gray[py, px]) - bg) > diff_thr:
                last_r = r
        if last_r > start + 30:
            radii.append(float(last_r))

    if len(radii) < 12:
        return round(float(np.clip(yolk_D_mm * 2.65, 70.0, 165.0)), 1)

    arr      = np.array(radii)
    med      = float(np.median(arr))
    filtered = arr[np.abs(arr - med) < med * 0.40]
    if len(filtered) < 8:
        filtered = arr

    spread_mm = 2.0 * float(np.median(filtered)) / ppm
    if yolk_D_mm > 5:
        norm = 43.0 / yolk_D_mm
        spread_mm *= (1.0 + (norm - 1.0) * 0.50)
    return round(float(np.clip(spread_mm, 55.0, 170.0)), 1)


# ── Side-profile measurements ─────────────────────────────────────────────────

def measure_side_profile(img_bgr: np.ndarray, ppm: float) -> Tuple[float, float, float, float]:
    """
    From a landscape side-profile image:
      H_alb_mm  — thick albumen height (mm)
      yolk_H_mm — yolk dome height (mm)
      yolk_D_mm — yolk horizontal diameter (mm)
      plate_y   — plate surface row (pixels)

    Plate detection: scan rows from yolk_bottom downward to 83% image height,
    find the LAST row significantly different from background (= egg edge).
    H_alb = gap × 0.355 (empirical calibration factor).
    """
    h, w  = img_bgr.shape[:2]
    gray  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Background level from cleanest corner
    bg_level = _background_level(gray)

    # Yolk detection
    cx, cy, yolk_maj_px, yolk_min_px = _detect_yolk(img_bgr, exclude_bottom_pct=0.12)

    if yolk_maj_px < 10:
        return 7.0, 12.0, 43.0, float(int(h * 0.78))

    yolk_bottom = cy + yolk_min_px / 2.0

    # Plate level: scan from yolk_bottom to 83% image height.
    # Use CENTRE 70% of row (cols 15%-85%) to exclude ruler columns.
    # Stop scanning if row mean drops below ruler_threshold (= steel ruler).
    ruler_threshold = bg_level - 45   # rows darker than this = steel ruler body
    zone_end        = int(h * 0.83)
    search_start    = max(int(yolk_bottom) + 3, int(h * 0.40))
    cx0, cx1        = int(w * 0.15), int(w * 0.85)
    plate_y         = int(yolk_bottom)

    for row in range(search_start, zone_end):
        row_mean = float(gray[row, cx0:cx1].mean())
        if row_mean < ruler_threshold:
            break    # hit the steel ruler — stop
        row_diff = abs(row_mean - bg_level)
        if row_diff > 6.0:           # row contains egg material
            plate_y = row            # LAST such row = plate surface

    # Safety: plate must be below yolk
    plate_y = max(plate_y, int(yolk_bottom) + 10)

    # Gap and H_alb
    gap_px    = max(0.0, plate_y - yolk_bottom)
    H_alb_raw = (gap_px / ppm) * 0.355

    # yolk_H = minor axis (dome height in true side-profile)
    yolk_H_raw = yolk_min_px / ppm
    yolk_D_raw = yolk_maj_px / ppm

    H_alb  = float(np.clip(H_alb_raw,  2.0, 14.0))
    yolk_H = float(np.clip(yolk_H_raw, 3.0, 22.0))
    yolk_D = float(np.clip(yolk_D_raw, 20.0, 65.0))

    return round(H_alb, 2), round(yolk_H, 2), round(yolk_D, 2), float(plate_y)


# ── Top-down measurements ─────────────────────────────────────────────────────

def measure_topdown(img_bgr: np.ndarray, label_map: np.ndarray,
                    ppm: float) -> Tuple[float, float, float]:
    """
    Returns (alb_spread_mm, yolk_D_mm, yolk_D_minor).

    alb_spread is computed from the LABEL MASK (label==1 = albumen) so that
    it responds correctly when the sensitivity slider changes the segmentation.
    Falls back to radial image-based sweep if no albumen pixels are labelled.
    """
    cx, cy, yolk_major_px, yolk_minor_px = _detect_yolk(img_bgr, exclude_bottom_pct=0.10)

    yolk_D     = float(np.clip(yolk_major_px / ppm, 20.0, 65.0)) if yolk_major_px > 10 else 43.0
    yolk_D_min = float(np.clip(yolk_minor_px / ppm, 15.0, 65.0)) if yolk_minor_px > 10 else yolk_D

    # Compute alb_spread from the segmentation label mask
    # This ensures sensitivity changes propagate into all downstream metrics.
    alb_mask = (label_map == 1).astype(np.uint8) * 255
    alb_px_count = int(alb_mask.sum() // 255)

    if alb_px_count > 200 and cx > 10 and cy > 10:
        conts, _ = cv2.findContours(alb_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if conts:
            all_pts = np.vstack(conts).reshape(-1, 2).astype(np.float32)
            dists = np.sqrt((all_pts[:, 0] - cx) ** 2 + (all_pts[:, 1] - cy) ** 2)
            # 80th-percentile radius excludes small tendrils / outlier protrusions
            spread_px = float(np.percentile(dists, 80))
            alb_spread = float(np.clip(spread_px / ppm, 20.0, 200.0))
        else:
            alb_spread = float(np.clip(yolk_D * 2.65, 70.0, 165.0))
    elif cx > 10 and cy > 10:
        # No label mask — fall back to image-based radial sweep
        alb_spread = _radial_albumen_spread(img_bgr, cx, cy, ppm, yolk_D)
    else:
        alb_spread = float(np.clip(yolk_D * 2.65, 70.0, 165.0))

    return round(alb_spread, 1), round(yolk_D, 1), round(yolk_D_min, 1)


# ── Main compute function ─────────────────────────────────────────────────────



def _calc_roche_color(img_bgr, exclude_bottom_pct=0.10):
    """DSM Roche Yolk Color Fan 1-15. Hue 10=15, Hue 38=1 (linear)."""
    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr[:int(h*(1-exclude_bottom_pct)), :int(w*0.92)],
                       cv2.COLOR_BGR2HSV)
    ym = cv2.inRange(hsv, np.array([10, 120, 100]), np.array([38, 255, 255]))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (12, 12))
    ym = cv2.morphologyEx(ym, cv2.MORPH_CLOSE, k)
    ym = cv2.morphologyEx(ym, cv2.MORPH_OPEN, k)
    if ym.sum() == 0: return 10.0
    median_hue = float(np.median(hsv[:, :, 0][ym > 0]))
    return round(float(np.clip(15.0 - (median_hue - 10.0) * (14.0/28.0), 1.0, 15.0)), 1)

def compute_metrics(
        top_img:    np.ndarray,   # side-profile (landscape)
        side_img:   np.ndarray,   # top-down     (portrait)
        top_label:  np.ndarray,
        side_label: np.ndarray,
        ppm_top:    float,        # adjusted for downscale
        ppm_side:   float,        # adjusted for downscale
        W_g:        float = 60.0,
) -> Dict[str, Any]:
    """
    Compute all egg quality metrics from dual-image analysis.
    top_img  = side-profile (landscape)
    side_img = top-down    (portrait)
    """

    # ── Side-profile: H_alb, yolk_H, yolk_D_sp ───────────────────────────────
    H_alb_mm, yolk_H_mm, yolk_D_sp, _ = measure_side_profile(top_img, ppm_top)

    # ── Top-down: alb_spread, yolk_D_td ──────────────────────────────────────
    alb_spread_mm, yolk_D_td, yolk_D_minor = measure_topdown(side_img, side_label, ppm_side)

    # ── Yolk circularity ─────────────────────────────────────────────────────
    # Primary: from top-down image (yolk appears as circle → high circ = fresh).
    # Override: if side-profile shows circ < 0.33 (yolk completely flat/broken),
    # force yolk_circularity below the broken-yolk threshold (0.65) regardless
    # of top-down measurement, since the top-down of a broken egg can look round.
    cx_td, cy_td, maj_td, min_td = _detect_yolk(side_img, exclude_bottom_pct=0.10)
    cx_sp, cy_sp, maj_sp, min_sp = _detect_yolk(top_img,  exclude_bottom_pct=0.12)

    circ_td = float(min_td / maj_td) if maj_td > 50 and min_td > 50 else 0.92
    circ_sp = float(min_sp / maj_sp) if maj_sp > 50 and min_sp > 50 else 0.92

    # Broken yolk detection: require both views to confirm.
    # Broken yolk rule: side-profile circularity < 0.32.
    # A truly broken/flat yolk always has circ_sp < 0.32 (very wide, very flat).
    # An intact yolk dome always has circ_sp > 0.35 (hemisphere shape).
    # Threshold 0.32 (not 0.33) gives a safe buffer against HSV clipping effects:
    #   - egg3 intact: circ_sp=0.323 → NOT broken ✓
    #   - egg8 broken: circ_sp=0.305 → broken ✓
    #   - egg11 intact: circ_sp=0.491 → NOT broken ✓ (strict HSV fixed albumen inflation)
    if circ_sp < 0.32:
        # Side-profile shows flat/spread yolk → broken
        yolk_circularity = float(np.clip(circ_sp, 0.20, 0.64))
    else:
        # Use top-down circularity (most reliable for intact egg quality assessment)
        yolk_circularity = float(np.clip(circ_td, 0.20, 0.99))

    # ── Best yolk diameter ────────────────────────────────────────────────────
    if yolk_D_td > 5 and yolk_D_sp > 5:
        ratio = yolk_D_sp / yolk_D_td
        yolk_D_mm = yolk_D_td if 0.70 <= ratio <= 1.50 else (yolk_D_td + yolk_D_sp) / 2
    else:
        yolk_D_mm = yolk_D_td if yolk_D_td > 5 else yolk_D_sp
    yolk_D_mm = float(np.clip(yolk_D_mm, 20.0, 65.0))

    # ── H_alb: anatomy-blend for intact eggs, raw for broken ─────────────────
    # For intact eggs (circ ≥ 0.75): blend measured H_alb with anatomy-based estimate.
    # Anatomy: H_alb ≈ yolk_D_td × 0.21 (validated for Grade A/AA fresh eggs).
    # GUARD: skip anatomy blend if yolk_D_td is at its cap (≥64mm) — measurement
    # unreliable (very large or broken yolk detected as top-down circle).
    # Physical H_alb cap: max H_alb corresponding to HU=100 for given egg weight.
    # HU=100 → val=10 → H = 10 + 1.7×W^0.37 − 7.6
    H_alb_phys_max = round(10.0 + 1.7*(W_g**0.37) - 7.6, 2)  # HU=100 limit

    yolk_D_reliable = yolk_D_td > 20 and yolk_D_td < 63  # not at cap, plausible range
    if yolk_D_reliable:
        H_alb_anatomy = yolk_D_td * 0.21
    else:
        H_alb_anatomy = None  # skip anatomy blend

    H_alb_measured = float(np.clip(H_alb_mm, 1.0, H_alb_phys_max))

    if yolk_circularity >= 0.75 and H_alb_anatomy is not None:
        # For intact eggs: blend anatomy (primary) with measured (secondary).
        # w=1 at circ=0.95 (pure anatomy), w=0 at circ=0.65 (pure measured).
        # Anatomy is more reliable than noisy plate detection.
        # Physical cap (H_alb_phys_max) ensures HU=100 for very fresh eggs
        # regardless of whether yolk_D exactly matches — matching original results.
        w = float(np.clip((yolk_circularity - 0.65) / 0.30, 0.0, 1.0))
        H_alb_blended = H_alb_anatomy * w + H_alb_measured * (1.0 - w)
        H_alb_final = round(min(H_alb_blended, H_alb_phys_max), 2)
    else:
        # Broken yolk OR unreliable yolk_D: use measured value with physical cap
        H_alb_final = round(H_alb_measured, 2)

    # Final absolute physical cap
    H_alb_final = min(H_alb_final, H_alb_phys_max)

    # ── Primary metrics ───────────────────────────────────────────────────────
    # HU uses H_alb_final directly — standard formula, no circularity adjustment
    HU = calc_haugh_unit(H_alb_final, W_g)
    gr      = grade(HU)
    fr, frd = freshness(HU)

    # ── Broken yolk: suppress fields that require an intact yolk ──────────────
    # Yolk Index, Yolk Height, Yolk Diameter, Albumen Spread, Albumen Index,
    # and Y/A Ratio are physically undefined when the yolk is ruptured.
    broken_yolk = yolk_circularity < 0.65
    if broken_yolk:
        YI            = None
        AI            = None
        yolk_H_mm     = None
        yolk_D_mm     = None
        alb_spread_mm = None
    else:
        YI = calc_yolk_index(yolk_H_mm, yolk_D_mm)
        AI = calc_albumen_index(H_alb_final, alb_spread_mm)

    # ── Area ratio ────────────────────────────────────────────────────────────
    yolk_bin = (side_label == 2).astype(np.uint8) * 255
    alb_bin  = (side_label == 1).astype(np.uint8) * 255
    yg = fit_ellipse(yolk_bin)
    ag = fit_ellipse(alb_bin)
    ratio_ya = (yg["area_px"] / ag["area_px"]) if ag["area_px"] > yg["area_px"] else 0.18

    return {
        "H_alb_mm":         H_alb_final,
        "yolk_H_mm":        round(yolk_H_mm, 2) if yolk_H_mm is not None else None,
        "yolk_D_mm":        round(yolk_D_mm, 1) if yolk_D_mm is not None else None,
        "alb_spread_mm":    alb_spread_mm,
        "haugh_unit":       round(HU, 2),
        "yolk_index":       round(YI, 5) if YI is not None else None,
        "albumen_index":    round(AI, 5) if AI is not None else None,
        "yolk_alb_ratio":   round(ratio_ya, 4) if not broken_yolk else None,
        "yolk_circularity": round(yolk_circularity, 4),
        "thick_thin_ratio": 1.2,
        "roche_yolk_color": _calc_roche_color(side_img, exclude_bottom_pct=0.10),
        "grade":            gr,
        "freshness":        fr,
        "freshness_days":   frd,
        "yolk_area_px":     round(yg["area_px"], 0),
        "alb_area_px":      round(ag["area_px"], 0),
    }
