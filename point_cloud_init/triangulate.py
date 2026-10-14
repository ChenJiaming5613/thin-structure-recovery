"""Generate supplementary initial points on thin / suspended structures.

Pipeline (poses + intrinsics are taken from the existing COLMAP model, nothing is re-estimated):
  1. per-frame 2D candidates (thin ridges + small blobs), see detect_2d.py
  2. per reference frame, sweep depths along the ray of every candidate pixel and count, in
     neighbouring frames, how many projections land on a candidate of the same kind
     (distance-transform lookup).  For line candidates, neighbour views whose epipolar line is
     nearly parallel to the local 2D line are treated as uninformative (degenerate).
     Free-space constraint (--free_space 1): the sweep of a reference pixel stops in front of the
     existing COLMAP surface seen through it, and a neighbour view does not vote for samples that
     lie behind its own known surface (they would be occluded there).
  3. accept a depth only if it is supported by enough views, by a large fraction of the
     informative views, and is a unique peak along the ray; refine it locally.
  4. keep points corroborated by other reference frames, drop points that coincide with the
     existing COLMAP cloud, voxel-downsample, write PLY.

Example:
  python tools/thin_init/triangulate.py -s dataset/tandt/truck --frames 1-40
"""
import argparse
import json
import os
import time

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

import common
import detect_2d

DT_SCALE = 20.0  # distance maps are stored as uint8(dist * DT_SCALE), i.e. up to 12.75 px


# ----------------------------------------------------------------------------- per-frame 2D features

def frame_features(path, det_cfg, max_line_samples, rng):
    gray, _ = common.load_gray_rgb(path)
    det = detect_2d.detect(gray, **det_cfg)
    line = det["mask_bright"] | det["mask_dark"]
    tan = np.where(det["mask_bright"], det["tan_bright"], det["tan_dark"])

    dt_l, (iy, ix) = ndi.distance_transform_edt(~line, return_indices=True)
    tan_near = tan[iy, ix]
    blob_xy = det["blob_xy"]
    bmask = np.zeros_like(line)
    if len(blob_xy):
        bmask[blob_xy[:, 1].astype(int), blob_xy[:, 0].astype(int)] = True
    dt_b = ndi.distance_transform_edt(~bmask) if bmask.any() else np.full(line.shape, 1e3)

    ys, xs = np.nonzero(line)
    if len(xs) > max_line_samples:
        sel = rng.choice(len(xs), max_line_samples, replace=False)
        xs, ys = xs[sel], ys[sel]
    return dict(
        dt_line=np.clip(dt_l * DT_SCALE, 0, 255).astype(np.uint8),
        tan=(np.mod(np.degrees(tan_near), 180.0)).astype(np.uint8),
        dt_blob=np.clip(dt_b * DT_SCALE, 0, 255).astype(np.uint8),
        line_xy=np.stack([xs, ys], 1).astype(np.float32),
        blob_xy=blob_xy.astype(np.float32),
        n_line_px=int(line.sum()),
    )


def load_or_detect(scene, views, ids, cache_dir, det_cfg, max_line_samples, seed):
    os.makedirs(cache_dir, exist_ok=True)
    cfg_tag = json.dumps({**detect_2d.DEFAULTS, **{k: v for k, v in det_cfg.items() if v is not None},
                          "max_line_samples": max_line_samples}, sort_keys=True, default=list)
    feats = {}
    t0 = time.time()
    for n, i in enumerate(ids):
        v = views[i]
        f = os.path.join(cache_dir, os.path.splitext(v.name)[0] + ".npz")
        if os.path.exists(f):
            z = np.load(f, allow_pickle=False)
            if str(z["cfg"]) == cfg_tag:
                feats[i] = {k: z[k] for k in z.files if k != "cfg"}
                continue
        rng = np.random.default_rng(seed + i)
        ft = frame_features(os.path.join(scene["img_dir"], v.name), det_cfg, max_line_samples, rng)
        np.savez_compressed(f, cfg=cfg_tag, **ft)
        feats[i] = ft
        if (n + 1) % 20 == 0 or n + 1 == len(ids):
            print(f"  detect {n + 1}/{len(ids)}  ({time.time() - t0:.0f}s)")
    return feats


# ----------------------------------------------------------------------------- geometry

def choose_neighbors(views, ref, pool, med_depth, n_nbr, min_base_ratio, max_view_angle):
    vr = views[ref]
    cand = []
    for j in pool:
        if j == ref:
            continue
        vj = views[j]
        base = np.linalg.norm(vj.C - vr.C)
        ang = np.degrees(np.arccos(np.clip(vr.fwd @ vj.fwd, -1, 1)))
        if base >= min_base_ratio * med_depth and ang <= max_view_angle:
            cand.append((base, j))
    cand.sort()
    return [j for _, j in cand[:n_nbr]]


def visible_depth_range(K, W, H, v, xyz):
    u, w, z = common.project(K, v.R, v.t, xyz)
    ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
    if ok.sum() < 20:
        return None
    zz = z[ok]
    return np.percentile(zz, 2), np.percentile(zz, 50), np.percentile(zz, 98)


class SurfaceDepth:
    """Coarse per-frame depth of the existing COLMAP surface ("background" depth).

    The image is split into `tile` x `tile` px cells. Each cell stores a low percentile of the
    camera-z depths of COLMAP points projecting into its (2r+1)^2 cell neighbourhood, or +inf if
    fewer than `min_count` points fall there (sky / unreconstructed regions).
    A low percentile instead of the minimum keeps a few wrong COLMAP points in front of the true
    surface from hiding the free space in front of it.
    """

    def __init__(self, K, W, H, v, xyz, tile=8, radius=1, pct=20.0, min_count=3, max_spread=0.0,
                 hi_pct=80.0):
        """max_spread > 0: a cell whose depths are not a single surface (p_hi / p_lo > max_spread,
        e.g. the silhouette of a pole in front of a facade) is left unconstrained (+inf)."""
        self.tile, self.W, self.H = tile, W, H
        tw, th = (W + tile - 1) // tile, (H + tile - 1) // tile
        self.grid = np.full((th, tw), np.inf, np.float32)
        u, w, z = common.project(K, v.R, v.t, xyz)
        ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
        if not ok.any():
            return
        tx, ty, z = (u[ok] // tile).astype(np.int64), (w[ok] // tile).astype(np.int64), z[ok]
        offs = [(dx, dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)]
        TX = np.concatenate([tx + dx for dx, _ in offs])
        TY = np.concatenate([ty + dy for _, dy in offs])
        Z = np.tile(z, len(offs))
        m = (TX >= 0) & (TX < tw) & (TY >= 0) & (TY < th)
        cell = TY[m] * tw + TX[m]
        Z = Z[m]
        order = np.lexsort((Z, cell))
        cell, Z = cell[order], Z[order]
        uc, start, cnt = np.unique(cell, return_index=True, return_counts=True)
        good = cnt >= min_count
        pick = start[good] + np.floor(pct / 100.0 * (cnt[good] - 1)).astype(np.int64)
        val = Z[pick]
        if max_spread > 0:
            pick_hi = start[good] + np.floor(hi_pct / 100.0 * (cnt[good] - 1)).astype(np.int64)
            val = np.where(Z[pick_hi] <= max_spread * val, val, np.inf)
        self.grid.reshape(-1)[uc[good]] = val

    def lookup(self, u, v):
        """u, v: float pixel coordinates (any shape). Out-of-image -> +inf."""
        tx = np.floor(u / self.tile).astype(np.int64)
        ty = np.floor(v / self.tile).astype(np.int64)
        th, tw = self.grid.shape
        inside = (tx >= 0) & (tx < tw) & (ty >= 0) & (ty < th)
        out = np.full(np.shape(u), np.inf, np.float32)
        out[inside] = self.grid[ty[inside], tx[inside]]
        return out


def pixel_rays(K, v, xy):
    """World-space ray directions (scaled to unit camera-z) through integer pixel indices.
    COLMAP convention: the centre of pixel index (x, y) is at (x + 0.5, y + 0.5)."""
    pix = np.concatenate([xy + 0.5, np.ones((len(xy), 1))], 1)
    return (pix @ np.linalg.inv(K).T) @ v.R


def sweep(K, W, H, vr, xy, is_line, depths, nbrs, feats, args, return_views=False, allowed=None):
    """xy: (S,2) pixel indices in ref, depths: (S,D) camera-z depths.
    allowed: optional (S,D) bool, samples outside it are never counted (free-space limit in ref).
    Returns hits, nvalid, cost (S,D) [, per-view hit mask (S,D,N)]."""
    rays = pixel_rays(K, vr, xy)
    X = vr.C[None, None, :] + depths[..., None] * rays[:, None, :]
    X2 = vr.C[None, None, :] + (depths * 1.002)[..., None] * rays[:, None, :]  # for epipolar direction
    S, D = depths.shape
    hits = np.zeros((S, D), np.int16)
    nvalid = np.zeros((S, D), np.int16)
    cost = np.zeros((S, D), np.float32)
    per_view = np.zeros((S, D, len(nbrs)), bool) if return_views else None
    tau, tau_c = args.tau, args.tau * 2
    min_deg = np.radians(args.degenerate_deg)
    line_col = is_line[:, None]
    surf = feats.get("surf") if args.free_space else None
    for n, j in enumerate(nbrs):
        vj, fj = feats["views"][j], feats[j]
        u, v, z = common.project(K, vj.R, vj.t, X)
        inb = (z > 1e-3) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        ui = np.clip(np.floor(u), 0, W - 1).astype(np.int32)
        vi = np.clip(np.floor(v), 0, H - 1).astype(np.int32)
        d = np.where(line_col, fj["dt_line"][vi, ui], fj["dt_blob"][vi, ui]).astype(np.float32) / DT_SCALE
        u2, v2, _ = common.project(K, vj.R, vj.t, X2)
        epi = np.arctan2(v2 - v, u2 - u)
        tn = np.radians(fj["tan"][vi, ui].astype(np.float32))
        diff = np.abs(np.angle(np.exp(2j * (epi - tn)))) / 2
        nondeg = ~line_col | (diff >= min_deg)
        valid = inb & nondeg
        if surf is not None:
            # a sample clearly behind the known surface of view j cannot be seen there: not a vote
            valid &= z <= args.occ_ratio * surf[j].lookup(u, v)
        if allowed is not None:
            valid &= allowed
        hit = valid & (d <= tau)
        hits += hit
        nvalid += valid
        cost += np.where(valid, np.minimum(d, tau_c), 0)
        if return_views:
            per_view[..., n] = hit
    return (hits, nvalid, cost, per_view) if return_views else (hits, nvalid, cost)


def process_reference(scene, i, nbrs, feats, args):
    K, W, H, views = scene["K"], scene["W"], scene["H"], scene["views"]
    vr = views[i]
    rng_d = visible_depth_range(K, W, H, vr, scene["xyz"])
    if rng_d is None or len(nbrs) < args.min_views:
        return None, None
    dmin, _, dmax = max(rng_d[0] * args.near_factor, 1e-2), rng_d[1], rng_d[2] * args.far_factor

    fr = feats[i]
    xy = np.concatenate([fr["line_xy"], fr["blob_xy"]], 0)
    is_line = np.concatenate([np.ones(len(fr["line_xy"]), bool), np.zeros(len(fr["blob_xy"]), bool)])
    if len(xy) == 0:
        return None, None

    inv = np.linspace(1.0 / dmin, 1.0 / dmax, args.n_depths)
    depths_all = 1.0 / inv  # increasing with the sample index

    # free-space constraint: only search in front of the known surface seen through this pixel
    if args.free_space:
        z_bg = feats["surf"][i].lookup(xy[:, 0] + 0.5, xy[:, 1] + 0.5).astype(np.float64)
        d_lim = np.minimum(dmax, args.front_ratio * z_bg)
        n_allow = np.searchsorted(depths_all, d_lim, side="right")  # samples [0, n_allow) are allowed
    else:
        d_lim = np.full(len(xy), dmax)
        n_allow = np.full(len(xy), args.n_depths)
    keep_c = n_allow >= args.min_free_samples
    stats = dict(cand=len(xy), cand_free=int(keep_c.sum()), samples=0)
    order = np.nonzero(keep_c)[0]
    order = order[np.argsort(-n_allow[order], kind="stable")]  # group long rays together
    xy, is_line, n_allow, d_lim = xy[order], is_line[order], n_allow[order], d_lim[order]

    out = []
    for s0 in range(0, len(xy), args.chunk):
        sl = slice(s0, s0 + args.chunk)
        cxy, cline, cna, cdl = xy[sl], is_line[sl], n_allow[sl], d_lim[sl]
        Dc = int(cna.max())
        dep = np.broadcast_to(depths_all[:Dc], (len(cxy), Dc)).copy()
        allowed = np.arange(Dc)[None, :] < cna[:, None]
        stats["samples"] += int(allowed.sum())
        hits, nval, cost = sweep(K, W, H, vr, cxy, cline, dep, nbrs, feats, args, allowed=allowed)

        mean_c = cost / np.maximum(nval, 1)
        key = hits.astype(np.float32) - 1e-3 * mean_c
        k = np.argmax(key, 1)
        r = np.arange(len(cxy))
        best, nv = hits[r, k], nval[r, k]
        far = np.abs(np.arange(Dc)[None, :] - k[:, None]) > args.unique_window
        second = np.where(far, hits, 0).max(1)
        ok = (best >= args.min_views) & (best >= args.min_ratio * np.maximum(nv, 1)) & (second <= best - args.unique_margin)
        if not ok.any():
            continue

        # local refinement between neighbouring depth samples (never past the free-space limit)
        idx = np.nonzero(ok)[0]
        k_lo = np.clip(k[idx] - 1, 0, args.n_depths - 1)
        k_hi = np.clip(k[idx] + 1, 0, args.n_depths - 1)
        t = np.linspace(0, 1, args.n_refine)[None, :]
        inv_ref = inv[k_lo][:, None] * (1 - t) + inv[k_hi][:, None] * t
        dep_ref = np.minimum(1.0 / inv_ref, cdl[idx][:, None])
        h2, n2, c2, pv = sweep(K, W, H, vr, cxy[idx], cline[idx], dep_ref, nbrs, feats, args, return_views=True)
        key2 = h2.astype(np.float32) - 1e-3 * c2 / np.maximum(n2, 1)
        k2 = np.argmax(key2, 1)
        r2 = np.arange(len(idx))
        d_fin = dep_ref[r2, k2]
        hv = pv[r2, k2]  # (n, N) which neighbour views support the point

        X = vr.C[None] + d_fin[:, None] * pixel_rays(K, vr, cxy[idx])

        # max triangulation angle among supporting views
        Cn = np.stack([views[j].C for j in nbrs], 0)
        a = X - vr.C[None]
        a /= np.linalg.norm(a, axis=1, keepdims=True)
        b = X[:, None, :] - Cn[None]
        b /= np.linalg.norm(b, axis=2, keepdims=True)
        ang = np.degrees(np.arccos(np.clip((a[:, None, :] * b).sum(2), -1, 1)))
        max_ang = np.where(hv, ang, 0).max(1)
        good = max_ang >= args.min_tri_angle
        if not good.any():
            continue
        out.append(dict(
            xyz=X[good], depth=d_fin[good], score=h2[r2, k2][good].astype(np.int16),
            kind=(~cline[idx][good]).astype(np.uint8), px=cxy[idx][good],
            tri=max_ang[good].astype(np.float32),
        ))
    if not out:
        return None, stats
    res = {k: np.concatenate([o[k] for o in out], 0) for k in out[0]}
    res["ref"] = np.full(len(res["xyz"]), i, np.int32)
    return res, stats


# ----------------------------------------------------------------------------- post filtering

def voxel_downsample(xyz, voxel, *attrs):
    key = np.floor(xyz / voxel).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    cnt = np.bincount(inv)
    mean = np.stack([np.bincount(inv, weights=xyz[:, d]) / cnt for d in range(3)], 1)
    return (mean,) + tuple(a[first] for a in attrs)


def sample_colors(scene, xyz, ref, px):
    from PIL import Image
    rgb = np.zeros((len(xyz), 3), np.uint8)
    for i in np.unique(ref):
        sel = ref == i
        im = np.asarray(Image.open(os.path.join(scene["img_dir"], scene["views"][i].name)).convert("RGB"))
        p = np.rint(px[sel]).astype(int)
        rgb[sel] = im[np.clip(p[:, 1], 0, im.shape[0] - 1), np.clip(p[:, 0], 0, im.shape[1] - 1)]
    return rgb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--scene", required=True, help="scene dir containing images/ and sparse/0/")
    ap.add_argument("--images", default="images")
    ap.add_argument("--out", default=None, help="output dir (default: <scene>/thin_init)")
    ap.add_argument("--frames", default="all", help="1-based frame ranges over name-sorted images, e.g. 1-40,230-251")
    # neighbours / sweep
    ap.add_argument("--n_nbr", type=int, default=16)
    ap.add_argument("--min_base_ratio", type=float, default=0.03, help="min baseline / median depth")
    ap.add_argument("--max_view_angle", type=float, default=60.0)
    ap.add_argument("--n_depths", type=int, default=192)
    ap.add_argument("--n_refine", type=int, default=9)
    ap.add_argument("--near_factor", type=float, default=0.3)
    ap.add_argument("--far_factor", type=float, default=1.2)
    ap.add_argument("--chunk", type=int, default=1500)
    # acceptance
    ap.add_argument("--tau", type=float, default=2.0, help="px tolerance for a hit")
    ap.add_argument("--degenerate_deg", type=float, default=15.0)
    ap.add_argument("--min_views", type=int, default=5)
    ap.add_argument("--min_ratio", type=float, default=0.6)
    ap.add_argument("--unique_window", type=int, default=6)
    ap.add_argument("--unique_margin", type=int, default=2)
    ap.add_argument("--min_tri_angle", type=float, default=2.0)
    # free-space constraint (search only in front of the existing COLMAP surface)
    ap.add_argument("--free_space", type=int, default=1, help="1: restrict the sweep to free space (A); 0: off")
    ap.add_argument("--front_ratio", type=float, default=0.9,
                    help="max sweep depth = front_ratio * background depth of the reference pixel")
    ap.add_argument("--occ_ratio", type=float, default=1.05,
                    help="a neighbour view does not vote if the sample is deeper than occ_ratio * its surface depth")
    ap.add_argument("--min_free_samples", type=int, default=8,
                    help="skip candidates with fewer allowed depth samples in front of the surface")
    ap.add_argument("--surf_tile", type=int, default=8, help="tile size (px) of the background depth map")
    ap.add_argument("--surf_radius", type=int, default=0,
                    help="tile neighbourhood radius for the depth percentile (0 = single tile; larger windows let "
                         "nearby foreground objects hide the free space in front of the background)")
    ap.add_argument("--surf_pct", type=float, default=20.0, help="depth percentile used as background depth")
    ap.add_argument("--surf_min_count", type=int, default=3, help="min COLMAP points for a tile to count as surface")
    ap.add_argument("--surf_max_spread", type=float, default=0.0,
                    help=">0: leave tiles unconstrained if p80/p20 of their depths exceeds this (mixed depths)")
    # post filtering
    ap.add_argument("--min_ref_support", type=int, default=2, help="other reference frames that must corroborate a point")
    ap.add_argument("--support_px", type=float, default=4.0, help="corroboration radius in px footprint")
    ap.add_argument("--far_px", type=float, default=8.0, help="min distance to existing COLMAP points, px footprint")
    ap.add_argument("--far_spacing", type=float, default=0.0,
                    help="min distance to existing COLMAP points, in units of their local point spacing")
    ap.add_argument("--spacing_k", type=int, default=6, help="k for the local COLMAP spacing estimate")
    ap.add_argument("--voxel", type=float, default=0.01)
    ap.add_argument("--max_line_samples", type=int, default=3000)
    ap.add_argument("--blob", type=int, default=1, help="use blob candidates (1/0)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--reuse_raw", action="store_true", help="skip the sweep and re-run only post filtering")
    ap.add_argument("--install", action="store_true",
                    help="also write merged cloud to sparse/0/points3D.ply (old one backed up)")
    args = ap.parse_args()

    out = args.out or os.path.join(args.scene, "thin_init")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    scene = common.load_scene(args.scene, args.images)
    K, W, H, views = scene["K"], scene["W"], scene["H"], scene["views"]
    ids = common.parse_frames(args.frames, len(views))
    print(f"scene: {len(views)} views ({W}x{H}), {len(scene['xyz'])} COLMAP points, using {len(ids)} frames")

    feats = load_or_detect(scene, views, ids, os.path.join(out, "cache"), {}, args.max_line_samples, args.seed)
    if not args.blob:
        for i in ids:
            feats[i]["blob_xy"] = feats[i]["blob_xy"][:0]
    feats["views"] = views
    print(f"detection done ({time.time() - t0:.0f}s)")

    raw_path = os.path.join(out, "raw_points.npz")
    if args.reuse_raw and os.path.exists(raw_path):
        R = dict(np.load(raw_path))
        print(f"reusing {raw_path}")
    else:
        meds = {}
        for i in ids:
            r = visible_depth_range(K, W, H, views[i], scene["xyz"])
            meds[i] = r[1] if r else None
        if args.free_space:
            feats["surf"] = {i: SurfaceDepth(K, W, H, views[i], scene["xyz"], tile=args.surf_tile,
                                             radius=args.surf_radius, pct=args.surf_pct,
                                             min_count=args.surf_min_count,
                                             max_spread=args.surf_max_spread) for i in ids}
        results = []
        sweep_stats = dict(cand=0, cand_free=0, samples=0)
        t1 = time.time()
        for n, i in enumerate(ids):
            if meds[i] is None:
                continue
            nbrs = choose_neighbors(views, i, ids, meds[i], args.n_nbr, args.min_base_ratio, args.max_view_angle)
            r, st = process_reference(scene, i, nbrs, feats, args)
            if st is not None:
                for k in sweep_stats:
                    sweep_stats[k] += st[k]
            if r is not None:
                results.append(r)
            if (n + 1) % 10 == 0 or n + 1 == len(ids):
                tot = sum(len(x["xyz"]) for x in results)
                print(f"  sweep {n + 1}/{len(ids)}  raw points {tot}  ({time.time() - t1:.0f}s)")
        print(f"  candidates {sweep_stats['cand']}, with free space {sweep_stats['cand_free']}, "
              f"depth samples swept {sweep_stats['samples']}")
        if not results:
            print("no points accepted")
            return
        R = {k: np.concatenate([r[k] for r in results], 0) for k in results[0]}
        np.savez_compressed(raw_path, **R)
        with open(os.path.join(out, "sweep_stats.json"), "w") as fp:
            json.dump({**sweep_stats, "seconds": round(time.time() - t1, 1)}, fp, indent=2)
    n_raw = len(R["xyz"])
    f = K[0, 0]
    foot = R["depth"] / f  # world size of one pixel at the point's depth

    # 1) corroboration by other reference frames
    tree = cKDTree(R["xyz"])
    nb = tree.query_ball_point(R["xyz"], r=args.support_px * foot)
    n_other = np.array([len(set(R["ref"][j]) - {R["ref"][k]}) for k, j in enumerate(nb)])
    keep = n_other >= args.min_ref_support
    R = {k: v[keep] for k, v in R.items()}
    foot = foot[keep]
    n_corr = len(R["xyz"])

    # 2) distance to existing COLMAP points, relative to the local COLMAP sampling density:
    #    a point counts as "new" only if it is far both in pixels and in units of the local point spacing
    ctree = cKDTree(scene["xyz"])
    sp, _ = ctree.query(scene["xyz"], k=args.spacing_k + 1)
    spacing = sp[:, 1:].mean(1)
    d_nn, j_nn = ctree.query(R["xyz"], k=1)
    is_new = (d_nn > args.far_px * foot) & (d_nn > args.far_spacing * spacing[j_nn])

    rgb = sample_colors(scene, R["xyz"], R["ref"], R["px"])
    allp = dict(xyz=R["xyz"], rgb=rgb, score=R["score"].astype(np.uint8), kind=R["kind"],
                new=is_new.astype(np.uint8), ref=R["ref"].astype(np.uint16), tri=R["tri"])

    # 3) voxel downsample, write
    def dump(sel, path):
        xyz, rgb_, score, kind, new, ref = voxel_downsample(allp["xyz"][sel], args.voxel, allp["rgb"][sel],
                                                            allp["score"][sel], allp["kind"][sel],
                                                            allp["new"][sel], allp["ref"][sel])
        common.write_ply(path, xyz, rgb_, extra=dict(score=score, kind=kind, new=new, ref=ref))
        return xyz, rgb_

    thin_xyz, thin_rgb = dump(is_new, os.path.join(out, "thin_points.ply"))
    near_xyz, _ = dump(~is_new, os.path.join(out, "thin_points_near_existing.ply")) if (~is_new).any() else (np.zeros((0, 3)), None)

    merged_xyz = np.concatenate([scene["xyz"], thin_xyz], 0)
    merged_rgb = np.concatenate([scene["rgb"], thin_rgb], 0)
    common.write_ply(os.path.join(out, "points3D_merged.ply"), merged_xyz, merged_rgb)

    stats = dict(frames=len(ids), raw=n_raw, corroborated=n_corr, new=int(is_new.sum()),
                 near_existing=int((~is_new).sum()), thin_after_voxel=len(thin_xyz),
                 near_after_voxel=len(near_xyz), colmap_points=len(scene["xyz"]),
                 by_kind_new=dict(line=int(((R["kind"] == 0) & is_new).sum()),
                                  blob=int(((R["kind"] == 1) & is_new).sum())),
                 seconds=round(time.time() - t0, 1), args=vars(args))
    with open(os.path.join(out, "stats.json"), "w") as fp:
        json.dump(stats, fp, indent=2)
    print(json.dumps({k: v for k, v in stats.items() if k != "args"}, indent=2))

    if args.install:
        dst = os.path.join(args.scene, "sparse", "0", "points3D.ply")
        if os.path.exists(dst) and not os.path.exists(dst + ".orig"):
            os.replace(dst, dst + ".orig")
        common.write_ply(dst, merged_xyz, merged_rgb)
        print(f"installed merged cloud -> {dst}")


if __name__ == "__main__":
    main()
