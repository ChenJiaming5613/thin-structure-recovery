"""Print paragraph-level outline of an unpacked docx (style, flags, text)."""
import re
import sys

sys.stdout = open(sys.argv[2], "w", encoding="utf-8") if len(sys.argv) > 2 else sys.stdout
src = sys.argv[1]
x = open(src, encoding="utf-8").read()
body = x[x.find("<w:body>"):]
print("tables", body.count("<w:tbl>"), "sectPr", body.count("<w:sectPr"), "drawing", body.count("<w:drawing"),
      "pict", body.count("<w:pict"), "oMath", body.count("<m:oMath"), "object", body.count("<w:object"))
tokens = re.finditer(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>|<w:sectPr.*?</w:sectPr>", body, re.S)
for i, m in enumerate(tokens):
    p = m.group(0)
    if p.startswith("<w:tbl>"):
        rows = p.count("<w:tr")
        t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
        print(i, "[TABLE rows=%d]" % rows, t[:160])
        continue
    if p.startswith("<w:sectPr"):
        print(i, "[BODY SECTPR]")
        continue
    st = re.search(r'<w:pStyle w:val="([^"]+)"', p)
    t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
    flags = ""
    if "<w:sectPr" in p:
        flags += "[SECT]"
    if "<w:drawing" in p or "<w:pict" in p:
        flags += "[IMG]"
    if "<m:oMath" in p or "<w:object" in p:
        flags += "[EQ]"
    if "<w:fldChar" in p or "<w:fldSimple" in p:
        flags += "[FLD]"
    print(i, st.group(1) if st else "-", flags, t[:150])
