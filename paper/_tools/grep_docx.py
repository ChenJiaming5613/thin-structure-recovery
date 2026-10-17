"""List body blocks of a docx whose text contains any of the given keywords.
  python grep_docx.py 论文.docx kw1 kw2 ...
"""
import html
import re
import sys
import zipfile

TOKEN = re.compile(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>", re.S)


def main():
    path, kws = sys.argv[1], sys.argv[2:]
    x = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    for k, m in enumerate(TOKEN.finditer(x)):
        b = m.group(0)
        t = html.unescape("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", b)))
        hit = [w for w in kws if w in t]
        if hit:
            print(k, "TBL" if b.startswith("<w:tbl") else "P", hit, "|", t[:120])


if __name__ == "__main__":
    main()
