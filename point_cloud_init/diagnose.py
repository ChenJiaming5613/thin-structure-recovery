"""Quantitative comparison of supplementary point sets on one frame.

For each thin_dir it reports, in the given frame:
  * visible supplementary points (approximate z-buffer from the COLMAP cloud)
  * how many fall into a region-of-interest box (e.g. the light string) vs. the rest
  * ROI recall: fraction of detected 2D line pixels inside the ROI with a supplementary
    point projected within `--cover_px`
and writes a side-by-side crop of the reprojections.

Example:
  python diagnose.py -s <scene> --frame 11 --roi 470 0 760 110 --lower 270 \
      --dirs <scene>/thin_init <scene>/thin_init_A
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

import common
import detect_2d


def zbuffer(K, W, H, v, xyz, radius=4):
    u, w, z = common.project(K, v.R, v.t, xyz)
    ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
    zb = np.full((H, W), np.inf, np.float32)
    np.minimum.at(zb, (w[ok].astype(int), u[ok].astype(int)), z[ok].astype(np.float32))
    return ndi.grey_erosion(zb, size=(2 * radius + 1, 2 * radius + 1))


def load_xyz(d):
    a = common.read_ply(os.path.join(d, "thin_points.ply"))
    return np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64), a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--scene", required=True)
    ap.add_argument("--images", default="images")
    ap.add_argument("--frame", type=int, required=True, help="1-based")
    ap.add_argument("--roi", type=int, nargs=4, required=True, help="x0 y0 x1 y1")
    ap.add_argument("--lower", type=int, default=None, help="also count points with v > lower (e.g. ground/vehicle)")
    ap.add_argument("--roi_line_ymax", type=int, default=None, help="only use line pixels with y < this for recall")
    ap.add_argument("--cover_px", type=float, default=3.0)
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sc = common.load_scene(args.scene, args.images)
    K, W, H = sc["K"], sc["W"], sc["H"]
    v = sc["views"][args.frame - 1]
    zb = zbuffer(K, W, H, v, sc["xyz"])
    gray, rgb = common.load_gray_rgb(os.path.join(sc["img_dir"], v.name))
    det = detect_2d.detect(gray)
    line = det["mask_bright"] | det["mask_dark"]
    x0, y0, x1, y1 = args.roi
    ys, xs = np.nonzero(line)
    ymax = args.roi_line_ymax if args.roi_line_ymax is not None else y1
    sel = (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < ymax)
    roi_px = np.stack([xs[sel], ys[sel]], 1) + 0.5

    tiles = []
    print(f"frame {v.name}: ROI line pixels {len(roi_px)}")
    for d in args.dirs:
        X, a = load_xyz(d)
        u, w, z = common.project(K, v.R, v.t, X)
        ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
        ui, wi = np.clip(u.astype(int), 0, W - 1), np.clip(w.astype(int), 0, H - 1)
        vis = ok & (z <= zb[wi, ui] / 0.97)
        in_roi = vis & (u >= x0) & (u < x1) & (w >= y0) & (w < y1)
        msg = f"  {os.path.basename(os.path.normpath(d)):>16}: total {len(X):6d} | visible {vis.sum():5d} | ROI {in_roi.sum():5d}"
        if args.lower is not None:
            msg += f" | v>{args.lower}: {(vis & (w > args.lower)).sum():5d}"
        if len(roi_px) and vis.any():
            dd, _ = cKDTree(np.stack([u[vis], w[vis]], 1)).query(roi_px)
            msg += f" | ROI recall {100 * (dd < args.cover_px).mean():5.1f}%"
        msg += f" | blobs {(a['kind'] == 1).sum()}"
        print(msg)

        im = Image.fromarray((rgb * 0.55).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        for p, q in zip(u[vis], w[vis]):
            dr.rectangle((p - 1, q - 1, p + 1, q + 1), fill=(255, 40, 40))
        dr.text((x0 + 3, y0 + 3), os.path.basename(os.path.normpath(d)), fill=(255, 255, 0))
        tiles.append(im)

    if args.out:
        cw, ch = x1 - x0, y1 - y0
        sc_ = max(1, 1300 // cw)
        crops = [Image.fromarray(rgb).crop((x0, y0, x1, y1))] + [t.crop((x0, y0, x1, y1)) for t in tiles]
        crops = [c.resize((cw * sc_, ch * sc_), Image.NEAREST) for c in crops]
        canvas = Image.new("RGB", (cw * sc_, ch * sc_ * len(crops)))
        for k, c in enumerate(crops):
            canvas.paste(c, (0, k * ch * sc_))
        canvas.save(args.out + "_roi.png")
        full = Image.new("RGB", (W, H * len(tiles)))
        for k, t in enumerate(tiles):
            full.paste(t, (0, k * H))
        full.save(args.out + "_full.png")
        print("wrote", args.out + "_roi.png", args.out + "_full.png")


if __name__ == "__main__":
    main()
