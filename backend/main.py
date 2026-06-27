"""
EggSaminer — FastAPI backend.
Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import os, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv()

from database import init_db
from routers import upload, results, download

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialised — ready.")
    yield

app = FastAPI(
    title="EggSaminer",
    description="Dual-image AI egg grading API",
    version="2.1.0",
    lifespan=lifespan,
)

# Wide-open CORS — allow any origin so local dev always works
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(upload.router,   tags=["Upload"])
app.include_router(results.router,  tags=["Results"])
app.include_router(download.router, tags=["Export"])

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "2.1.0"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# ── Re-segment + recalculate all albumen metrics ──────────────────────────
from pathlib import Path as _Path
from fastapi.responses import Response as _Resp
from fastapi import HTTPException as _HTTP

@app.get("/resegment/{uid}")
async def resegment(uid: str, sensitivity: float = 1.0):
    """
    Re-segment the top-down image with new albumen sensitivity and
    recalculate ALL albumen-dependent metrics (alb_area, yolk_alb_ratio,
    albumen_index, alb_spread, haugh_unit, grade, freshness).
    Returns: { overlay_url, metrics: { updated fields } }
    """
    import cv2 as _cv2
    from services.segmentation import segment as _seg, make_overlay as _mkol
    from services.metrics import (
        measure_topdown as _mtd, calc_haugh_unit as _hu,
        calc_albumen_index as _ai, calc_yolk_index as _yi,
        fit_ellipse as _fe, grade as _gr_fn, freshness as _fr_fn,
    )
    from utils.image_utils import load_cv2 as _lc, downscale_if_needed as _ds
    from sqlalchemy import select as _sel
    from database import AsyncSessionLocal as _ASL
    from models.egg_result import EggResult as _ERM

    STOR = _Path(os.getenv("STORAGE_DIR", "./storage"))
    # top-down original stored as {uid}_side.jpg (legacy naming)
    orig_td = STOR / "originals" / f"{uid}_side.jpg"
    if not orig_td.exists():
        raise _HTTP(status_code=404, detail="Top-down original not found; re-upload egg")

    with open(orig_td, "rb") as f: raw = f.read()
    img = _lc(raw); img, _ = _ds(img)

    # Re-segment with new sensitivity
    label = _seg(img, None, sat_sensitivity=float(sensitivity))
    overlay = _mkol(img, label, show_albumen=True)
    ov_path = STOR / "overlays" / f"{uid}_side.jpg"
    _cv2.imwrite(str(ov_path), overlay, [int(_cv2.IMWRITE_JPEG_QUALITY), 85])

    # Fetch current DB record for ppm/weight/existing metrics
    async with _ASL() as session:
        row = (await session.execute(_sel(_ERM).where(_ERM.id == uid))).scalar_one_or_none()
        if not row:
            raise _HTTP(status_code=404, detail="Result record not found")

        ppm_td = float(row.ppm_side or 9.0)   # top-down ppm stored in ppm_side
        W_g    = float(row.egg_weight_g or 60.0)
        yolk_H = float(row.yolk_H_mm) if row.yolk_H_mm else None
        H_alb  = float(row.H_alb_mm) if row.H_alb_mm else 5.0
        circ   = float(row.yolk_circularity) if row.yolk_circularity else 1.0
        broken = circ < 0.65

        # Recalculate from new segmentation
        alb_spread, yolk_D_td, _ = _mtd(img, label, ppm_td)
        yolk_bin = (label == 2).astype("uint8") * 255
        alb_bin  = (label == 1).astype("uint8") * 255
        yg = _fe(yolk_bin); ag = _fe(alb_bin)
        ratio_ya = (yg["area_px"] / ag["area_px"]) if (not broken and ag["area_px"] > yg["area_px"]) else None
        YI = _yi(yolk_H, yolk_D_td) if (yolk_H and yolk_D_td and not broken) else None
        AI = _ai(H_alb, alb_spread) if not broken else None
        HU = _hu(H_alb, W_g)
        gr = _gr_fn(HU)
        fr, frd = _fr_fn(HU)

        # Save to DB
        row.alb_area_px    = round(ag["area_px"], 0)
        row.yolk_area_px   = round(yg["area_px"], 0)
        row.yolk_alb_ratio = round(ratio_ya, 4) if ratio_ya is not None else None
        row.albumen_index  = round(AI, 5)        if AI is not None else None
        row.yolk_index     = round(YI, 5)        if YI is not None else None
        row.alb_spread_mm  = alb_spread
        row.grade          = gr
        row.freshness      = fr
        row.freshness_days = frd
        await session.commit()

    return {
        "overlay_url": f"/images/overlays/{uid}_side.jpg",
        "metrics": {
            "alb_area_px":    round(ag["area_px"], 0),
            "yolk_area_px":   round(yg["area_px"], 0),
            "yolk_alb_ratio": round(ratio_ya, 4) if ratio_ya is not None else None,
            "albumen_index":  round(AI, 5)        if AI is not None else None,
            "yolk_index":     round(YI, 5)        if YI is not None else None,
            "alb_spread_mm":  alb_spread,
            "haugh_unit":     round(HU, 2),
            "grade":          gr,
            "freshness":      fr,
            "freshness_days": frd,
        }
    }


@app.get("/resegment/{uid}")
async def resegment(uid: str, sensitivity: float = 1.0, view: str = "top"):
    """
    Re-generate overlay with custom albumen sensitivity.
    view: 'top' = top-down view, 'side' = side-profile view
    sensitivity: 0.3 = strict (less albumen), 1.0 = normal, 3.0 = loose (more albumen)
    Returns JSON with overlay_url pointing to the regenerated overlay.
    """
    import cv2 as _cv2
    from services.segmentation import segment as _seg, make_overlay as _mkol
    from utils.image_utils import load_cv2 as _lc, downscale_if_needed as _ds

    STOR = _Path(os.getenv("STORAGE_DIR", "./storage"))
    # Originals: td_img stored as {uid}_side.jpg, sp_img stored as {uid}_top.jpg
    # (legacy naming: "side" suffix = top-down, "top" suffix = side-profile)
    if view == "top":
        orig_path = STOR / "originals" / f"{uid}_side.jpg"  # top-down original
        overlay_name = f"{uid}_side.jpg"                     # top-down overlay filename
        show_alb = True
    else:
        orig_path = STOR / "originals" / f"{uid}_top.jpg"   # side-profile original
        overlay_name = f"{uid}_top.jpg"                      # side-profile overlay filename
        show_alb = False

    if not orig_path.exists():
        raise _HTTP(status_code=404, detail=f"Original not found for view={view}; re-upload egg")

    with open(orig_path, "rb") as f:
        raw = f.read()
    img = _lc(raw)
    img, _ = _ds(img)
    label = _seg(img, None, sat_sensitivity=float(sensitivity))
    overlay = _mkol(img, label, show_albumen=show_alb)
    
    # Save regenerated overlay
    overlay_path = STOR / "overlays" / overlay_name
    _cv2.imwrite(str(overlay_path), overlay, [int(_cv2.IMWRITE_JPEG_QUALITY), 85])
    
    return {"overlay_url": f"/images/overlays/{overlay_name}"}

# ── Auto-detect PPM from image ──────────────────────────────────────────────
@app.post("/detect-ppm")
async def detect_ppm(image: UploadFile = File(...)):
    """
    Auto-detect pixels-per-mm from a ruler in the image.
    Returns { ppm, ruler_detected, scene_mm } so the UI can show it as a suggestion.
    """
    from utils.image_utils import get_scale, load_cv2, downscale_if_needed as _ds
    raw = await image.read()
    img = load_cv2(raw)
    ppm_full, ruler_ok = get_scale(img)
    img_s, sc = _ds(img)
    h, w = img_s.shape[:2]
    is_p = h > w
    ref = h if is_p else w
    scene_mm = round((ref / sc) / ppm_full, 1) if ppm_full > 0 else 0
    ppm_proc = round(ppm_full * sc, 2)
    return {
        "ppm": round(ppm_full, 2),      # px/mm on original full-res image
        "ppm_proc": ppm_proc,           # px/mm on working (downscaled) image
        "ruler_detected": ruler_ok,
        "scene_mm": scene_mm,
        "portrait": is_p,
    }

