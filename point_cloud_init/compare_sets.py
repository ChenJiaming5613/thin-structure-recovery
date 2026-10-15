"""Set-difference analysis of supplementary point clouds against a baseline.

For every candidate folder it reports, relative to the baseline folder:
  * removed  : baseline points with no candidate point within --match m
  * added    : candidate points with no baseline point within --match m
and classifies both sets by their depth relative to the COLMAP background depth in their own
reference frame (in front / on surface / behind / no background). For each --frames entry it
writes <out>/frame<k>_<name>_diff.png (top: removed, blue; bottom: added, red).

Example:
  python compare_sets.py -s <scene> --base <scene>/thin_init \
      --cands <scene>/thin_init_A_r0 <scene>/thin_init_B_reject --frames 11 20 --out <dir>
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

import common
import diagnose
import triangulate


def rel_depth(scene, X, refs):
    """depth / background depth in the point's reference frame; inf background -> 0."""
    K, W, H, views = scene["K"], scene["W"], scene["H"], scene["views"]
    r = np.zeros(len(X))
    for i in np.unique(refs):
        m = refs == i
        v = views[i]
        sd = triangulate.SurfaceDepth(K, W, H, v, scene["xyz"], radius=0)
        u, w, z = common.project(K, v.R, v.t, X[m])
        zb = sd.lookup(u, w)
        r[m] = np.where(np.isfinite(zb), z / zb, 0.0)
    return r


def describe(r):
    n = max(len(r), 1)
    return ("no-bg {:3.0f}% | front {:3.0f}% | on-surface {:3.0f}% | behind {:3.0f}%".format(
        100 * np.sum(r == 0) / n, 100 * np.sum((r > 0) & (r < 0.9)) / n,
        100 * np.sum((r >= 0.9) & (r <= 1.1)) / n, 100 * np.sum(r > 1.1) / n))


def draw(scene, v, sets, path):
    K, W, H = scene["K"], scene["W"], scene["H"]
    zb = diagnose.zbuffer(K, W, H, v, scene["xyz"])
    rgb = np.asarray(Image.open(os.path.join(scene["img_dir"], v.name)).convert("RGB"))
    panels = []
    for label, X, col in sets:
        u, w, z = common.project(K, v.R, v.t, X)
        ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
        ui, wi = np.clip(u.astype(int), 0, W - 1), np.clip(w.astype(int), 0, H - 1)
        vis = ok & (z <= zb[wi, ui] / 0.97)
        im = Image.fromarray((rgb * 0.5).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        for p, q in zip(u[vis], w[vis]):
            dr.rectangle((p - 1, q - 1, p + 1, q + 1), fill=col)
        dr.text((6, 6), f"{label}: {vis.sum()} visible", fill=(255, 255, 0))
        panels.append(im)
    out = Image.new("RGB", (W, H * len(panels)))
    for k, p in enumerate(panels):
        out.paste(p, (0, k * H))
    out.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--scene", required=True)
    ap.add_argument("--images", default="images")
    ap.add_argument("--base", required=True)
    ap.add_argument("--cands", nargs="+", required=True)
    ap.add_argument("--frames", type=int, nargs="*", default=[], help="1-based frames to draw")
    ap.add_argument("--match", type=float, default=0.05, help="match radius in scene units")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sc = common.load_scene(args.scene, args.images)
    Xb, ab = diagnose.load_xyz(args.base)
    rb = rel_depth(sc, Xb, ab["ref"].astype(int))
    print(f"base {os.path.basename(os.path.normpath(args.base))}: {len(Xb)} pts | {describe(rb)}")
    if args.out:
        os.makedirs(args.out, exist_ok=True)
    tb = cKDTree(Xb)
    for d in args.cands:
        name = os.path.basename(os.path.normpath(d))
        Xc, ac = diagnose.load_xyz(d)
        rc = rel_depth(sc, Xc, ac["ref"].astype(int))
        dc, _ = cKDTree(Xc).query(Xb)
        db, _ = tb.query(Xc)
        removed, added = dc > args.match, db > args.match
        print(f"\n{name}: {len(Xc)} pts | {describe(rc)}")
        print(f"  removed {removed.sum():6d} | {describe(rb[removed])}")
        print(f"  added   {added.sum():6d} | {describe(rc[added])}")
        if args.out:
            for f in args.frames:
                draw(sc, sc["views"][f - 1],
                     [(f"removed vs base ({name})", Xb[removed], (80, 160, 255)),
                      (f"added vs base ({name})", Xc[added], (255, 40, 40))],
                     os.path.join(args.out, f"frame{f}_{name}_diff.png"))


if __name__ == "__main__":
    main()
