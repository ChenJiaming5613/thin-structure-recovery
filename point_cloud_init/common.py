import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from third_party import colmap_loader as cl  # noqa: E402  (bundled copy, see third_party/LICENSE_gaussian-splatting.md)


class View:
    __slots__ = ("idx", "name", "R", "t", "C", "fwd", "up")

    def __init__(self, idx, name, R, t):
        self.idx, self.name, self.R, self.t = idx, name, R, t
        self.C = -R.T @ t
        self.fwd = R.T @ np.array([0.0, 0.0, 1.0])
        self.up = -(R.T @ np.array([0.0, 1.0, 0.0]))


def load_scene(scene, images_dir="images"):
    sp = os.path.join(scene, "sparse", "0")
    try:
        cams = cl.read_intrinsics_binary(os.path.join(sp, "cameras.bin"))
        imgs = cl.read_extrinsics_binary(os.path.join(sp, "images.bin"))
    except Exception:
        cams = cl.read_intrinsics_text(os.path.join(sp, "cameras.txt"))
        imgs = cl.read_extrinsics_text(os.path.join(sp, "images.txt"))
    try:
        xyz, rgb, _ = cl.read_points3D_binary(os.path.join(sp, "points3D.bin"))
    except Exception:
        xyz, rgb, _ = cl.read_points3D_text(os.path.join(sp, "points3D.txt"))

    if len(cams) != 1:
        raise NotImplementedError("only a single shared camera is supported for now")
    cam = next(iter(cams.values()))
    if cam.model == "PINHOLE":
        fx, fy, cx, cy = cam.params
    elif cam.model in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL"):
        fx = fy = cam.params[0]
        cx, cy = cam.params[1], cam.params[2]
    else:
        raise NotImplementedError(f"camera model {cam.model} (undistort first)")

    img_dir = os.path.join(scene, images_dir)
    views = []
    for k, im in enumerate(sorted(imgs.values(), key=lambda v: v.name)):
        views.append(View(k, os.path.basename(im.name), cl.qvec2rotmat(im.qvec), np.asarray(im.tvec, np.float64)))

    W, H = Image.open(os.path.join(img_dir, views[0].name)).size
    sx, sy = W / cam.width, H / cam.height
    K = np.array([[fx * sx, 0, cx * sx], [0, fy * sy, cy * sy], [0, 0, 1]], np.float64)
    return dict(K=K, W=W, H=H, views=views, xyz=xyz.astype(np.float64), rgb=rgb.astype(np.uint8), img_dir=img_dir)


def load_gray_rgb(path):
    rgb = np.asarray(Image.open(path).convert("RGB"))
    return rgb.astype(np.float32).mean(2) / 255.0, rgb


def project(K, R, t, X):
    Xc = X @ R.T + t
    z = Xc[..., 2]
    u = K[0, 0] * Xc[..., 0] / z + K[0, 2]
    v = K[1, 1] * Xc[..., 1] / z + K[1, 2]
    return u, v, z


def write_ply(path, xyz, rgb, extra=None):
    """Binary PLY with the exact vertex layout Scaffold-GS' storePly/fetchPly use
    (x y z nx ny nz red green blue), plus optional extra float/uint8 fields."""
    n = len(xyz)
    fields = [("x", "f4"), ("y", "f4"), ("z", "f4"), ("nx", "f4"), ("ny", "f4"), ("nz", "f4"),
              ("red", "u1"), ("green", "u1"), ("blue", "u1")]
    extra = extra or {}
    for k, v in extra.items():
        fields.append((k, np.asarray(v).dtype.str[1:]))
    arr = np.zeros(n, dtype=fields)
    arr["x"], arr["y"], arr["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    arr["red"], arr["green"], arr["blue"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    for k, v in extra.items():
        arr[k] = v
    ply_t = {"f4": "float", "u1": "uchar", "i4": "int", "u2": "ushort", "i2": "short", "f8": "double", "u4": "uint"}
    header = ["ply", "format binary_little_endian 1.0", f"element vertex {n}"]
    header += [f"property {ply_t[t]} {name}" for name, t in fields]
    header += ["end_header"]
    with open(path, "wb") as f:
        f.write(("\n".join(header) + "\n").encode("ascii"))
        f.write(arr.tobytes())


def read_ply(path):
    with open(path, "rb") as f:
        n, props = 0, []
        while True:
            line = f.readline().decode("ascii").strip()
            if line.startswith("element vertex"):
                n = int(line.split()[-1])
            elif line.startswith("property"):
                _, t, name = line.split()
                props.append((name, {"float": "<f4", "uchar": "u1", "int": "<i4", "double": "<f8",
                                     "ushort": "<u2", "short": "<i2", "uint": "<u4"}[t]))
            elif line == "end_header":
                break
        arr = np.frombuffer(f.read(n * np.dtype(props).itemsize), dtype=props, count=n)
    return arr


def parse_frames(spec, n):
    """'all' or '1-30,240-251' (1-based, inclusive, over the name-sorted image list)."""
    if spec in (None, "", "all"):
        return list(range(n))
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a) - 1, min(int(b), n)))
        else:
            out.append(int(part) - 1)
    return sorted(set(i for i in out if 0 <= i < n))
