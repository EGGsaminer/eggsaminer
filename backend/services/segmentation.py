"""
Segmentation v5 — saturation-only detection, top-center background estimation.

Key fixes vs v4:
  • Background estimated from TOP-CENTER strip only (avoids dark ruler corners
    that contaminate the estimate and cause dist>40 to flag 96% of the image)
  • Colour-distance detector REMOVED (was unreliable on grey surfaces)
  • Side ruler exclusion NOT applied to egg_raw (was causing rectangular boundary
    artifacts when the egg body extended to the image edges)
  • Only bottom ruler strip excluded from egg detection
  • Adaptive sat threshold uses p75 of top-center strip × 1.5 + 5
    (uses p75 not p25, so a few high-sat pixels in the ruler don't raise the bar)
"""
from __future__ import annotations
import cv2, numpy as np, logging
from typing import Optional
logger = logging.getLogger(__name__)

try:
    import torch; TORCH = True
except ImportError:
    TORCH = False

def _load_model(weights):
    if not TORCH or not weights: return None, "cpu"
    try:
        import os
        if not os.path.exists(weights): return None, "cpu"
        from torch import nn
        class _U(nn.Module):
            def __init__(self): super().__init__()
        m = _U(); m.load_state_dict(torch.load(weights, map_location="cpu")); m.eval()
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        return m.to(dev), dev
    except Exception as e:
        logger.warning(f"Model load: {e}"); return None, "cpu"

def _yolk(img, excl):
    """Detect yolk mask using strict HSV. Returns (mask, seed_y, seed_x)."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ym = cv2.inRange(hsv, np.array([10, 120, 100]), np.array([38, 255, 255]))
    ym = cv2.bitwise_and(ym, excl)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (12, 12))
    ym = cv2.morphologyEx(ym, cv2.MORPH_CLOSE, k)
    ym = cv2.morphologyEx(ym, cv2.MORPH_OPEN, k)
    conts, _ = cv2.findContours(ym, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros((h, w), np.uint8)
    sy, sx = h // 2, w // 2
    if conts:
        ma = max(cv2.contourArea(c) for c in conts)
        for c in conts:
            if cv2.contourArea(c) >= ma * 0.01:
                cv2.drawContours(mask, [c], -1, 255, -1)
        if mask.any():
            ys = np.where(mask > 0)
            sy, sx = int(np.median(ys[0])), int(np.median(ys[1]))
    return mask, sy, sx

def _body(img, ym, sy, sx, ruler_bot_px, sat_sensitivity: float = 1.0):
    """
    Detect egg body using saturation only — no colour distance.
    Background estimated from top-center strip to avoid ruler-corner contamination.
    Side ruler exclusion NOT used here (avoids rectangular boundary artifacts).
    """
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32)

    # Background from top-center strip (top 1–7%, centre 10–90% of width)
    # This area always contains background paper, no rulers, no egg.
    rs_inner = int(w * 0.10)
    tc = sat[int(h * 0.01): int(h * 0.07), rs_inner: w - rs_inner]
    bg_p75 = float(np.percentile(tc, 75)) if tc.size > 0 else 5.0
    # sat_sensitivity: 1.0=normal, <1=stricter (less albumen), >1=looser (more albumen)
    thr = max(4.0, (bg_p75 * 1.5 + 5.0) / max(0.3, sat_sensitivity))

    # Egg footprint: saturation above adaptive threshold
    raw = (sat > thr).astype(np.uint8) * 255

    # Exclude ONLY the bottom ruler strip (not the sides)
    raw[h - ruler_bot_px:, :] = 0

    # Always include yolk
    raw = cv2.bitwise_or(raw, ym)

    # Morphological cleanup — 8px close (tight enough to not bridge noise)
    ke  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (8, 8))
    ke2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (6, 6))
    raw = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, ke)
    raw = cv2.morphologyEx(raw, cv2.MORPH_OPEN, ke2)

    # Remove small noise components before flood-fill
    min_area = max(100, int(h * w * 0.002))
    nc, cc = cv2.connectedComponents(raw)
    filt = np.zeros((h, w), np.uint8)
    for i in range(1, nc):
        if int((cc == i).sum()) >= min_area:
            filt[cc == i] = 255
    filt = cv2.bitwise_or(filt, ym)

    # Flood-fill: keep component containing yolk
    nf, ccf = cv2.connectedComponents(filt)
    sl = int(ccf[sy, sx])
    if sl > 0:
        return (ccf == sl).astype(np.uint8) * 255
    cnt = np.bincount(ccf.ravel()); cnt[0] = 0
    return (ccf == int(cnt.argmax())).astype(np.uint8) * 255 if cnt.max() > 0 else ym.copy()

def _heuristic(img, sat_sensitivity: float = 1.0):
    h, w = img.shape[:2]
    rb = int(h * 0.09)   # bottom ruler strip height
    rs = int(w * 0.08)   # side ruler strip width (for yolk detection only)

    # Exclusion mask for yolk detection only (keeps yolk away from rulers)
    excl = np.ones((h, w), np.uint8) * 255
    excl[h - rb:, :] = 0
    excl[:, :rs]     = 0
    excl[:, w - rs:] = 0

    ym, sy, sx = _yolk(img, excl)
    emask = _body(img, ym, sy, sx, rb, sat_sensitivity)

    alb = cv2.subtract(emask, ym)
    ka = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (6, 6))
    alb = cv2.morphologyEx(alb, cv2.MORPH_OPEN, ka)

    # Keep only largest albumen component — eliminates false blobs
    na, cca = cv2.connectedComponents(alb)
    if na > 2:
        sizes = [(i, int((cca == i).sum())) for i in range(1, na)]
        lg = max(sizes, key=lambda x: x[1])[0]
        alb = (cca == lg).astype(np.uint8) * 255
        alb = cv2.bitwise_and(alb, cv2.bitwise_not(ym))

    label = np.zeros((h, w), np.uint8)
    label[alb > 0] = 1
    label[ym  > 0] = 2
    return label

def segment(img, weights=None, sat_sensitivity: float = 1.0):
    m, dev = _load_model(weights)
    if m is not None and TORCH:
        import torch
        oh, ow = img.shape[:2]
        inp = cv2.resize(img, (256, 256))
        inp = cv2.cvtColor(inp, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        inp = torch.from_numpy(inp.transpose(2, 0, 1)).unsqueeze(0).to(dev)
        with torch.no_grad():
            out = m(inp).argmax(1).squeeze().cpu().numpy().astype(np.uint8)
        return cv2.resize(out, (ow, oh), interpolation=cv2.INTER_NEAREST)
    return _heuristic(img, sat_sensitivity)

def make_overlay(img, label, alpha=0.35, show_albumen=True):
    out = img.copy()
    for cls, col in [(1, (180, 200, 0)), (2, (0, 140, 255))]:
        if cls == 1 and not show_albumen:
            continue
        mask = (label == cls).astype(np.uint8) * 255
        if not mask.any():
            continue
        fill = img.copy(); fill[mask > 0] = col
        out = cv2.addWeighted(out, 1 - alpha * 0.6, fill, alpha * 0.6, 0)
        conts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, conts, -1, col, 2)
    return out
