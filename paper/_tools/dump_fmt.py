"""Dump compact pPr / rPr per paragraph of an unpacked docx document.xml."""
import re
import sys

x = open(sys.argv[1], encoding="utf-8").read()
out = open(sys.argv[2], "w", encoding="utf-8")
idx = [int(i) for i in sys.argv[3].split(",")] if len(sys.argv) > 3 else None
body = x[x.find("<w:body>"):]
paras = re.findall(r"<w:p[ >].*?</w:p>", body, re.S)
squash = lambda s: re.sub(r"\s+", " ", s)
for i, p in enumerate(paras):
    if idx and i not in idx:
        continue
    ppr = re.search(r"<w:pPr>.*?</w:pPr>", p, re.S)
    out.write(f"===== {i}\n")
    out.write("pPr: " + squash(ppr.group(0) if ppr else "-") + "\n")
    for r in re.findall(r"<w:r[ >].*?</w:r>", p, re.S):
        rpr = re.search(r"<w:rPr>.*?</w:rPr>", r, re.S)
        t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", r))
        out.write("  r: " + squash(rpr.group(0) if rpr else "-") + " || " + t[:60] + "\n")
