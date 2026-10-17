"""Thin-structure evaluation mask: schematic on Rubble frame 49 + feasibility check of masked metrics.

Mask protocol (applied to the ground-truth test image only, identical for every method):
  1. detect_2d.detect(gray) with DEFAULTS (same detector / parameters as the anchor seeding run)
  2. M_line = bright | dark ridge masks (blobs are not used)
  3. M = dilate(M_line, R_DIL px) -> evaluation band that also covers the 1-2 px border of each structure,
     so that a sub-pixel misalignment does not dominate the score

Masked metrics (per view, then averaged over the test views whose mask is non-empty):
  PSNR_M  = 10 log10(1 / MSE over pixels in M, all channels)
  SSIM_M  = mean of the SSIM map (11x11 Gaussian window, sigma 1.5) over M
  LPIPS_M = mean of the spatial LPIPS map (VGG, spatial=True) over M

Outputs (paper/figures):
  mask49_a_gt.png      test view (GT)
  mask49_b_detect.png  detected thin-structure lines
  mask49_c_mask.png    evaluation mask M (binary)
  mask49_d_region.png  pixels inside M kept, the rest dimmed
  mask49_overview.png  the four panels side by side (preview)
The feasibility check simulates a "missing thin structure" rendering by inpainting the masked pixels from
their surroundings and reports full-image vs masked metrics for it (no method renders are needed).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "..", "point_cloud_init"))
import common  # noqa: E402
import detect_2d  # noqa: E402

SCENE = r"D:/GS/Scaffold-GS/dataset/rubble200"
FRAME = 49                    # 1-based over name-sorted registered views; index 48 -> test view (llffhold 8)
LLFFHOLD = 8
R_DIL = 2                     # dilation radius (px, images_4 resolution)
FIG = os.path.join(ROOT, "figures")
LINE_COLOR = (0, 255, 255)
DIM = 0.35


def disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def thin_mask(gray):
    det = detect_2d.detect(gray)
    line = det["mask_bright"] | det["mask_dark"]
    return line, ndi.binary_dilation(line, structure=disk(R_DIL))


# --------------------------------------------------------------------------- masked metrics
def psnr_masked(a, b, m):
    mse = ((a - b) ** 2)[m].mean()
    return 10 * np.log10(1.0 / max(mse, 1e-12))


def ssim_map(a, b):
    """a, b: HxWx3 float in [0,1]; standard SSIM (Gaussian 11x11, sigma 1.5), averaged over channels."""
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    out = []
    for c in range(3):
        x, y = a[..., c], b[..., c]
        f = lambda z: ndi.gaussian_filter(z, 1.5, truncate=3.5)   # 11x11 support
        mx, my = f(x), f(y)
        sxx, syy, sxy = f(x * x) - mx * mx, f(y * y) - my * my, f(x * y) - mx * my
        out.append(((2 * mx * my + C1) * (2 * sxy + C2)) / ((mx * mx + my * my + C1) * (sxx + syy + C2)))
    return np.mean(out, 0)


_lpips = None


def lpips_map(a, b):
    global _lpips
    import torch
    import lpips
    if _lpips is None:
        _lpips = lpips.LPIPS(net="vgg", spatial=True, verbose=False).eval()
    t = lambda z: torch.from_numpy(z).permute(2, 0, 1)[None].float() * 2 - 1
    with torch.no_grad():
        return _lpips(t(a), t(b))[0, 0].numpy()          # HxW (upsampled to input size)


def metrics(gt, img, m):
    s, l = ssim_map(gt, img), lpips_map(gt, img)
    full = dict(PSNR=psnr_masked(gt, img, np.ones_like(m)), SSIM=s.mean(), LPIPS=l.mean())
    mask = dict(PSNR=psnr_masked(gt, img, m), SSIM=s[m].mean(), LPIPS=l[m].mean())
    return full, mask


def remove_structure(rgb_f, m):
    """Simulated failure: replace masked pixels by a normalised blur of the unmasked surroundings."""
    w = (~m).astype(np.float32)
    out = rgb_f.copy()
    for c in range(3):
        num = ndi.gaussian_filter(rgb_f[..., c] * w, 4)
        den = ndi.gaussian_filter(w, 4) + 1e-6
        out[..., c] = np.where(m, num / den, rgb_f[..., c])
    return out


# --------------------------------------------------------------------------- figure
def label(im, text):
    im = im.copy()
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("times.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=font)
    d.rectangle((8, 8, 8 + x1 - x0 + 16, 8 + y1 - y0 + 14), fill=(255, 255, 255))
    d.text((16, 12 - y0 + 2), text, fill=(0, 0, 0), font=font)
    return im


def main():
    sc = common.load_scene(SCENE, "images_4")
    i = FRAME - 1
    v = sc["views"][i]
    split = "test" if i % LLFFHOLD == 0 else "train"
    gray, rgb = common.load_gray_rgb(os.path.join(sc["img_dir"], v.name))
    line, m = thin_mask(gray)
    H, W = m.shape
    print(f"frame {FRAME}: {v.name} ({W}x{H}), {split} view; line px {int(line.sum())} "
          f"({100 * line.mean():.2f}%), mask px {int(m.sum())} ({100 * m.mean():.2f}%)")

    a = Image.fromarray(rgb)
    vis = (rgb.astype(np.float32) * DIM).astype(np.uint8)
    vis[ndi.binary_dilation(line, iterations=1)] = LINE_COLOR
    b = Image.fromarray(vis)
    c = Image.fromarray(np.where(m, 255, 0).astype(np.uint8)).convert("RGB")
    lum = (rgb.astype(np.float32).mean(2, keepdims=True) * 0.3).repeat(3, 2)     # grey, dimmed context
    reg = lum.astype(np.uint8)
    reg[m] = rgb[m]
    d = Image.fromarray(reg)
    os.makedirs(FIG, exist_ok=True)
    for im, n in ((a, "a_gt"), (b, "b_detect"), (c, "c_mask"), (d, "d_region")):
        im.save(os.path.join(FIG, f"mask49_{n}.png"))
    gap = 12
    ov = Image.new("RGB", (4 * W + 3 * gap, H), (255, 255, 255))
    for k, (im, t) in enumerate(((a, "(a) GT"), (b, "(b) Detected lines"), (c, "(c) Mask M"), (d, "(d) Masked region"))):
        ov.paste(label(im, t), (k * (W + gap), 0))
    ov.save(os.path.join(FIG, "mask49_overview.png"))

    # feasibility: a rendering that misses the thin structures
    gt = rgb.astype(np.float32) / 255
    fake = remove_structure(gt, m)
    full, mk = metrics(gt, fake, m)
    print("simulated 'structure removed' rendering:")
    print(f"  full image : PSNR {full['PSNR']:.2f}  SSIM {full['SSIM']:.4f}  LPIPS {full['LPIPS']:.4f}")
    print(f"  in mask M  : PSNR {mk['PSNR']:.2f}  SSIM {mk['SSIM']:.4f}  LPIPS {mk['LPIPS']:.4f}")

    # mask statistics over all test views of the scene
    fr = []
    for j in range(0, len(sc["views"]), LLFFHOLD):
        g, _ = common.load_gray_rgb(os.path.join(sc["img_dir"], sc["views"][j].name))
        fr.append(thin_mask(g)[1].mean())
    fr = np.array(fr)
    print(f"test views: {len(fr)}, mask coverage mean {100 * fr.mean():.2f}% "
          f"(min {100 * fr.min():.2f}%, max {100 * fr.max():.2f}%), empty {int((fr == 0).sum())}")


if __name__ == "__main__":
    main()
