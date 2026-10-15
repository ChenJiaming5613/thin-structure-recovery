"""Export the cached monocular depth maps (<thin_dir>/cache_mono/*.npz) as PNG images.

--kind
  disp   raw relative disparity predicted by Depth Anything V2 (no units, larger = closer)
  depth  disparity aligned to the COLMAP scale with background_fit.json: z = 1 / (a*disp + b)
  bg     the background depth the sweep actually uses: COLMAP tile depth where available, aligned
         monocular depth (max-filtered by --dilate px) elsewhere. Needs -s/--scene.

Outputs per frame, in --out (default <thin_dir>/depth_png/<kind>/):
  <name>.png       colour visualisation (turbo; near = red, far = blue, invalid / +inf = black).
                   depth/bg use a log scale.
  <name>_16.png    with --raw16 (depth/bg only): uint16 depth * --scale, 0 = invalid / +inf
                   (default scale 1000 -> value / 1000 = depth in COLMAP units)
  --with_rgb puts the RGB frame above the visualisation (needs -s/--scene).

Example:
  python depth_to_png.py --thin_dir <scene>/thin_init --kind depth --frames 40-60 --raw16
  python depth_to_png.py --thin_dir <scene>/thin_init -s <scene> --images images_4 --kind bg --with_rgb
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

import common


def turbo(x):
    """Polynomial approximation of the turbo colormap. x in [0,1] -> uint8 RGB."""
    x = np.clip(x, 0.0, 1.0)
    r = 0.13572138 + x * (4.61539260 + x * (-42.66032258 + x * (132.13108234 + x * (-152.94239396 + x * 59.28637943))))
    g = 0.09140261 + x * (2.19418839 + x * (4.84296658 + x * (-14.18503333 + x * (4.27729857 + x * 2.82956604))))
    b = 0.10667330 + x * (12.64194608 + x * (-60.58204836 + x * (110.36276771 + x * (-89.90310912 + x * 27.34824973))))
    return (np.clip(np.stack([r, g, b], -1), 0, 1) * 255).astype(np.uint8)


def colorize(val, valid, lo, hi, log, near_high):
    """Map val to colours. near_high: True if larger values mean closer (disparity)."""
    v = np.where(valid, val, lo).astype(np.float64)
    if log:
        x = (np.log(np.clip(v, lo, hi)) - np.log(lo)) / max(np.log(hi) - np.log(lo), 1e-12)
    else:
        x = (np.clip(v, lo, hi) - lo) / max(hi - lo, 1e-12)
    if not near_high:
        x = 1.0 - x  # depth: small = near = red
    rgb = turbo(x)
    rgb[~valid] = 0
    return rgb


def value_range(val, valid, pct):
    if not valid.any():
        return 1.0, 2.0
    lo, hi = np.percentile(val[valid], [pct, 100 - pct])
    if hi <= lo:
        hi = lo * 1.01 + 1e-6
    return float(lo), float(hi)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--thin_dir", required=True, help="output folder of triangulate.py (contains cache_mono/)")
    ap.add_argument("--kind", default="depth", choices=["disp", "depth", "bg"])
    ap.add_argument("-s", "--scene", default=None, help="scene folder (needed for --kind bg and --with_rgb)")
    ap.add_argument("--images", default="images")
    ap.add_argument("--frames", default="all", help="1-based ranges over the name-sorted cache files, e.g. 40-60")
    ap.add_argument("--out", default=None)
    ap.add_argument("--range", type=float, nargs=2, default=None,
                    help="fixed colour range (lo hi) shared by all frames; default = per-frame percentiles")
    ap.add_argument("--pct", type=float, default=2.0, help="percentile clip for the per-frame colour range")
    ap.add_argument("--raw16", action="store_true", help="also write uint16 depth PNGs (depth/bg)")
    ap.add_argument("--scale", type=float, default=1000.0, help="uint16 value = depth * scale")
    ap.add_argument("--with_rgb", action="store_true")
    ap.add_argument("--dilate", type=int, default=8, help="--kind bg: max-filter radius, same as --bg_dilate")
    args = ap.parse_args()

    cache = os.path.join(args.thin_dir, "cache_mono")
    names = sorted(f[:-4] for f in os.listdir(cache) if f.endswith(".npz"))
    sel = [names[i] for i in common.parse_frames(args.frames, len(names))]
    out = args.out or os.path.join(args.thin_dir, "depth_png", args.kind)
    os.makedirs(out, exist_ok=True)

    fits = {}
    fit_path = os.path.join(args.thin_dir, "background_fit.json")
    if args.kind in ("depth", "bg"):
        if not os.path.exists(fit_path):
            raise SystemExit(f"{fit_path} not found (run triangulate.py with --bg fill/max first)")
        with open(fit_path) as fp:
            fits = {os.path.splitext(k)[0]: v for k, v in json.load(fp).items()}

    scene, by_name = None, {}
    if args.kind == "bg" or args.with_rgb:
        if not args.scene:
            raise SystemExit("--kind bg / --with_rgb need -s/--scene")
        scene = common.load_scene(args.scene, args.images)
        by_name = {os.path.splitext(v.name)[0]: v for v in scene["views"]}
    if args.kind == "bg":
        import mono_depth
        import triangulate

    n_skip = 0
    for k, name in enumerate(sel):
        disp = np.load(os.path.join(cache, name + ".npz"))["disp"].astype(np.float32)
        if args.kind == "disp":
            val, valid, log, near_high = disp, np.isfinite(disp), False, True
        else:
            fit = fits.get(name)
            if args.kind == "depth":
                if fit is None or "a" not in fit:
                    n_skip += 1
                    continue
                val = mono_depth_aligned(disp, fit["a"], fit["b"])
            else:
                v = by_name[name]
                K, W, H = scene["K"], scene["W"], scene["H"]
                tiles = triangulate.SurfaceDepth(K, W, H, v, scene["xyz"])
                if fit is not None and fit.get("used"):
                    z = mono_depth.aligned_depth(disp, fit["a"], fit["b"])
                    val = triangulate.DenseBackground(tiles, z, "fill", args.dilate).z.astype(np.float32)
                else:
                    yy, xx = np.mgrid[0:H, 0:W]
                    val = tiles.lookup(xx + 0.5, yy + 0.5)
            valid = np.isfinite(val) & (val > 0)
            log, near_high = True, False

        lo, hi = args.range if args.range else value_range(val, valid, args.pct)
        vis = colorize(val, valid, lo, hi, log, near_high)
        if args.with_rgb:
            _, rgb = common.load_gray_rgb(os.path.join(scene["img_dir"], by_name[name].name))
            if rgb.shape[:2] != vis.shape[:2]:
                rgb = np.asarray(Image.fromarray(rgb).resize(vis.shape[1::-1], Image.BILINEAR))
            vis = np.concatenate([rgb, vis], 0)
        Image.fromarray(vis).save(os.path.join(out, name + ".png"))

        if args.raw16 and args.kind != "disp":
            q = np.where(valid, np.round(val * args.scale), 0)
            q = np.clip(q, 0, 65535).astype(np.uint16)
            Image.fromarray(q).save(os.path.join(out, name + "_16.png"))
        if (k + 1) % 20 == 0 or k + 1 == len(sel):
            print(f"  {k + 1}/{len(sel)}  ({name}: range {lo:.3g}-{hi:.3g}, valid {100 * valid.mean():.0f}%)")
    if n_skip:
        print(f"skipped {n_skip} frames without an alignment in background_fit.json")
    print("wrote", out)


def mono_depth_aligned(disp, a, b, min_inv=1e-4):
    inv = a * disp + b
    return np.where(inv > min_inv, 1.0 / np.maximum(inv, min_inv), np.inf).astype(np.float32)


if __name__ == "__main__":
    main()
