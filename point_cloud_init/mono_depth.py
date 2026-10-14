"""Monocular depth (Depth Anything V2) aligned to the COLMAP scale, used as a dense background depth.

Depth Anything V2 predicts relative inverse depth (affine-invariant disparity). Per frame we fit
    1 / z_colmap  ~=  a * disparity + b
on the COLMAP points visible in that frame (robust IRLS), giving a metric-scale depth map in the
COLMAP frame. Pixels whose aligned inverse depth is ~0 or negative (sky) get +inf.

Requires: torch, transformers (weights are downloaded from the HuggingFace hub on first use).
"""
import os
import time

import numpy as np
from PIL import Image

import common

MODEL = "depth-anything/Depth-Anything-V2-Small-hf"


class MonoPredictor:
    def __init__(self, model_name=MODEL, threads=0):
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        if threads > 0:
            torch.set_num_threads(threads)
        self.torch = torch
        self.proc = AutoImageProcessor.from_pretrained(model_name)
        self.model = AutoModelForDepthEstimation.from_pretrained(model_name).eval()

    def __call__(self, rgb):
        """rgb: HxWx3 uint8 -> HxW float32 relative disparity at image resolution."""
        torch = self.torch
        x = self.proc(images=Image.fromarray(rgb), return_tensors="pt")
        with torch.no_grad():
            d = self.model(**x).predicted_depth  # (1, h, w)
        d = torch.nn.functional.interpolate(d[:, None], size=rgb.shape[:2], mode="bilinear", align_corners=False)
        return d[0, 0].numpy().astype(np.float32)


def load_or_predict(scene, views, ids, cache_dir, model_name=MODEL, threads=0):
    """Returns {frame index: HxW float16 relative disparity}, cached in cache_dir/<name>.npz."""
    os.makedirs(cache_dir, exist_ok=True)
    out, todo = {}, []
    for i in ids:
        f = os.path.join(cache_dir, os.path.splitext(views[i].name)[0] + ".npz")
        if os.path.exists(f):
            z = np.load(f)
            if str(z["model"]) == model_name:
                out[i] = z["disp"]
                continue
        todo.append(i)
    if todo:
        t0 = time.time()
        pred = MonoPredictor(model_name, threads)
        print(f"  mono depth model loaded ({time.time() - t0:.0f}s)")
        for n, i in enumerate(todo):
            _, rgb = common.load_gray_rgb(os.path.join(scene["img_dir"], views[i].name))
            d = pred(rgb).astype(np.float16)
            np.savez_compressed(os.path.join(cache_dir, os.path.splitext(views[i].name)[0] + ".npz"),
                                model=model_name, disp=d)
            out[i] = d
            if (n + 1) % 20 == 0 or n + 1 == len(todo):
                print(f"  mono depth {n + 1}/{len(todo)}  ({time.time() - t0:.0f}s)")
    return out


def visible_colmap_samples(K, W, H, v, xyz, tile=8, slack=1.1):
    """COLMAP points projected into v that lie on the front-most surface of their tile
    (z <= slack * 20th-percentile depth of the tile). Returns u, w, z."""
    u, w, z = common.project(K, v.R, v.t, xyz)
    ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
    u, w, z = u[ok], w[ok], z[ok]
    if len(z) == 0:
        return u, w, z
    tw = (W + tile - 1) // tile
    cell = (w // tile).astype(np.int64) * tw + (u // tile).astype(np.int64)
    order = np.lexsort((z, cell))
    cs, zs = cell[order], z[order]
    uc, start, cnt = np.unique(cs, return_index=True, return_counts=True)
    p20 = zs[start + np.floor(0.2 * (cnt - 1)).astype(np.int64)]
    ref = np.empty_like(z)
    ref[order] = np.repeat(p20, cnt)
    keep = z <= slack * ref
    return u[keep], w[keep], z[keep]


def align(disp, u, w, z, iters=10, huber=0.05):
    """Robust fit of 1/z = a*disp + b. Returns a, b, median relative depth error, n samples."""
    if len(z) < 50:
        return None
    d = disp[np.clip(w.astype(int), 0, disp.shape[0] - 1), np.clip(u.astype(int), 0, disp.shape[1] - 1)].astype(np.float64)
    y = 1.0 / z
    wts = np.ones_like(y)
    A = np.stack([d, np.ones_like(d)], 1)
    for _ in range(iters):
        sw = np.sqrt(wts)
        a, b = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)[0]
        res = (A @ [a, b] - y) / y  # relative error in inverse depth ~ relative depth error
        wts = np.where(np.abs(res) <= huber, 1.0, huber / np.maximum(np.abs(res), 1e-12))
    pred_inv = a * d + b
    rel = np.abs(np.where(pred_inv > 0, 1.0 / np.maximum(pred_inv, 1e-12), np.inf) / z - 1)
    return float(a), float(b), float(np.median(rel)), len(z)


def aligned_depth(disp, a, b, min_inv=1e-4):
    inv = a * disp.astype(np.float32) + b
    return np.where(inv > min_inv, 1.0 / np.maximum(inv, min_inv), np.inf).astype(np.float32)
