"""ORM model for a dual-image (top + side) egg analysis session."""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class EggResult(Base):
    __tablename__ = "egg_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # File references
    session_name: Mapped[str]  = mapped_column(String, nullable=False)
    top_path:     Mapped[str]  = mapped_column(String, nullable=True)   # side-profile image
    side_path:    Mapped[str]  = mapped_column(String, nullable=True)   # top-down image
    overlay_top:  Mapped[str]  = mapped_column(String, nullable=True)
    overlay_side: Mapped[str]  = mapped_column(String, nullable=True)

    # Input
    egg_weight_g: Mapped[float] = mapped_column(Float, default=60.0)

    # Scale (px/mm per image)
    ppm_top:  Mapped[float] = mapped_column(Float, nullable=True)  # side-profile px/mm
    ppm_side: Mapped[float] = mapped_column(Float, nullable=True)  # top-down px/mm

    # Raw measurements (mm)
    H_alb_mm:      Mapped[float] = mapped_column(Float, nullable=True)  # thick albumen height
    yolk_H_mm:     Mapped[float] = mapped_column(Float, nullable=True)  # yolk dome height
    yolk_D_mm:     Mapped[float] = mapped_column(Float, nullable=True)  # yolk diameter
    alb_spread_mm: Mapped[float] = mapped_column(Float, nullable=True)  # avg albumen spread

    # Quality metrics
    haugh_unit:        Mapped[float] = mapped_column(Float, nullable=True)
    yolk_index:        Mapped[float] = mapped_column(Float, nullable=True)
    albumen_index:     Mapped[float] = mapped_column(Float, nullable=True)
    yolk_alb_ratio:    Mapped[float] = mapped_column(Float, nullable=True)
    yolk_circularity:  Mapped[float] = mapped_column(Float, nullable=True)
    thick_thin_ratio:  Mapped[float] = mapped_column(Float, nullable=True, default=1.2)
    roche_yolk_color:  Mapped[float] = mapped_column(Float, nullable=True, default=11.0)

    # Classification
    grade:         Mapped[str] = mapped_column(String,  nullable=True)
    freshness:     Mapped[str] = mapped_column(String,  nullable=True)
    freshness_days:Mapped[str] = mapped_column(String,  nullable=True)

    # Pixel areas
    yolk_area_px:  Mapped[float] = mapped_column(Float, nullable=True)
    alb_area_px:   Mapped[float] = mapped_column(Float, nullable=True)

    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
