"""Draw the same wire-region box (relative coordinates) on the four Fig.5 panels -> figures/*_box.png."""
import os

from PIL import Image, ImageDraw

FIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures")
NAMES = ["colmap_init_custom_view", "edgs_init_custom_view", "ours_init_custom_view", "ours_init_custom_view_mark"]
BOX = (0.52, 0.27, 0.90, 0.515)          # x0, y0, x1, y1 as fractions of width / height
COLOR = (255, 30, 30)


def main():
    for n in NAMES:
        im = Image.open(os.path.join(FIG, n + ".png")).convert("RGB")
        W, H = im.size
        lw = max(3, round(W / 220))
        x0, y0, x1, y1 = BOX[0] * W, BOX[1] * H, BOX[2] * W, BOX[3] * H
        ImageDraw.Draw(im).rectangle((x0, y0, x1, y1), outline=COLOR, width=lw)
        out = os.path.join(FIG, n + "_box.png")
        im.save(out)
        print("wrote", out, im.size)


if __name__ == "__main__":
    main()
