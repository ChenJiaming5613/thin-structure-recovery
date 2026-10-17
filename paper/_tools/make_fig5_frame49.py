"""Fig.5 panels (frame 49 of Rubble), one per step of anchor seeding:
  f049_ridge.png     (a) 2D thin-structure candidates (same detect_2d.detect + defaults as the seeding run)
  f049_mono_depth.png(b) monocular depth aligned to the SfM scale
  f049_decision.png  (c) per-candidate decision of this reference frame:
                         green  = accepted (solid, suspended, not covered by SfM, corroborated)
                         red    = rejected by the suspension test (best depth not in front of the background,
                                  or no room in front of it)
                         orange = rejected otherwise (insufficient / ambiguous multi-view support, small
                                  triangulation angle, covered by SfM points, not corroborated)
The decision re-runs triangulate.process_reference on frame 49 with the parameters stored in
<thin_init>/stats.json, on *all* ridge pixels of the frame (the seeding run subsamples them to
max_line_samples per frame). Cross-reference corroboration uses <thin_init>/raw_points.npz of the other
reference frames. Re-run this script after re-running the seeding.
All panels at images_4 resolution, rows CROP_Y kept.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "..", "point_cloud_init"))
import common  # noqa: E402
import detect_2d  # noqa: E402
import triangulate as T  # noqa: E402

SCENE = r"D:/GS/Scaffold-GS/dataset/rubble200"
THIN = os.path.join(SCENE, "thin_init")
FRAME = 49
FIG = os.path.join(ROOT, "figures")
DIM = 0.7
CROP_Y = (0, 520)          # keep the upper part of the frame (wire + poles)
RIDGE_COLOR = (0, 255, 255)
BLOB_COLOR = (255, 230, 0)
THICKEN = 1                # dilate 1-px masks by this many px so they survive print size
GREEN, RED, ORANGE = (40, 230, 60), (255, 30, 30), (255, 150, 0)


def dimmed(rgb):
    return (rgb.astype(np.float32) * DIM).astype(np.uint8)


def paint(vis, xy, color):
    m = np.zeros(vis.shape[:2], bool)
    m[xy[:, 1].astype(int), xy[:, 0].astype(int)] = True
    if THICKEN:
        m = ndi.binary_dilation(m, iterations=THICKEN)
    vis[m] = color


def ridge_panel(gray, rgb, det):
    line = det["mask_bright"] | det["mask_dark"]
    vis = dimmed(rgb)
    ys, xs = np.nonzero(line)
    paint(vis, np.stack([xs, ys], 1), RIDGE_COLOR)
    im = Image.fromarray(vis)
    dr = ImageDraw.Draw(im)
    for x, y in det["blob_xy"]:
        dr.ellipse((x - 3, y - 3, x + 3, y + 3), outline=BLOB_COLOR, width=2)
    return im, int(line.sum()), len(det["blob_xy"])


def decide(sc, i, det):
    run = json.load(open(os.path.join(THIN, "stats.json"), encoding="utf-8"))
    args = argparse.Namespace(**run["args"])
    K, W, H, views = sc["K"], sc["W"], sc["H"], sc["views"]
    ids = common.parse_frames(args.frames, len(views))
    med = T.visible_depth_range(K, W, H, views[i], sc["xyz"])[1]
    nbrs = T.choose_neighbors(views, i, ids, med, args.n_nbr, args.min_base_ratio, args.max_view_angle)
    use = [i] + nbrs
    feats = T.load_or_detect(sc, views, use, os.path.join(THIN, "cache"), {}, args.max_line_samples, args.seed)
    feats["views"] = views
    if args.free_space:
        feats["surf"], _ = T.build_backgrounds(sc, use, args, THIN)
    line = det["mask_bright"] | det["mask_dark"]
    ys, xs = np.nonzero(line)
    feats[i] = dict(feats[i], line_xy=np.stack([xs, ys], 1).astype(np.float32))
    if not args.blob:
        feats[i]["blob_xy"] = feats[i]["blob_xy"][:0]
    res, _, (xy, is_line, code) = T.process_reference(sc, i, nbrs, feats, args, labels=True)
    code = code.astype(np.int16)

    if res is not None:
        foot = res["depth"] / K[0, 0]
        R = np.load(os.path.join(THIN, "raw_points.npz"))
        other = R["ref"] != i
        oxyz, oref = R["xyz"][other], R["ref"][other]
        nb = cKDTree(oxyz).query_ball_point(res["xyz"], r=args.support_px * foot)
        corr = np.array([len(set(oref[j])) >= args.min_ref_support for j in nb], bool)
        ctree = cKDTree(sc["xyz"])
        d_nn, j_nn = ctree.query(res["xyz"], k=1)
        new = d_nn > args.far_px * foot
        if args.far_spacing > 0:
            sp, _ = ctree.query(sc["xyz"], k=args.spacing_k + 1)
            new &= d_nn > args.far_spacing * sp[:, 1:].mean(1)[j_nn]
        code[res["cand"][~corr]] = 5
        code[res["cand"][corr & ~new]] = 6
    return xy, is_line, code, len(nbrs)


def decision_panel(rgb, xy, code):
    vis = dimmed(rgb)
    groups = [(np.isin(code, (2, 4, 5, 6)), ORANGE), (np.isin(code, (1, 3)), RED), (code == 0, GREEN)]
    for m, c in groups:
        if m.any():
            paint(vis, xy[m], c)
    return Image.fromarray(vis)


def main():
    sc = common.load_scene(SCENE, "images_4")
    W, H = sc["W"], sc["H"]
    i = FRAME - 1
    v = sc["views"][i]
    tag = os.path.splitext(v.name)[0]
    box = (0, CROP_Y[0], W, CROP_Y[1])

    dep = Image.open(os.path.join(THIN, "depth_png", "depth", f"{tag}.png")).convert("RGB")
    assert dep.size == (W, H), "depth png resolution differs from images_4"
    dep.crop(box).save(os.path.join(FIG, "f049_mono_depth.png"))

    gray, rgb = common.load_gray_rgb(os.path.join(sc["img_dir"], v.name))
    det = detect_2d.detect(gray)
    rim, n_line, n_blob = ridge_panel(gray, rgb, det)
    rim.crop(box).save(os.path.join(FIG, "f049_ridge.png"))

    xy, is_line, code, n_nbr = decide(sc, i, det)
    decision_panel(rgb, xy, code).crop(box).save(os.path.join(FIG, "f049_decision.png"))

    names = {0: "accepted", 1: "no free space (suspension)", 2: "multi-view support", 3: "on surface (suspension)",
             4: "triangulation angle", 5: "not corroborated", 6: "covered by SfM"}
    inside = (xy[:, 1] >= CROP_Y[0]) & (xy[:, 1] < CROP_Y[1])
    print(f"{v.name}: {n_line} ridge px, {n_blob} blobs, {n_nbr} neighbour views, {len(xy)} candidates")
    for k, s in names.items():
        print(f"  {k} {s:28s} all {int((code == k).sum()):6d}   in crop {int(((code == k) & inside).sum()):6d}")
    green, red = code == 0, np.isin(code, (1, 3))
    print(f"  green {int(green.sum())}  red {int(red.sum())}  orange {int(len(code) - green.sum() - red.sum())}")


if __name__ == "__main__":
    main()
