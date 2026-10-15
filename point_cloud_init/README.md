# point_cloud_init

Training-free preprocessing that adds initial points on thin / suspended structures
(wires, light strings, crane booms, poles, branches) that COLMAP's sparse reconstruction misses.
The output is a drop-in replacement for `sparse/0/points3D.ply` used by Scaffold-GS / 3DGS.

Camera poses and intrinsics are taken from the existing COLMAP model; nothing is re-estimated.

## Requirements

Python 3.8+, CPU only.

```bash
pip install -r requirements.txt
# optional, for the dense monocular background (--bg fill, default; falls back to --bg colmap without it)
pip install torch transformers
```

The monocular model weights (~100 MB) are downloaded from the HuggingFace hub on first use.

## Input

A COLMAP scene folder with **undistorted** images (PINHOLE / SIMPLE_PINHOLE camera):

```
<scene>/
  images/
  sparse/0/{cameras,images,points3D}.{bin|txt}
```

If the images are smaller than the resolution stored in `cameras.bin`
(e.g. the Tanks&Temples release), intrinsics are rescaled automatically.

## Usage

```bash
# 1) generate supplementary points  ->  <scene>/thin_init/
python triangulate.py -s <scene> --frames all

# re-run only the post filtering after changing thresholds (seconds)
python triangulate.py -s <scene> --frames all --reuse_raw --far_px 10

# 2) preview: reprojection overlays, WebGL viewer, CloudCompare PLY
python preview.py -s <scene> --frames 11,45 --crop 450 0 760 140

# 3) optional: install merged cloud as <scene>/sparse/0/points3D.ply (original backed up as .orig)
python triangulate.py -s <scene> --frames all --reuse_raw --install
```

Compare several output folders on one frame (counts, ROI recall, side-by-side reprojections):

```bash
python diagnose.py -s <scene> --frame 11 --roi 470 0 760 110 --lower 270 \
    --dirs <scene>/thin_init_old <scene>/thin_init --out cmp_11
```

Set difference against a baseline folder (removed / added points, classified by depth relative to
the COLMAP background; draws removed=blue, added=red):

```bash
python compare_sets.py -s <scene> --base <scene>/thin_init_old --cands <scene>/thin_init \
    --frames 11 20 --out cmp
```

Export the cached monocular depth as PNG (`disp` = raw relative disparity, `depth` = aligned to the
COLMAP scale, `bg` = background depth actually used by the sweep; `--raw16` adds uint16 depth*1000):

```bash
python depth_to_png.py --thin_dir <scene>/thin_init --kind depth --frames 40-60 --raw16
python depth_to_png.py --thin_dir <scene>/thin_init -s <scene> --images images_4 --kind bg --with_rgb
```

Standalone 2D detection on a single image:

```bash
python detect_2d.py --image <img> --out <dir> [--crop x0 y0 x1 y1]
```

## Outputs (`<scene>/thin_init/`)

| file | content |
|---|---|
| `thin_points.ply` | supplementary points only (fields: `score`, `kind` 0=line 1=blob, `new`, `ref`) |
| `thin_points_near_existing.ply` | candidates rejected for being close to existing COLMAP points |
| `points3D_merged.ply` | original COLMAP points + supplementary points (Scaffold-GS PLY layout) |
| `raw_points.npz`, `cache/` | sweep results / per-frame 2D features, reused across runs |
| `preview/compare_colored.ply` | original = grey, supplementary = red, scalar field `is_thin` |
| `preview/preview.html` | standalone interactive viewer |
| `preview/reproj_*.png` | supplementary points reprojected onto frames |

## Method (summary)

1. **2D candidates** per frame: multi-scale Hessian ridge filter (bright and dark lines) with
   orientation-coherent line integration, hysteresis and shape filtering; Hessian blob detector
   for small bright dots.
2. **Depth sweep** along the ray of each candidate pixel (inverse-depth sampling) with fixed COLMAP
   poses; a neighbour view votes if the projection lands within `tau` px of a candidate of the same
   kind (distance-transform lookup). For lines, views whose epipolar direction is nearly parallel to
   the local 2D line are treated as degenerate and ignored.
   **Free-space constraint**: a coarse background depth map is built per frame from the COLMAP
   points (8 px tiles, 20th depth percentile, +inf where there are no points); a neighbour view does
   not vote for samples behind its own background (`occ_ratio`).
   * `--free_space 2` (default, *reject*): full sweep; a point is dropped if its best depth is not in
     front of the background (`> front_ratio` = 0.9 x background depth), so only suspended points survive.
   * `--free_space 1` (*truncate*): the sweep stops at `front_ratio` x background depth. Removes
     on-surface points too, but surface edges can then settle on a wrong depth in front of the
     surface and become floaters; kept for comparison.
   * `--free_space 0`: unconstrained sweep (original behaviour).

   **Dense background** (`--bg fill`, default): COLMAP has no points on textureless surfaces
   (walls, door frames), so the background there is unknown and the constraint is inactive. With
   `--bg fill` a monocular depth map (Depth Anything V2 Small, CPU ~0.75 s/frame) is aligned per frame
   to the visible COLMAP points (robust fit of `1/z = a*disp + b`, frames with median error above
   `--mono_max_err` fall back to COLMAP only), max-filtered by `--bg_dilate` px so that poles and trunks
   take the depth behind them, and used wherever the COLMAP tile map is empty. Fits are written to
   `background_fit.json`, predictions are cached in `cache_mono/`. `--bg colmap` disables it; if
   torch/transformers are missing it falls back automatically.
3. **Acceptance**: minimum supporting views, support ratio, unique peak along the ray, minimum
   triangulation angle; local depth refinement.
4. **Post filtering**: corroboration by other reference frames, removal of points close to the
   existing COLMAP cloud, voxel down-sampling.

## License

`third_party/colmap_loader.py` is copied unmodified from
[gaussian-splatting](https://github.com/graphdeco-inria/gaussian-splatting) (via Scaffold-GS) and is
distributed under the Gaussian-Splatting License (non-commercial, research and evaluation use only),
a full copy of which is included in `third_party/LICENSE_gaussian-splatting.md`.
That license applies to that file only.
