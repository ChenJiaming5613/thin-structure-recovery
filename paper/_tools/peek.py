"""Text of headers/footers + docDefaults/style summary of an unpacked docx."""
import glob
import os
import re
import sys

d = sys.argv[1]
out = open(sys.argv[2], "w", encoding="utf-8")
rels = open(os.path.join(d, "word/_rels/document.xml.rels"), encoding="utf-8").read()
out.write(re.sub(r"\s+", " ", rels) + "\n\n")
for f in sorted(glob.glob(os.path.join(d, "word/header*.xml")) + glob.glob(os.path.join(d, "word/footer*.xml"))):
    x = open(f, encoding="utf-8").read()
    paras = re.findall(r"<w:p[ >].*?</w:p>", x, re.S)
    out.write(f"## {os.path.basename(f)}\n")
    for p in paras:
        t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
        instr = "".join(re.findall(r"<w:instrText[^>]*>([^<]*)</w:instrText>", p))
        out.write(f"  [{t}] {('FIELD:' + instr) if instr else ''}\n")
    if "<w:txbxContent" in x or "<v:shape" in x or "<wp:anchor" in x:
        out.write("  (contains textbox/shape)\n")
s = open(os.path.join(d, "word/styles.xml"), encoding="utf-8").read()
dd = re.search(r"<w:docDefaults>.*?</w:docDefaults>", s, re.S)
out.write("\n## docDefaults\n" + re.sub(r"\s+", " ", dd.group(0) if dd else "-") + "\n")
for st in re.findall(r"<w:style [^>]*>.*?</w:style>", s, re.S):
    sid = re.search(r'w:styleId="([^"]+)"', st).group(1)
    name = re.search(r'<w:name w:val="([^"]+)"', st)
    if sid in ("a", "a0", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "1", "2", "3") or "Normal" in st[:200]:
        out.write(f"\n-- {sid} ({name.group(1) if name else ''}): " + re.sub(r"\s+", " ", st)[:900] + "\n")
