"""Fig.6(d): the "ours" free-view screenshot with the seeded points highlighted in green.

Re-projects the cropped point sets of the fly-through viewer with the exact camera of the screenshot
(same lookAt / perspective as fly_viewer.py) and paints the visible seeded points green on top of
figures/ours_init_custom_view.png (real-colour screenshot of mode B, same pose), so (c) and (d) differ
only in the colour of the seeded points.

  python make_fig6_mark.py            -> figures/ours_init_custom_view_mark.png
  python make_fig6_mark.py --check    -> also compares the projection with the old red-marked panel
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "..", "point_cloud_init"))
import common  # noqa: E402

FIG = os.path.join(ROOT, "figures")
CLOUD = r"D:/GS/Scaffold-GS/dataset/rubble200/edgs_init/fly/crop_B_colmap_plus_ours.ply"
POSE = {"p": [-1.3748690485288038, -1.8281030081736263, 4.061163952014318],
        "f": [0.0032194875908518536, -0.6750355054429836, 0.7377782195829504],
        "u": [0.05929214635377273, -0.7363551708202474, -0.6739922134468966],
        "fov": 60, "hmin": 0, "hmax": 1000}
GREEN = (40, 230, 60)


def nrm(a):
    return a / np.linalg.norm(a)


def project(X, pose, W, H):
    """fly_viewer.py: lookAt(p, p+f, u) and persp(fov (vertical), W/H). Returns pixel u, v and view depth."""
    e, f, up = (np.asarray(pose[k], float) for k in ("p", "f", "u"))
    z = nrm(-f)
    x = nrm(np.cross(up, z))
    y = np.cross(z, x)
    d = X - e
    xc, yc, zc = d @ x, d @ y, d @ z
    depth = -zc
    t = 1.0 / np.tan(np.radians(pose["fov"]) / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        u = (xc * t / (W / H) / depth + 1) / 2 * W
        v = (1 - yc * t / depth) / 2 * H
    return u, v, depth


def splat_zbuffer(u, v, depth, W, H, r):
    zb = np.full((H, W), np.inf, np.float32)
    ok = (depth > 0) & np.isfinite(u) & (u >= -r) & (u < W + r) & (v >= -r) & (v < H + r)
    ui, vi, dz = np.round(u[ok]).astype(int), np.round(v[ok]).astype(int), depth[ok].astype(np.float32)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            a, b = ui + dx, vi + dy
            m = (a >= 0) & (a < W) & (b >= 0) & (b < H)
            np.minimum.at(zb, (b[m], a[m]), dz[m])
    return zb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.path.join(FIG, "ours_init_custom_view.png"))
    ap.add_argument("--out", default=os.path.join(FIG, "ours_init_custom_view_mark.png"))
    ap.add_argument("--r_colmap", type=int, default=1, help="splat radius (px) of COLMAP points for occlusion")
    ap.add_argument("--r_seed", type=int, default=2, help="drawn radius (px) of seeded points")
    ap.add_argument("--check", default=None, help="old red-marked panel to compare the projection with")
    ap.add_argument("--pose", default=None, help="pose JSON string exported from the viewer")
    args = ap.parse_args()
    pose = json.loads(args.pose) if args.pose else POSE
    if (pose.get("hmin", 0), pose.get("hmax", 1000)) != (0, 1000):
        raise SystemExit("height clip is not reproduced; export the pose with hmin=0, hmax=1000")

    base = np.asarray(Image.open(args.base).convert("RGB")).copy()
    H, W = base.shape[:2]
    a = common.read_ply(CLOUD)
    X = np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)
    thin = np.asarray(a["is_thin"]) > 0.5
    u, v, z = project(X, pose, W, H)

    zb = splat_zbuffer(u[~thin], v[~thin], z[~thin], W, H, args.r_colmap)
    us, vs, zs = u[thin], v[thin], z[thin]
    inside = (zs > 0) & (us >= 0) & (us < W) & (vs >= 0) & (vs < H)
    ui = np.clip(np.round(us).astype(int), 0, W - 1)
    vi = np.clip(np.round(vs).astype(int), 0, H - 1)
    visible = inside & (zs <= zb[vi, ui] * 1.01)
    order = np.argsort(-zs[visible])                       # far first, near seeds on top
    r = args.r_seed
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disk = (xx ** 2 + yy ** 2) <= r * r + 0.5
    for x0, y0 in zip(ui[visible][order], vi[visible][order]):
        for dx, dy in zip(xx[disk], yy[disk]):
            a_, b_ = x0 + dx, y0 + dy
            if 0 <= a_ < W and 0 <= b_ < H:
                base[b_, a_] = GREEN
    Image.fromarray(base).save(args.out)
    print(f"{args.out}: {W}x{H}, seeded points in view {int(inside.sum())}, drawn (not occluded) {int(visible.sum())}")

    if args.check:
        old = np.asarray(Image.open(args.check).convert("RGB")).astype(int)
        red = (old[..., 0] > 200) & (old[..., 1] < 90) & (old[..., 2] < 90)
        from scipy import ndimage as ndi
        near = ndi.binary_dilation(red, iterations=3)
        hit = near[vi[inside], ui[inside]].mean()
        ys, xs = np.nonzero(red)
        print(f"check: {red.sum()} red px in old panel, centroid ({xs.mean():.1f}, {ys.mean():.1f}); "
              f"projected seeds centroid ({us[inside].mean():.1f}, {vs[inside].mean():.1f}); "
              f"{100 * hit:.1f}% of projected seeds land within 3 px of an old red pixel")


if __name__ == "__main__":
    main()
