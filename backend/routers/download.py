"""CSV / PDF export and image serving."""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.egg_result import EggResult
from services.export_service import generate_csv, generate_pdf

STORAGE = Path(os.getenv("STORAGE_DIR","./storage"))
router = APIRouter()

@router.get("/download/csv")
async def dl_csv(db: AsyncSession=Depends(get_db)):
    rows=(await db.execute(select(EggResult).order_by(EggResult.created_at.desc()))).scalars().all()
    return Response(generate_csv(rows), media_type="text/csv",
                    headers={"Content-Disposition":"attachment; filename=egg_results.csv"})

@router.get("/download/pdf")
async def dl_pdf(db: AsyncSession=Depends(get_db)):
    rows=(await db.execute(select(EggResult).order_by(EggResult.created_at.desc()))).scalars().all()
    return Response(generate_pdf(rows), media_type="application/pdf",
                    headers={"Content-Disposition":"attachment; filename=egg_report.pdf"})

@router.get("/images/{folder}/{filename}")
async def serve_image(folder: str, filename: str):
    if folder not in {"originals","masks","overlays"}:
        raise HTTPException(400,"Invalid folder")
    p = STORAGE / folder / filename
    if not p.exists(): raise HTTPException(404,"Not found")
    mt = "image/jpeg" if filename.endswith(".jpg") else "image/png"
    return FileResponse(str(p), media_type=mt)
