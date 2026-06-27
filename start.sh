#!/usr/bin/env bash
# =============================================================
# Egg Quality Analyzer Pro — One-shot startup
# =============================================================
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "🥚  Egg Quality Analyzer Pro v2.0"
echo "=================================="

# ── Backend ──────────────────────────────────────────────────
echo "▶  Starting FastAPI backend..."
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
  echo "   Creating Python virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

pip install -q --upgrade pip
pip install -q -r requirements.txt

# Optional PyTorch (CPU) for U-Net if not installed
python -c "import torch" 2>/dev/null || {
  echo "   Installing PyTorch CPU (optional, for U-Net model)..."
  pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
}

mkdir -p storage/originals storage/masks storage/overlays models

uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "   ✓ Backend  →  http://localhost:8000"
echo "   ✓ API docs →  http://localhost:8000/docs"

# ── Frontend ─────────────────────────────────────────────────
echo "▶  Starting Next.js frontend..."
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
  echo "   Installing npm packages..."
  npm install --legacy-peer-deps
fi

npm run dev &
FRONTEND_PID=$!
echo "   ✓ Frontend → http://localhost:3000"

# ── Cleanup ───────────────────────────────────────────────────
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "✓  Both services running."
echo "   Open http://localhost:3000 in your browser."
echo "   Press Ctrl+C to stop."
echo ""
wait
