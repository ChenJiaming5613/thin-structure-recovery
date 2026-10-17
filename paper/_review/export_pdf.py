"""Export a .docx to PDF with Word, then restore the original picture quality.

usage: python export_pdf.py <in.docx> <out.pdf> [--fast]

1. Word (COM) exports the document, optimised for print, with heading bookmarks and embedded fonts.
   This keeps the exact Word layout, text and vector graphics, but Word downsamples every raster picture to
   ~200 ppi JPEG (the docx image-quality settings are ignored by its PDF writer).
2. pdf_hq_images.py (PyMuPDF, run in the managed venv) replaces those pictures by the original, lossless
   files from the .docx package. Skipped with --fast.
"""
import os
import subprocess
import sys
import tempfile

import win32com.client

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PY = r"C:\Users\mingjiachen\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
# originals that are not in the docx media: the photo inside the framework figure (EMF), from _ov/lambda_fix.pptx
EXTRA = [os.path.join(HERE, "fig1_photo_src.png")]


def word_export(src, dst):
    w = win32com.client.DispatchEx("Word.Application")
    w.Visible = False
    w.DisplayAlerts = 0
    try:
        d = w.Documents.Open(src, ReadOnly=True)
        d.Repaginate()
        print("pages", d.ComputeStatistics(2))
        d.ExportAsFixedFormat(OutputFileName=dst, ExportFormat=17, OpenAfterExport=False,
                              OptimizeFor=0,            # wdExportOptimizeForPrint
                              Range=0, Item=0,          # whole document, content only
                              IncludeDocProps=True, KeepIRM=True,
                              CreateBookmarks=1,        # bookmarks from headings
                              DocStructureTags=True, BitmapMissingFonts=True, UseISO19005_1=False)
        d.Close(False)
    finally:
        w.Quit()


def main():
    src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    if "--fast" in sys.argv:
        word_export(src, dst)
        return
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        word_export(src, tmp)
        subprocess.run([VENV_PY, os.path.join(HERE, "pdf_hq_images.py"), src, tmp, dst] + [f for f in EXTRA if os.path.isfile(f)], check=True)
    finally:
        os.remove(tmp)


if __name__ == "__main__":
    main()
