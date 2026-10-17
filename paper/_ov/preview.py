"""Render one slide of a pptx with an enlarged canvas so that overflowing content is visible.
usage: python preview.py <in.pptx> <slide> <out.png|out.emf> [scale]"""
import os, shutil, sys, tempfile
import win32com.client

src, idx, out = os.path.abspath(sys.argv[1]), int(sys.argv[2]), os.path.abspath(sys.argv[3])
scale = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
tmp = os.path.join(tempfile.gettempdir(), "ov_preview.pptx")
shutil.copyfile(src, tmp)
pp = win32com.client.Dispatch("PowerPoint.Application")
p = pp.Presentations.Open(tmp, False, False, False)
s = p.Slides(idx)
L = min(sh.Left for sh in s.Shapes)
T = min(sh.Top for sh in s.Shapes)
R = max(sh.Left + sh.Width for sh in s.Shapes)
B = max(sh.Top + sh.Height for sh in s.Shapes)
pad = 8
W, H = R - L + 2 * pad, B - T + 2 * pad
orig = [(sh, sh.Left, sh.Top) for sh in s.Shapes]
p.PageSetup.SlideWidth, p.PageSetup.SlideHeight = W, H   # PowerPoint re-centres content here
for sh, l0, t0 in orig:
    sh.Left, sh.Top = l0 - L + pad, t0 - T + pad
if out.lower().endswith(".emf"):                          # vector (EMF+ with EMF fallback), canvas = content bbox
    s.Export(out, "EMF")
else:
    s.Export(out, "PNG", int(W * scale), int(H * scale))
print(f"size {W:.1f} x {H:.1f} pt")
p.Close()
print(f"bbox L={L:.1f} T={T:.1f} R={R:.1f} B={B:.1f}")
