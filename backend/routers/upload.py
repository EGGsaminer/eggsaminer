"""POST /upload — accepts paired top-down + side-profile images per egg."""
import logging
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from database import get_db
from models.egg_result import EggResult
from services.analysis import analyse_pair

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_dict(r: EggResult) -> dict:
    """Serialize EggResult ORM object to JSON-safe dict."""
    return {
        "id":               r.id,
        "session_name":     r.session_name,
        "egg_weight_g":     r.egg_weight_g,
        "ppm_top":          r.ppm_top,
        "ppm_side":         r.ppm_side,
        "H_alb_mm":         r.H_alb_mm,
        "yolk_H_mm":        r.yolk_H_mm,
        "yolk_D_mm":        r.yolk_D_mm,
        "alb_spread_mm":    r.alb_spread_mm,
        "haugh_unit":       r.haugh_unit,
        "yolk_index":       r.yolk_index,
        "albumen_index":    r.albumen_index,
        "yolk_alb_ratio":   r.yolk_alb_ratio,
        "yolk_circularity": r.yolk_circularity,
        "thick_thin_ratio": r.thick_thin_ratio,
        "roche_yolk_color": r.roche_yolk_color,
        "grade":            r.grade,
        "freshness":        r.freshness,
        "freshness_days":   r.freshness_days,
        "yolk_area_px":     r.yolk_area_px,
        "alb_area_px":      r.alb_area_px,
        "overlay_top":      r.overlay_top,
        "overlay_side":     r.overlay_side,
        "top_path":         r.top_path,
        "side_path":        r.side_path,
        "error_msg":        r.error_msg,
        "created_at":       r.created_at.isoformat() if r.created_at else None,
    }


@router.post("/upload")
async def upload(
    top_images:   List[UploadFile] = File(..., description="Top-down view image(s)"),
    side_images:  List[UploadFile] = File(..., description="Side-profile image(s)"),
    egg_weights:  Optional[str]    = Form(None),
    session_name: Optional[str]    = Form(None),
    ppm_top_values:  Optional[str] = Form(None),
    ppm_side_values: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload one or more egg pairs.
    top_images:  top_view.jpeg — shot from directly above (top-down)
    side_images: side_view.jpeg — shot from the side (side-profile)
    egg_weights: comma-separated floats in grams, one per pair
    ppm_top_values:  optional comma-separated px/mm for side-profile images
    ppm_side_values: optional comma-separated px/mm for top-down images
    """
    from database import init_db
    await init_db()  # ensure table exists (handles cold starts without lifespan)
    if len(top_images) != len(side_images):
        raise HTTPException(400, f"Mismatch: {len(top_images)} top vs {len(side_images)} side images")

    # Parse weights
    weights: List[float] = []
    if egg_weights:
        try:
            weights = [float(w.strip()) for w in egg_weights.split(",") if w.strip()]
        except ValueError:
            raise HTTPException(400, "egg_weights must be comma-separated numbers")
    while len(weights) < len(top_images):
        weights.append(60.0)

    # Parse optional manual ppm values
    def _parse_ppm(s: Optional[str]) -> List[Optional[float]]:
        if not s: return [None] * len(top_images)
        vals = []
        for v in s.split(","):
            v = v.strip()
            try: vals.append(float(v) if v and float(v) > 0 else None)
            except ValueError: vals.append(None)
        while len(vals) < len(top_images): vals.append(None)
        return vals

    ppm_tops  = _parse_ppm(ppm_top_values)
    ppm_sides = _parse_ppm(ppm_side_values)

    results = []
    for i, (top_f, side_f) in enumerate(zip(top_images, side_images)):
        top_b  = await top_f.read()
        side_b = await side_f.read()
        name   = session_name or top_f.filename or f"Egg {i+1}"

        # top_images = user's top_view.jpeg = side-profile analysis (landscape close-up)
        # side_images = user's side_view.jpeg = top-down analysis (portrait overhead)
        r = await analyse_pair(
            top_bytes=top_b,   top_name=top_f.filename  or "top.jpg",
            side_bytes=side_b, side_name=side_f.filename or "side.jpg",
            egg_weight_g=weights[i],
            session_name=name,
            ppm_top_override=ppm_tops[i],
            ppm_side_override=ppm_sides[i],
        )
        db.add(r)
        results.append(_to_dict(r))

    await db.commit()
    return JSONResponse({"results": results, "count": len(results)})
