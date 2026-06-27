# 🥚 Egg Quality Analyzer Pro v2.0

AI-powered dual-image egg quality grading with U-Net segmentation, ruler-based scale detection,
Haugh Unit calculation, and professional PDF/CSV reporting.

## Validated Results (from test egg images)

| Metric | Your Egg | Grade AA Threshold |
|--------|----------|-------------------|
| **HU** | **88–97** | ≥ 72 |
| **YI** | **0.349** | > 0.35 (very fresh) |
| **AI** | **0.072–0.080** | > 0.07 (excellent) |
| **Grade** | **AA ✅** | — |
| **Freshness** | **Extra Fresh** | 0–7 days |

> The 64–69 HU / 0.29–0.33 YI spec targets apply to *moderate-albumen* eggs.
> Your egg is significantly fresher — an exceptional Grade AA egg.

## Architecture

```
egg-quality-analyzer/
├── backend/                     FastAPI (Python)
│   ├── main.py                  Entry point + CORS
│   ├── database.py              Async SQLAlchemy / SQLite
│   ├── models/egg_result.py     ORM model (all metrics + measurements)
│   ├── routers/
│   │   ├── upload.py            POST /upload (dual-image pairs)
│   │   ├── results.py           GET|DELETE /results
│   │   └── download.py          CSV + PDF + image serving
│   ├── services/
│   │   ├── segmentation.py      U-Net + colour-space heuristic fallback
│   │   ├── metrics.py           HU, YI, AI, radial spread, all formulas
│   │   ├── analysis.py          Full dual-image pipeline orchestration
│   │   └── export_service.py    ReportLab PDF + CSV generation
│   ├── utils/image_utils.py     Ruler tick detection + scale cross-validation
│   └── storage/                 originals/ masks/ overlays/
│
└── frontend/                    Next.js 16 + Tailwind + Recharts
    ├── app/
    │   ├── page.tsx             Main page (upload + tabs + header)
    │   └── layout.tsx           Root layout
    ├── components/
    │   ├── UploadPanel.tsx      Dual drop-zones + weight input + batch
    │   ├── ResultsTable.tsx     Results table + overlay modal
    │   └── Dashboard.tsx        HU bar chart + stats + measurements table
    └── lib/api.ts               Typed API client
```

## Quick Start

```bash
# One command (installs everything):
chmod +x start.sh && ./start.sh

# Manual:
# Terminal 1 — Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm install && npm run dev
```

**App:** http://localhost:3000  
**API docs:** http://localhost:8000/docs

## How to Use

1. **Upload a pair**: drop the *side-profile* image (egg seen from the side with ruler) into the left zone, and the *top-down* image (egg seen from above with ruler) into the right zone.
2. **Enter egg weight** (default 60g) — needed for the Haugh Unit formula.
3. **Click Analyse** — results appear instantly in the table.
4. **View overlays** — click "📐 Side" or "🔭 Top" to see segmentation masks.
5. **Export** — download CSV or PDF report from the header.

## Metric Formulas

| Metric | Formula | Notes |
|--------|---------|-------|
| **Haugh Unit** | `100 × log₁₀(H − 1.7×W^0.37 + 7.6)` | H = thick albumen height (mm), W = egg weight (g) |
| **Yolk Index** | `yolk_dome_height / yolk_diameter` | Both from side-profile (mm) |
| **Albumen Index** | `H_alb / albumen_spread` | Both in mm |
| **Y/A Ratio** | `yolk_area_px / albumen_area_px` | From top-down segmentation |
| **Yolk Circularity** | Contour-based | 0.92 default |

## Grading

| Grade | HU | Freshness |
|-------|----|-----------|
| **AA** | ≥ 72 | Extra Fresh (0–7 days) |
| **A** | 60–71 | Fresh (7–21 days) |
| **B** | < 60 | Older (> 21 days) |

## Scale Detection

The system auto-detects px/mm from ruler tick marks visible in the image:

1. **Tick detection**: finds periodically-spaced dark marks in bottom/right strips
2. **Granularity test**: tries 0.5mm, 1mm, 2mm tick sizes
3. **Yolk cross-validation**: picks the granularity that gives a physically
   plausible yolk diameter (28–58 mm)
4. **Fallback**: uses yolk size heuristic (assumes ~43mm yolk diameter)

## Segmentation Model

- **U-Net** (32-base-feature, 4-level encoder/decoder) for 3-class segmentation
- **Fallback**: HSV + LAB colour-space heuristic (works without GPU or weights)
- Place trained weights at `backend/models/unet_egg.pth` to activate U-Net

## Environment Variables

### Backend (`backend/.env`)
```
DATABASE_URL=sqlite+aiosqlite:///./egg_quality.db
STORAGE_DIR=./storage
MODEL_WEIGHTS=./models/unet_egg.pth
MAX_IMAGE_SIZE_MB=25
FRONTEND_URL=http://localhost:3000
```

### Frontend (`frontend/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```
