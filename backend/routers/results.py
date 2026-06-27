"""GET/DELETE /results endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.egg_result import EggResult

router = APIRouter()


def _to_dict(r: EggResult) -> dict:
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
        "error_msg":        r.error_msg,
        "created_at":       r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/results")
async def list_results(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(EggResult).order_by(EggResult.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()
    total = (await db.execute(select(func.count()).select_from(EggResult))).scalar_one()
    return {"results": [_to_dict(r) for r in rows], "total": total}


@router.get("/results/{rid}")
async def get_result(rid: str, db: AsyncSession = Depends(get_db)):
    r = await db.get(EggResult, rid)
    if not r:
        raise HTTPException(404, "Not found")
    return _to_dict(r)


@router.delete("/results/{rid}")
async def delete_result(rid: str, db: AsyncSession = Depends(get_db)):
    r = await db.get(EggResult, rid)
    if not r:
        raise HTTPException(404, "Not found")
    await db.delete(r)
    await db.commit()
    return {"deleted": rid}
