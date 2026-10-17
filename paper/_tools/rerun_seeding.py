"""Re-run anchor seeding (point_cloud_init/triangulate.py) on Rubble with exactly the arguments recorded in
<thin_init>/stats.json of the previous run. Existing outputs are copied to <thin_init>/_backup_<time>/ first.
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "point_cloud_init"))
import triangulate  # noqa: E402

THIN = r"D:/GS/Scaffold-GS/dataset/rubble200/thin_init"
OUTPUTS = ["background_fit.json", "points3D_merged.ply", "raw_points.npz", "stats.json", "sweep_stats.json",
           "thin_points.ply", "thin_points_near_existing.ply"]


def main():
    args = json.load(open(os.path.join(THIN, "stats.json"), encoding="utf-8"))["args"]
    bak = os.path.join(THIN, "_backup_" + time.strftime("%m%d_%H%M%S"))
    os.makedirs(bak)
    for f in OUTPUTS:
        if os.path.exists(os.path.join(THIN, f)):
            shutil.copy2(os.path.join(THIN, f), bak)
    print("backup ->", bak, flush=True)
    argv = ["triangulate.py"]
    for k, v in args.items():
        if v is None or v is False:
            continue
        if v is True:
            argv.append(f"--{k}")
        else:
            argv += [f"--{k}", str(v)]
    argv = [a.replace("--scene", "-s") if a == "--scene" else a for a in argv]
    print(" ".join(argv), flush=True)
    sys.argv = argv
    triangulate.main()


if __name__ == "__main__":
    main()
