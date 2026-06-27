"""
Dual-image analysis pipeline — v2.4
Auto-detects side-profile vs top-down image using:
1. Orientation (landscape → side-profile, portrait → top-down)
2. When both landscape: use yolk circularity (higher circ → top-down)
   Top-down shows yolk as circle; side-profile shows yolk as elongated ellipse.
"""
import os, uuid, logging
from pathlib import Path
import cv2, numpy as np

from services.segmentation import segment, make_overlay
from services.metrics import compute_metrics
from utils.image_utils import validate_image, load_cv2, get_scale, downscale_if_needed
from models.egg_result import EggResult

logger  = logging.getLogger(__name__)
STORAGE = Path(os.getenv("STORAGE_DIR", "./storage"))
WEIGHTS = os.getenv("MODEL_WEIGHTS", "./models/unet_egg.pth")


def _yolk_circularity(img_bgr: np.ndarray) -> float:
    """Measure yolk ellipse circularity (minor/major). Higher = more top-down view."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, w = img_bgr.shape[:2]
    ym = cv2.inRange(hsv[:int(h*0.88), :int(w*0.92)],
                     np.array([10, 120, 100]), np.array([38, 255, 255]))
    k  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (12, 12))
    ym = cv2.morphologyEx(ym, cv2.MORPH_CLOSE, k)
    ym = cv2.morphologyEx(ym, cv2.MORPH_OPEN,  k)
    conts, _ = cv2.findContours(ym, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not conts:
        return 0.5
    yc = max(conts, key=cv2.contourArea)
    if len(yc) >= 5:
        _, (ma, mi), _ = cv2.fitEllipse(yc)
        return (min(ma, mi) / max(ma, mi)) if max(ma, mi) > 0 else 0.5
    _, _, bw, bh = cv2.boundingRect(yc)
    return (min(bw, bh) / max(bw, bh)) if max(bw, bh) > 0 else 0.5


def _assign_roles(img_a: np.ndarray, img_b: np.ndarray,
                  name_a: str, name_b: str):
    """
    Assign side-profile and top-down roles.
    Logic:
    1. If one is landscape and one is portrait → landscape = side-profile, portrait = top-down
    2. If both landscape → measure yolk circularity: lower circ = side-profile
    3. If both portrait → measure yolk circularity: lower circ = side-profile
    Returns (sp_img, sp_name, td_img, td_name).
    """
    ha, wa = img_a.shape[:2]
    hb, wb = img_b.shape[:2]
    land_a = wa > ha
    land_b = wb > hb

    if land_a and not land_b:
        return img_a, name_a, img_b, name_b  # A=landscape=sp, B=portrait=td
    if land_b and not land_a:
        return img_b, name_b, img_a, name_a  # B=landscape=sp, A=portrait=td

    # Both same orientation → use yolk circularity
    # Lower circularity = more elongated = side-profile view
    circ_a = _yolk_circularity(img_a)
    circ_b = _yolk_circularity(img_b)
    logger.info(f"Both same orientation — yolk circ: {name_a}={circ_a:.3f}, {name_b}={circ_b:.3f}")

    if circ_a <= circ_b:
        return img_a, name_a, img_b, name_b  # A more elongated = sp
    else:
        return img_b, name_b, img_a, name_a  # B more elongated = sp


async def analyse_pair(
        top_bytes:    bytes,
        top_name:     str,
        side_bytes:   bytes,
        side_name:    str,
        egg_weight_g: float = 60.0,
        session_name: str   = "",
        ppm_top_override:  float | None = None,  # manual px/mm for side-profile image
        ppm_side_override: float | None = None,  # manual px/mm for top-down image
) -> EggResult:
    uid = str(uuid.uuid4())

    for content, name in [(top_bytes, top_name), (side_bytes, side_name)]:
        ok, err = validate_image(content, name)
        if not ok:
            return EggResult(id=uid, session_name=session_name or name,
                             egg_weight_g=egg_weight_g, error_msg=err)

    try:
        img_a_full = load_cv2(top_bytes)
        img_b_full = load_cv2(side_bytes)

        # ── Assign roles ──────────────────────────────────────────────────────
        sp_full, sp_name, td_full, td_name = _assign_roles(
            img_a_full, img_b_full, top_name, side_name)
        logger.info(f"[{uid}] side-profile={sp_name} "
                    f"({sp_full.shape[1]}×{sp_full.shape[0]}), "
                    f"top-down={td_name} ({td_full.shape[1]}×{td_full.shape[0]})")

        # ── Scale on full-res, then downscale ────────────────────────────────
        # get_scale on full-res image gives the most accurate tick detection.
        # ppm_proc = ppm_full * sc scales it correctly to the working image.
        ppm_sp, ruler_sp = get_scale(sp_full)
        ppm_td, ruler_td = get_scale(td_full)
        logger.info(f"[{uid}] ppm sp={ppm_sp:.2f}({'ruler' if ruler_sp else 'heur'}) "
                    f"td={ppm_td:.2f}({'ruler' if ruler_td else 'heur'})")

        # ── Downscale ─────────────────────────────────────────────────────────
        sp_img, sc_sp = downscale_if_needed(sp_full); del sp_full
        td_img, sc_td = downscale_if_needed(td_full); del td_full
        ppm_sp_proc = ppm_sp * sc_sp
        ppm_td_proc = ppm_td * sc_td

        # Override with manual PPM if provided (already in full-image px/mm,
        # user-supplied from the UI ruler measurement — scale to working image)
        if ppm_top_override and ppm_top_override > 0:
            ppm_sp_proc = float(ppm_top_override) * sc_sp
            logger.info(f"[{uid}] manual ppm_sp override: {ppm_top_override} -> proc={ppm_sp_proc:.2f}")
        if ppm_side_override and ppm_side_override > 0:
            ppm_td_proc = float(ppm_side_override) * sc_td
            logger.info(f"[{uid}] manual ppm_td override: {ppm_side_override} -> proc={ppm_td_proc:.2f}")

        # ── Segmentation ──────────────────────────────────────────────────────
        sp_label = segment(sp_img, WEIGHTS)
        td_label = segment(td_img, WEIGHTS)

        # ── Metrics ───────────────────────────────────────────────────────────
        m = compute_metrics(sp_img, td_img, sp_label, td_label,
                            ppm_sp_proc, ppm_td_proc, egg_weight_g)

        # ── Save images ───────────────────────────────────────────────────────
        def _save(img, folder, suffix):
            p = STORAGE / folder / f"{uid}_{suffix}.jpg"
            p.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 92])

        _save(sp_img, "originals", "top")
        _save(td_img, "originals", "side")
        # Side-profile: show yolk only (albumen seg unreliable due to background gradient)
        # Top-down:     show both yolk and albumen (background is clearly bounded)
        _save(make_overlay(sp_img, sp_label, show_albumen=False), "overlays", "top")
        _save(make_overlay(td_img, td_label, show_albumen=True),  "overlays", "side")

        return EggResult(
            id=uid,
            session_name=session_name or top_name,
            top_path=f"{uid}_top.jpg",
            side_path=f"{uid}_side.jpg",
            overlay_top=f"{uid}_top.jpg",
            overlay_side=f"{uid}_side.jpg",
            egg_weight_g=egg_weight_g,
            ppm_top=round(ppm_sp_proc, 3),   # side-profile ppm on working image
            ppm_side=round(ppm_td_proc, 3),  # top-down ppm on working image
            H_alb_mm=m["H_alb_mm"],
            yolk_H_mm=m["yolk_H_mm"],
            yolk_D_mm=m["yolk_D_mm"],
            alb_spread_mm=m["alb_spread_mm"],
            haugh_unit=m["haugh_unit"],
            yolk_index=m["yolk_index"],
            albumen_index=m["albumen_index"],
            yolk_alb_ratio=m["yolk_alb_ratio"],
            yolk_circularity=m["yolk_circularity"],
            thick_thin_ratio=m["thick_thin_ratio"],
            roche_yolk_color=m["roche_yolk_color"],
            grade=m["grade"],
            freshness=m["freshness"],
            freshness_days=m["freshness_days"],
            yolk_area_px=m["yolk_area_px"],
            alb_area_px=m["alb_area_px"],
        )

    except Exception as e:
        logger.exception(f"[{uid}] Pipeline error: {e}")
        return EggResult(id=uid, session_name=session_name or top_name,
                         egg_weight_g=egg_weight_g, error_msg=str(e))
