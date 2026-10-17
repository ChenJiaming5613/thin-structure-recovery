"""Dump every body block of a docx (index, kind, full text) to a UTF-8 text file.
  python dump_blocks.py 论文.docx out.txt
"""
import html
import re
import sys
import zipfile

TOKEN = re.compile(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>|<w:p/>|<w:sectPr.*?</w:sectPr>", re.S)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    x = zipfile.ZipFile(src).read("word/document.xml").decode("utf-8")
    i0 = x.index("<w:body>") + len("<w:body>")
    out = []
    for k, m in enumerate(TOKEN.finditer(x[i0:])):
        b = m.group(0)
        t = html.unescape("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", b)))
        kind = "TBL" if b.startswith("<w:tbl") else ("SECT" if "<w:sectPr" in b else "P")
        if "<m:oMath" in b:
            kind += "+EQ"
        out.append(f"[{k}] {kind} | {t}")
    open(dst, "w", encoding="utf-8").write("\n".join(out))


if __name__ == "__main__":
    main()
