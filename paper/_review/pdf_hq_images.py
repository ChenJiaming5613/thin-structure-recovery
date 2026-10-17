"""Put the original pictures back into a PDF exported by Word.

Word's PDF export downsamples every raster picture to ~200 ppi and re-encodes it as JPEG, regardless of the
document's image-quality settings. This script keeps Word's layout (text, vector graphics, positions) and
replaces each downsampled picture stream by the original file from the .docx package (lossless, full
resolution). Pictures are matched to media files by aspect ratio and content similarity; a picture without a
confident match is left untouched and reported.

usage: python pdf_hq_images.py <in.docx> <word.pdf> <out.pdf> [extra.png ...]
extra.png: further originals that are not in the docx media (e.g. a photo embedded in the EMF framework figure)
(needs PyMuPDF and Pillow)
"""
import io
import sys
import zipfile

import numpy as np
import pymupdf
from PIL import Image

MIN_SIDE = 64           # ignore icons (inline bitmaps of the EMF framework figure)
MAX_ASPECT_ERR = 0.05
MAX_DIFF = 0.06         # mean abs difference of 64x64 grey thumbnails, [0,1]


def thumb(im):
    g = im.convert("RGBA")
    bg = Image.new("RGBA", g.size, (255, 255, 255, 255))
    g = Image.alpha_composite(bg, g).convert("L").resize((64, 64), Image.BILINEAR)
    return np.asarray(g, np.float32) / 255


def png_flate(data):
    """Original picture -> (zlib data with PNG row filters, width, height). The PDF FlateDecode filter with
    /Predictor 15 reads the PNG IDAT stream directly, so the pixels stay lossless at PNG-like size.
    Transparency is flattened onto white (the page background)."""
    im = Image.open(io.BytesIO(data))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    b = buf.getvalue()
    pos, idat = 8, []
    while pos < len(b):
        n = int.from_bytes(b[pos:pos + 4], "big")
        typ = b[pos + 4:pos + 8]
        if typ == b"IDAT":
            idat.append(b[pos + 8:pos + 8 + n])
        pos += 12 + n
    return b"".join(idat), im.size


def put_image(doc, xref, data):
    raw, (w, h) = png_flate(data)
    doc.update_object(xref, f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
                            f"/BitsPerComponent 8 /Filter /FlateDecode "
                            f"/DecodeParms << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns {w} >> >>")
    doc.update_stream(xref, raw, compress=False)
    # update_stream drops DecodeParms: set the filter keys again after writing the stream
    doc.xref_set_key(xref, "Filter", "/FlateDecode")
    doc.xref_set_key(xref, "DecodeParms", f"<</Predictor 15/Colors 3/BitsPerComponent 8/Columns {w}>>")


def main():
    docx, src_pdf, dst_pdf = sys.argv[1:4]
    z = zipfile.ZipFile(docx)
    media = {}
    for f in sys.argv[4:]:
        data = open(f, "rb").read()
        im = Image.open(io.BytesIO(data))
        media[f] = (data, im.size, thumb(im))
    for n in z.namelist():
        if n.startswith("word/media/") and n.lower().endswith((".png", ".jpg", ".jpeg")):
            data = z.read(n)
            im = Image.open(io.BytesIO(data))
            media[n.split("/")[-1]] = (data, im.size, thumb(im))

    doc = pymupdf.open(src_pdf)
    done, skipped = {}, []
    for pno, page in enumerate(doc):
        for info in page.get_images(full=True):
            xref, smask, w, h = info[0], info[1], info[2], info[3]
            if xref in done or min(w, h) < MIN_SIDE:
                continue
            pix = pymupdf.Pixmap(doc, xref)          # colour part only; the soft mask is not needed for matching
            if pix.alpha:
                pix = pymupdf.Pixmap(pix, 0)
            if pix.colorspace and pix.colorspace.n != 3:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            cur = Image.open(io.BytesIO(pix.tobytes("png")))
            t = thumb(cur)
            best = None
            for name, (data, (mw, mh), mt) in media.items():
                if abs((mw / mh) / (w / h) - 1) > MAX_ASPECT_ERR:
                    continue
                diff = float(np.abs(mt - t).mean())
                if best is None or diff < best[1]:
                    best = (name, diff)
            if best is None or best[1] > MAX_DIFF:
                skipped.append((pno + 1, w, h, best))
                continue
            name = best[0]
            put_image(doc, xref, media[name][0])
            done[xref] = name
            mw, mh = media[name][1]
            print(f"p{pno + 1}: {w}x{h} -> {name} {mw}x{mh} (diff {best[1]:.3f})")
    for s in skipped:
        print("left unchanged:", s)
    doc.save(dst_pdf, garbage=4, deflate=True, use_objstms=1)
    print(f"replaced {len(done)} pictures -> {dst_pdf}")


if __name__ == "__main__":
    main()
