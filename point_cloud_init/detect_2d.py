"""Thin-structure 2D candidate detection (ridges = thin lines, blobs = small bright dots).

Usable as a module (`detect(gray, **cfg)`) or as a CLI that writes visualisations.
"""
import argparse
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.signal import oaconvolve


DEFAULTS = dict(
    sigmas=(0.8, 1.2, 1.8),
    blob_sigmas=(1.2, 1.8, 2.5),
    hi_pct=99.0,
    lo_pct=96.5,
    blob_pct=99.8,
    min_len=25.0,
    min_elong=4.0,
    line_len=21,
    support_pct=85.0,
    edge_suppress=0,
    local_norm=0.0,
    max_halfwidth=0.0,
)


def hessian_eigs(img, sigma):
    hxx = ndi.gaussian_filter(img, sigma, order=(0, 2)) * sigma ** 2
    hyy = ndi.gaussian_filter(img, sigma, order=(2, 0)) * sigma ** 2
    hxy = ndi.gaussian_filter(img, sigma, order=(1, 1)) * sigma ** 2
    tmp = np.sqrt((hxx - hyy) ** 2 + 4 * hxy ** 2)
    l1 = 0.5 * (hxx + hyy + tmp)
    l2 = 0.5 * (hxx + hyy - tmp)
    swap = np.abs(l1) > np.abs(l2)
    la = np.where(swap, l2, l1)  # small |lambda|, along the line
    lb = np.where(swap, l1, l2)  # large |lambda|, across the line
    # angle (image x-y coords) of the eigenvector of l1 (algebraically larger eigenvalue)
    theta = 0.5 * np.arctan2(2 * hxy, hxx - hyy)
    return la, lb, theta


def ridge_response(img, sigmas, beta=0.5):
    """Bright/dark ridge strength and the line tangent angle for each."""
    bright = np.zeros_like(img)
    dark = np.zeros_like(img)
    tan_b = np.zeros_like(img)
    tan_d = np.zeros_like(img)
    for s in sigmas:
        la, lb, th = hessian_eigs(img, s)
        aniso = np.exp(-(la / (lb + 1e-12)) ** 2 / (2 * beta ** 2))
        rb = np.where(lb < 0, -lb * aniso, 0)
        rd = np.where(lb > 0, lb * aniso, 0)
        # bright line: across = eigvec(l2) = th+90deg -> tangent = th
        # dark line:   across = eigvec(l1) = th       -> tangent = th+90deg
        tan_b = np.where(rb > bright, th, tan_b)
        tan_d = np.where(rd > dark, th + np.pi / 2, tan_d)
        bright = np.maximum(bright, rb)
        dark = np.maximum(dark, rd)
    return bright, dark, tan_b, tan_d


def line_kernel(length, angle, width=0.7):
    r = length // 2
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
    c, s = np.cos(angle), np.sin(angle)
    along = xx * c + yy * s
    across = -xx * s + yy * c
    k = np.exp(-across ** 2 / (2 * width ** 2)) * (np.abs(along) <= r)
    return (k / k.sum()).astype(np.float32)


def coherence_enhance(resp, tangent, length=21, n_orient=16, tol_deg=12):
    """Average ridge response along straight segments, counting only pixels
    whose local ridge tangent agrees with the segment direction."""
    out = np.zeros_like(resp)
    for i in range(n_orient):
        a = np.pi * i / n_orient
        d = np.abs(np.angle(np.exp(2j * (tangent - a)))) / 2
        agree = (resp * (d < np.radians(tol_deg))).astype(np.float32)
        out = np.maximum(out, oaconvolve(agree, line_kernel(length, a), mode="same"))
    return out


def blob_response(img, sigmas):
    resp = np.zeros_like(img)
    for s in sigmas:
        la, lb, _ = hessian_eigs(img, s)
        both_neg = (la < 0) & (lb < 0)
        r = np.sqrt(np.where(both_neg, la * lb, 0))
        resp = np.maximum(resp, r)
    return resp


def hysteresis(resp, lo, hi):
    strong = resp > hi
    weak = resp > lo
    lab, n = ndi.label(weak, structure=np.ones((3, 3)))
    keep = np.zeros(n + 1, bool)
    keep[np.unique(lab[strong])] = True
    keep[0] = False
    return keep[lab]


def filter_components(mask, min_len, min_elong, max_halfwidth=0.0):
    """Keep long, elongated components. max_halfwidth > 0 also keeps long components that are not
    elongated as a whole but are thin everywhere (max half-width <= max_halfwidth px), e.g. several
    wires crossing each other, which the elongation test (PCA of the whole component) rejects."""
    lab, n = ndi.label(mask, structure=np.ones((3, 3)))
    out = np.zeros_like(mask)
    if n == 0:
        return out
    idx = ndi.find_objects(lab)
    for k, sl in enumerate(idx, start=1):
        if sl is None:
            continue
        sub = lab[sl] == k
        ys, xs = np.nonzero(sub)
        if len(ys) < 5:
            continue
        pts = np.stack([xs, ys], 1).astype(np.float64)
        pts -= pts.mean(0)
        ev = np.linalg.eigvalsh(np.cov(pts.T) + 1e-6 * np.eye(2))
        length = 4 * np.sqrt(ev[1])
        elong = np.sqrt(ev[1] / ev[0])
        keep = length >= min_len and elong >= min_elong
        if not keep and max_halfwidth > 0 and length >= min_len:
            keep = ndi.distance_transform_edt(np.pad(sub, 1)).max() <= max_halfwidth
        if keep:
            out[sl][sub] = True
    return out


def detect_blobs(resp, thr, min_dist, max_size):
    peaks = (resp == ndi.maximum_filter(resp, size=2 * min_dist + 1)) & (resp > thr)
    ys, xs = np.nonzero(peaks)
    if max_size > 0:
        big = ndi.binary_opening(resp > thr, iterations=max_size)
        sel = ~big[ys, xs]
        ys, xs = ys[sel], xs[sel]
    return xs, ys


def detect(gray, **cfg):
    """gray: HxW float32 in [0,1].
    Returns dict with bright/dark line masks, their tangent maps, blob coords and raw responses."""
    c = dict(DEFAULTS)
    c.update({k: v for k, v in cfg.items() if v is not None})

    rb, rd, tb, td = ridge_response(gray, c["sigmas"])
    blob = blob_response(gray, c["blob_sigmas"])

    if c["edge_suppress"] > 0:
        # a step edge yields a bright ridge and a dark ridge side by side; a true thin line yields only one
        k = int(c["edge_suppress"])
        rb_n, rd_n = ndi.maximum_filter(rb, size=k), ndi.maximum_filter(rd, size=k)
        rb, rd = np.clip(rb - rd_n, 0, None), np.clip(rd - rb_n, 0, None)

    if c["local_norm"] > 0:
        def bg(r):
            return ndi.gaussian_filter(r, c["local_norm"]) + np.percentile(r, 90) * 0.5 + 1e-6
        rb, rd = rb / bg(rb), rd / bg(rd)

    masks, coh = [], []
    for r, t in ((rb, tb), (rd, td)):
        e = coherence_enhance(r, t, length=int(c["line_len"]))
        e = e * (r > np.percentile(r, c["support_pct"]))
        coh.append(e)
        hi, lo = np.percentile(e, c["hi_pct"]), np.percentile(e, c["lo_pct"])
        m = hysteresis(e, lo, hi)
        masks.append(filter_components(m, c["min_len"], c["min_elong"], c["max_halfwidth"]))

    bxs, bys = detect_blobs(blob, np.percentile(blob, c["blob_pct"]), min_dist=3, max_size=3)
    return dict(
        mask_bright=masks[0], mask_dark=masks[1],
        tan_bright=tb, tan_dark=td,
        resp_bright=coh[0], resp_dark=coh[1], resp_blob=blob,
        blob_xy=np.stack([bxs, bys], 1).astype(np.float32),
    )


def overlay(rgb, ridge_b, ridge_d, bxs, bys, dim=0.45):
    vis = (rgb.astype(np.float32) * dim).astype(np.uint8)
    vis[ridge_d] = (0, 255, 255)
    vis[ridge_b] = (255, 60, 60)
    h, w = ridge_b.shape
    for x, y in zip(bxs, bys):
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if abs(dx) == 2 or abs(dy) == 2:
                    xx, yy = int(x) + dx, int(y) + dy
                    if 0 <= xx < w and 0 <= yy < h:
                        vis[yy, xx] = (255, 255, 0)
    return vis


def to_u8(x, p=99.5):
    v = np.percentile(x, p) + 1e-12
    return (np.clip(x / v, 0, 1) * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sigmas", type=float, nargs="+")
    ap.add_argument("--blob_sigmas", type=float, nargs="+")
    ap.add_argument("--hi_pct", type=float)
    ap.add_argument("--lo_pct", type=float)
    ap.add_argument("--blob_pct", type=float)
    ap.add_argument("--min_len", type=float)
    ap.add_argument("--min_elong", type=float)
    ap.add_argument("--line_len", type=int, help="length of oriented line integration (px)")
    ap.add_argument("--support_pct", type=float, help="raw ridge percentile a pixel must exceed")
    ap.add_argument("--edge_suppress", type=int, help="window (px) for bright/dark pair suppression; 0=off")
    ap.add_argument("--local_norm", type=float, help="sigma (px) of local contrast normalisation; 0=off")
    ap.add_argument("--max_halfwidth", type=float, help="keep non-elongated but thin components (crossing wires); 0=off")
    ap.add_argument("--crop", type=int, nargs=4, default=None, help="x0 y0 x1 y1 for zoomed view")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    name = os.path.splitext(os.path.basename(args.image))[0]
    rgb = np.asarray(Image.open(args.image).convert("RGB"))
    gray = rgb.astype(np.float32).mean(2) / 255.0

    cfg = {k: getattr(args, k) for k in DEFAULTS}
    det = detect(gray, **cfg)
    mb, md, bxy = det["mask_bright"], det["mask_dark"], det["blob_xy"]

    vis = overlay(rgb, mb, md, bxy[:, 0], bxy[:, 1])
    Image.fromarray(vis).save(os.path.join(args.out, f"{name}_detect.png"))
    resp = np.stack([to_u8(det["resp_bright"]), to_u8(det["resp_blob"]), to_u8(det["resp_dark"])], 2)
    Image.fromarray(resp).save(os.path.join(args.out, f"{name}_response.png"))

    if args.crop:
        x0, y0, x1, y1 = args.crop
        sc = max(1, 1300 // (x1 - x0))
        crops = [rgb[y0:y1, x0:x1], vis[y0:y1, x0:x1], resp[y0:y1, x0:x1]]
        crops = [np.asarray(Image.fromarray(c).resize(((x1 - x0) * sc, (y1 - y0) * sc), Image.NEAREST)) for c in crops]
        Image.fromarray(np.concatenate(crops, 0)).save(os.path.join(args.out, f"{name}_crop.png"))

    print(f"bright ridge px: {mb.sum()}, dark ridge px: {md.sum()}, blobs: {len(bxy)}")


if __name__ == "__main__":
    main()
