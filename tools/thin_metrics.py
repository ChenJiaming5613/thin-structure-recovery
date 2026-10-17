#!/usr/bin/env python3
"""Thin-structure (masked) metrics for rendered test views.

For every model directory it looks for <model>/test/ours_<iter>/{renders,gt} (Scaffold-GS / 3DGS layout,
latest iteration) and reports, in addition to the full-image metrics of metrics.py:
  PSNR_M  : PSNR over the pixels of the thin-structure mask M (MSE over M, all channels)
  SSIM_M  : SSIM map (11x11 Gaussian window, sigma 1.5) averaged over M
  LPIPS_M : spatial LPIPS map (VGG, as in metrics.py) averaged over M
  PSNR_out: PSNR outside M (checks that the rest of the image does not get worse)
Per-view values are averaged over the test views whose mask is non-empty.

The mask is computed ONLY from the ground-truth test image, with point_cloud_init/detect_2d.detect and its
DEFAULTS (ridge lines, blobs ignored), dilated by --dilate px. Masks are cached per scene under --mask_dir so
that all methods are evaluated on exactly the same pixels; a cached mask whose size differs from a method's
GT image aborts the run.

usage:
  python tools/thin_metrics.py --mask_dir eval_out/_thin_masks \
      --models eval_out/ours/mill19/rubble eval_out/scaffold-gs/mill19/rubble ...
  python tools/thin_metrics.py --mask_dir eval_out/_thin_masks --root eval_out   # every <algo>/<dataset>/<scene>
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "point_cloud_init"))
import detect_2d  # noqa: E402


def disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def make_mask(gt_rgb, dilate):
    gray = gt_rgb.astype(np.float32).mean(2) / 255.0
    det = detect_2d.detect(gray)
    line = det["mask_bright"] | det["mask_dark"]
    return ndi.binary_dilation(line, structure=disk(dilate)) if dilate > 0 else line


def ssim_map(a, b):
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    out = []
    for c in range(3):
        x, y = a[..., c], b[..., c]
        f = lambda z: ndi.gaussian_filter(z, 1.5, truncate=3.5)
        mx, my = f(x), f(y)
        sxx, syy, sxy = f(x * x) - mx * mx, f(y * y) - my * my, f(x * y) - mx * my
        out.append(((2 * mx * my + C1) * (2 * sxy + C2)) / ((mx * mx + my * my + C1) * (sxx + syy + C2)))
    return np.mean(out, 0)


class LpipsMap:
    def __init__(self):
        import torch
        import lpips
        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.net = lpips.LPIPS(net="vgg", spatial=True, verbose=False).to(self.dev).eval()

    def __call__(self, a, b):
        t = lambda z: self.torch.from_numpy(z).permute(2, 0, 1)[None].float().to(self.dev) * 2 - 1
        with self.torch.no_grad():
            return self.net(t(a), t(b))[0, 0].cpu().numpy()


def psnr(a, b, m):
    return float(10 * np.log10(1.0 / max(((a - b) ** 2)[m].mean(), 1e-12)))


def find_render_dir(model):
    cands = sorted(Path(model).glob("test/ours_*"), key=lambda p: int(p.name.split("_")[-1]))
    cands = [p for p in cands if (p / "renders").is_dir() and (p / "gt").is_dir()]
    if not cands:
        raise FileNotFoundError(f"no test/ours_*/renders + gt under {model}")
    return cands[-1]


def scene_key(model, root):
    p = Path(model).resolve()
    if root:
        parts = p.relative_to(Path(root).resolve()).parts
        return "/".join(parts[1:])                                  # drop the algorithm name
    return "/".join(p.parts[-2:])                                   # <dataset>/<scene>


def evaluate(model, mask_root, dilate, lp, root=None):
    rd = find_render_dir(model)
    key = scene_key(model, root)
    mdir = Path(mask_root) / key
    mdir.mkdir(parents=True, exist_ok=True)
    per_view = {}
    for fn in sorted(os.listdir(rd / "gt")):
        gt = np.asarray(Image.open(rd / "gt" / fn).convert("RGB"))
        img = np.asarray(Image.open(rd / "renders" / fn).convert("RGB"))
        mp = mdir / (os.path.splitext(fn)[0] + ".png")
        if mp.exists():
            m = np.asarray(Image.open(mp)) > 127
            if m.shape != gt.shape[:2]:
                raise SystemExit(f"cached mask {mp} is {m.shape}, GT is {gt.shape[:2]}: resolutions differ")
        else:
            m = make_mask(gt, dilate)
            Image.fromarray((m * 255).astype(np.uint8)).save(mp)
        if not m.any():
            continue
        a, b = gt.astype(np.float32) / 255, img.astype(np.float32) / 255
        s, l = ssim_map(a, b), lp(a, b)
        per_view[fn] = dict(PSNR_M=psnr(a, b, m), SSIM_M=float(s[m].mean()), LPIPS_M=float(l[m].mean()),
                            PSNR_out=psnr(a, b, ~m), coverage=float(m.mean()))
    keys = ["PSNR_M", "SSIM_M", "LPIPS_M", "PSNR_out", "coverage"]
    mean = {k: float(np.mean([v[k] for v in per_view.values()])) for k in keys}
    res = dict(scene=key, render_dir=str(rd), dilate=dilate, n_views=len(per_view), mean=mean, per_view=per_view)
    json.dump(res, open(Path(model) / "results_thin.json", "w"), indent=2)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--root", default=None, help="eval_out root: evaluate every <algo>/<dataset>/<scene>")
    ap.add_argument("--mask_dir", required=True)
    ap.add_argument("--dilate", type=int, default=2, help="mask dilation radius in px (at render resolution)")
    args = ap.parse_args()
    models = list(args.models)
    if args.root:
        models += sorted(str(p.parents[2]) for p in Path(args.root).glob("*/*/*/test/ours_*/renders"))
        models = sorted(set(m for m in models if "_thin_masks" not in m))
    lp = LpipsMap()
    for m in models:
        r = evaluate(m, args.mask_dir, args.dilate, lp, args.root)
        e = r["mean"]
        print(f"{m}: views {r['n_views']}  PSNR_M {e['PSNR_M']:.2f}  SSIM_M {e['SSIM_M']:.3f}  "
              f"LPIPS_M {e['LPIPS_M']:.3f}  PSNR_out {e['PSNR_out']:.2f}  coverage {100 * e['coverage']:.1f}%")


if __name__ == "__main__":
    main()
