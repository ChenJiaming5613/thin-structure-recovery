"""Side-effect-free WordprocessingML builders matching the 《小型微型计算机系统》 template.

Shared by build_docx.py (md -> docx) and restructure.py (edits on 论文.docx).
Formatting: body 宋体 小5 (sz 18), headings 黑体, captions CN + EN, tables 6号 (sz 15) three-line,
equations = OMML numbered (n) at the right margin.
"""
import os
import re
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tex2omml import tex_to_omml  # noqa: E402

ROOT = os.path.dirname(HERE)
TPL = os.path.join(ROOT, "_tpl")

COL_W, PAGE_W = 4606, 9638
REF_SZ = 16                        # 8 pt, matching the compact journal reference style
REF_LINE = 220                     # 11 pt exact line spacing
SONG, HEI, KAI, FANG, TNR = "宋体", "黑体", "楷体_GB2312", "仿宋_GB2312", "Times New Roman"

# --------------------------------------------------------------------------- template pieces
_doc_xml = open(os.path.join(TPL, "word", "document.xml"), encoding="utf-8").read()
HEAD = _doc_xml[: _doc_xml.find("<w:body>") + len("<w:body>")]
SECTS = re.findall(r"<w:sectPr.*?</w:sectPr>", _doc_xml, re.S)
assert len(SECTS) == 4, len(SECTS)
SECT_FRONT_CN, SECT_CLC, SECT_FRONT_EN, SECT_BODY = SECTS
_i_intro = _doc_xml.find("\u5f15  \u8a00")
INTRO_NO = int(_doc_xml[_i_intro - 2])           # numbering of the introduction in the template (0 or 1)
OFF = INTRO_NO - 1                               # paper_zh.md numbers the introduction 1


def sect_no_titlepg(s):
    return s.replace("<w:titlePg/>", "")


def sect_single_col(s):
    return re.sub(r"<w:cols .*?</w:cols>|<w:cols[^>]*/>", '<w:cols w:space="720"/>', s, flags=re.S)


SECT_2COL = sect_no_titlepg(SECT_BODY)
SECT_1COL = sect_single_col(sect_no_titlepg(SECT_BODY))


# --------------------------------------------------------------------------- run / paragraph helpers
def rpr(ea=SONG, ascii_=TNR, sz=18, b=False, i=False, u=False, sup=False, sub=False):
    s = f'<w:rFonts w:ascii="{ascii_}" w:eastAsia="{ea}" w:hAnsi="{ascii_}" w:hint="eastAsia"/>'
    if b:
        s += "<w:b/><w:bCs/>"
    if i:
        s += "<w:i/><w:iCs/>"
    if u:
        s += '<w:u w:val="single"/>'
    s += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if sup:
        s += '<w:vertAlign w:val="superscript"/>'
    if sub:
        s += '<w:vertAlign w:val="subscript"/>'
    return f"<w:rPr>{s}</w:rPr>"


def run(text, **kw):
    if text == "":
        return ""
    return f'<w:r>{rpr(**kw)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def tab_run(**kw):
    return f"<w:r>{rpr(**kw)}<w:tab/></w:r>"


def para(content, ppr="", mark=None):
    mark = mark or {}
    return f"<w:p><w:pPr>{ppr}{rpr(**mark) if mark is not None else ''}</w:pPr>{content}</w:p>"


def ppr_body(math=False, indent=True):
    rule = "atLeast" if math else "exact"
    s = f'<w:spacing w:line="280" w:lineRule="{rule}"/>'
    if indent:
        s += '<w:ind w:firstLineChars="200" w:firstLine="360"/>'
    return s


MATH_RE = re.compile(r"(\$[^$]+\$|\*\*[^*]+\*\*|__[^_]+__|\*[^*\s][^*]*\*)")


def inline(text, ea=SONG, ascii_=TNR, sz=18, bold_ok=True, base_b=False, base_i=False, base_u=False):
    """Markdown inline -> runs + inline OMML. Returns (xml, has_math)."""
    out, has_math = [], False
    for tok in MATH_RE.split(text):
        if not tok:
            continue
        if tok.startswith("$"):
            out.append(tex_to_omml(tok[1:-1], size_half_pt=sz))
            has_math = True
        elif tok.startswith("**"):
            x, m = inline(tok[2:-2], ea, ascii_, sz, bold_ok, base_b=bold_ok or base_b,
                          base_i=base_i, base_u=base_u)
            out.append(x); has_math |= m
        elif tok.startswith("__"):
            x, m = inline(tok[2:-2], ea, ascii_, sz, bold_ok, base_b=base_b,
                          base_i=base_i, base_u=True)
            out.append(x); has_math |= m
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            x, m = inline(tok[1:-1], ea, ascii_, sz, bold_ok, base_b=base_b,
                          base_i=True, base_u=base_u)
            out.append(x); has_math |= m
        else:
            out.append(run(tok, ea=ea, ascii_=ascii_, sz=sz, b=base_b, i=base_i, u=base_u))
    return "".join(out), has_math


def renum(text):
    """Shift section references by OFF ('第 3.2 节' -> '第 2.2 节' when the template starts at 0)."""
    if OFF == 0:
        return text
    return re.sub(r"第\s*(\d+)\.(\d+)\s*节", lambda m: f"第 {int(m.group(1)) + OFF}.{m.group(2)} 节", text)


def spaced(title):
    return f"{title[0]}  {title[1]}" if len(title) == 2 else title


# --------------------------------------------------------------------------- block builders
def h1(no, title):
    t = f"{no}　{spaced(title)}" if no is not None else spaced(title)
    ppr = '<w:keepNext/><w:spacing w:before="120" w:after="60" w:line="240" w:lineRule="atLeast"/>'
    return para(run(t, ea=HEI, ascii_=TNR, sz=21, b=True), ppr, dict(ea=HEI, sz=21, b=True))


def h2(no, title):
    ppr = '<w:keepNext/><w:spacing w:before="60" w:line="280" w:lineRule="exact"/>'
    return para(run(f"{no}　{title}", ea=HEI, sz=18, b=True), ppr, dict(ea=HEI, sz=18, b=True))


def h3(title):
    ppr = '<w:keepNext/><w:spacing w:line="280" w:lineRule="exact"/>'
    x, _ = inline(title, ea=KAI, ascii_=TNR, sz=18)
    return para(x, ppr, dict(ea=KAI, sz=18))


def body(text, indent=True, shift=True):
    x, m = inline(renum(text) if shift else text)
    return para(x, ppr_body(m, indent))


def equation(tex, no, width=COL_W):
    om = tex_to_omml(tex, size_half_pt=18)
    tabs = f'<w:tabs><w:tab w:val="center" w:pos="{width // 2}"/><w:tab w:val="right" w:pos="{width}"/></w:tabs>'
    ppr = tabs + '<w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>'
    return para(tab_run() + om + tab_run() + run(f"({no})"), ppr)


def caption(cn, en, kind):
    cn_xml, m1 = inline(cn, sz=18)
    en_xml, m2 = inline(en, ea=TNR, sz=18)
    sp_cn = '<w:spacing w:before="60" w:line="280" w:lineRule="atLeast"/>' if kind == "tab" else '<w:spacing w:line="280" w:lineRule="atLeast"/>'
    sp_en = '<w:spacing w:after="120" w:line="280" w:lineRule="atLeast"/>' if kind == "fig" else '<w:spacing w:after="40" w:line="280" w:lineRule="atLeast"/>'
    keep = "<w:keepNext/>" if kind == "tab" else ""
    # the Chinese caption always stays on the same page as the English one
    return (para(cn_xml, "<w:keepNext/><w:keepLines/>" + sp_cn + '<w:jc w:val="center"/>')
            + para(en_xml, keep + "<w:keepLines/>" + sp_en + '<w:jc w:val="center"/>'))


def figure_placeholder(no, files, width, height=1700, notes=None):
    border = '<w:{0} w:val="dashed" w:sz="6" w:space="0" w:color="808080"/>'
    bd = "".join(border.format(s) for s in ("top", "left", "bottom", "right"))
    lines = [run(f"【图{no}占位】", ea=HEI, sz=18, b=True)]
    inner = [para("".join(lines), '<w:spacing w:line="280" w:lineRule="exact"/><w:jc w:val="center"/>')]
    if files:
        inner.append(para(run("源文件：" + "、".join(files), sz=15),
                          '<w:spacing w:line="240" w:lineRule="exact"/><w:jc w:val="center"/>'))
    for n in notes or []:
        inner.append(para(run(n, sz=15), '<w:spacing w:line="240" w:lineRule="exact"/><w:jc w:val="center"/>'))
    w = width - 200
    tbl = (f'<w:tbl><w:tblPr><w:tblW w:w="{w}" w:type="dxa"/><w:jc w:val="center"/>'
           f'<w:tblBorders>{bd}</w:tblBorders><w:tblLayout w:type="fixed"/>'
           f'<w:tblCellMar><w:left w:w="60" w:type="dxa"/><w:right w:w="60" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           f'<w:tblGrid><w:gridCol w:w="{w}"/></w:tblGrid>'
           f'<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="{height}" w:hRule="exact"/><w:jc w:val="center"/></w:trPr>'
           f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>{"".join(inner)}</w:tc></w:tr></w:tbl>')
    return para("", '<w:keepNext/><w:spacing w:before="60" w:line="120" w:lineRule="exact"/>') + tbl


def table(rows, width, first_col):
    """rows: list of list of md cell strings (row 0 = header). Three-line table, 6号 font."""
    n = len(rows[0])
    rest = (width - first_col) // (n - 1)
    widths = [width - rest * (n - 1)] + [rest] * (n - 1)
    thick = '<w:{0} w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
    nil = '<w:{0} w:val="nil"/>'
    tbl_bd = (thick.format("top") + nil.format("left") + thick.format("bottom") + nil.format("right")
              + nil.format("insideH") + nil.format("insideV"))
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{width}" w:type="dxa"/><w:jc w:val="center"/>'
           f'<w:tblBorders>{tbl_bd}</w:tblBorders><w:tblLayout w:type="fixed"/>'
           f'<w:tblCellMar><w:left w:w="30" w:type="dxa"/><w:right w:w="30" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"]
    for ri, row in enumerate(rows):
        tr = "<w:tr><w:trPr><w:cantSplit/>" + ("<w:tblHeader/>" if ri == 0 else "") + "</w:trPr>"
        for ci, cell in enumerate(row):
            tcbd = '<w:tcBorders><w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/></w:tcBorders>' if ri == 0 else ""
            x, _ = inline(cell.strip().replace(" ↑", "\u00a0↑").replace(" ↓", "\u00a0↓"), sz=15)
            jc = "left" if ci == 0 else "center"
            keep = "<w:keepNext/>" if ri < len(rows) - 1 else ""       # keep the whole table on one page
            p = para(x, f'{keep}<w:spacing w:line="240" w:lineRule="auto"/><w:jc w:val="{jc}"/>', dict(sz=15))
            tr += f'<w:tc><w:tcPr><w:tcW w:w="{widths[ci]}" w:type="dxa"/>{tcbd}<w:vAlign w:val="center"/></w:tcPr>{p}</w:tc>'
        out.append(tr + "</w:tr>")
    return "".join(out) + "</w:tbl>"


def table_grouped(first, groups, metrics, rows, width, first_col):
    """Three-line table with a two-row header: row 1 = group names (each spanning len(metrics) columns),
    row 2 = metric names; the first header cell spans both rows. rows: body rows (md cell strings)."""
    m = len(metrics)
    n = 1 + m * len(groups)
    rest = (width - first_col) // (n - 1)
    widths = [width - rest * (n - 1)] + [rest] * (n - 1)
    thick = '<w:{0} w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
    nil = '<w:{0} w:val="nil"/>'
    thin = '<w:{0} w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
    tbl_bd = (thick.format("top") + nil.format("left") + thick.format("bottom") + nil.format("right")
              + nil.format("insideH") + nil.format("insideV"))

    def cell(text, w, jc="center", span=1, vmerge=None, bottom=False, keep=True, gap=False, tight=False):
        sz = 14 if tight else 15
        x, _ = inline(text.strip().replace(" ↑", "\u00a0↑").replace(" ↓", "\u00a0↓"), sz=sz)
        ppr = ("<w:keepNext/>" if keep else "") + '<w:spacing w:line="240" w:lineRule="auto"/>' + f'<w:jc w:val="{jc}"/>'
        tcpr = f'<w:tcW w:w="{w}" w:type="dxa"/>'
        if span > 1:
            tcpr += f'<w:gridSpan w:val="{span}"/>'
        if vmerge:
            tcpr += f'<w:vMerge w:val="{vmerge}"/>' if vmerge == "restart" else "<w:vMerge/>"
        if bottom:
            tcpr += "<w:tcBorders>" + thin.format("bottom") + "</w:tcBorders>"
        # CT_TcPr order: tcW, gridSpan, vMerge, tcBorders, shd, noWrap, tcMar, textDirection, tcFitText, vAlign
        if tight:
            tcpr += "<w:noWrap/>"
        if gap:   # small inset so adjacent group underlines do not touch
            tcpr += '<w:tcMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar>'
        elif tight:
            tcpr += '<w:tcMar><w:left w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tcMar>'
        tcpr += '<w:vAlign w:val="center"/>'
        return f"<w:tc><w:tcPr>{tcpr}</w:tcPr>{para(x, ppr, dict(sz=sz))}</w:tc>"

    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{width}" w:type="dxa"/><w:jc w:val="center"/>'
           f'<w:tblBorders>{tbl_bd}</w:tblBorders><w:tblLayout w:type="fixed"/>'
           f'<w:tblCellMar><w:left w:w="30" w:type="dxa"/><w:right w:w="30" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"]
    hdr = '<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>'
    r1 = hdr + cell(first, widths[0], "left", vmerge="restart")
    for g in groups:
        r1 += cell(g, rest * m, span=m, bottom=True, gap=True)
    r2 = hdr + cell("", widths[0], "left", vmerge="continue", bottom=True)
    for _ in groups:
        for t in metrics:
            r2 += cell(t, rest, bottom=True, tight=True)
    out += [r1 + "</w:tr>", r2 + "</w:tr>"]
    for ri, row in enumerate(rows):
        tr = "<w:tr><w:trPr><w:cantSplit/></w:trPr>"
        for ci, c in enumerate(row):
            tr += cell(c, widths[ci], "left" if ci == 0 else "center", keep=ri < len(rows) - 1)
        out.append(tr + "</w:tr>")
    return "".join(out) + "</w:tbl>"


def note(text):
    x, _ = inline(text, sz=15)
    return para(x, '<w:spacing w:before="20" w:after="80" w:line="240" w:lineRule="auto"/>')


def reference(no, text):
    t = text.replace("–", "-").replace("—", "-")
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    m = re.match(r"(.*?\.)\s(.*)$", t)
    authors, rest = (m.group(1), m.group(2)) if m else ("", t)
    if ". In: " in rest:
        title, venue = rest.split(". In: ", 1)
        t = f"{authors} {title}[C]//{venue}"
    elif re.search(r"\.\s*arXiv:", rest):
        title, venue = re.split(r"\.\s*(?=arXiv:)", rest, maxsplit=1)
        t = f"{authors} {title}[J]. arXiv preprint {venue}"
    else:
        parts = rest.split(". ", 1)
        t = f"{authors} {parts[0]}[J]. {parts[1]}" if len(parts) == 2 else f"{authors} {rest}"
    return reference_raw(no, t)


def reference_raw(no, formatted):
    """Reference line with already-formatted text (no [J]/[C] inference).

    The body section uses a 15.6 pt document grid. References opt out of that grid and use the
    compact 8 pt / 11 pt exact setting shown in the journal sample."""
    ppr = ('<w:snapToGrid w:val="0"/>'
           f'<w:spacing w:before="0" w:after="0" w:line="{REF_LINE}" w:lineRule="exact"/>'
           '<w:ind w:left="400" w:hanging="400"/>')
    return para(run(f"[{no}] ", ea=SONG, sz=REF_SZ) + run(formatted, ea=SONG, sz=REF_SZ), ppr)


def end_section(sect):
    return f'<w:p><w:pPr><w:spacing w:line="20" w:lineRule="exact"/>{rpr(sz=2)}{sect}</w:pPr></w:p>'


def image_row(items, width=PAGE_W, label_sz=15, max_h=None, uniform=False):
    """Several independent pictures side by side (borderless 1-row table), each with its label below.
    items: list of (rid, img_w_px, img_h_px, pic_id, name, label).
    max_h: if given, all pictures share one height (<= max_h dxa) and the cell widths follow the
    individual aspect ratios, so the row never overflows the page.
    uniform: for panels that are meant to be the same size -- every cell gets the exact same width
    and every picture the exact same height, so rounding differences between the source files
    (e.g. 1193x1128 vs 1190x1128) cannot shift the last panel out of line."""
    n = len(items)
    mar = 0
    pad = 0                              # subfigures are stitched edge-to-edge
    aspects = None
    if uniform:
        cw = width // n
        widths = [cw] * n
        width = cw * n
        aspects = [sum(ih / iw for _, iw, ih, *_ in items) / n] * n
    elif max_h is None:
        cw = width // n
        widths = [width - cw * (n - 1)] + [cw] * (n - 1)
    else:
        ratio = sum(iw / ih for _, iw, ih, *_ in items)
        h = min(max_h, (width - n * pad) / ratio)
        widths = [int(h * iw / ih) + pad for _, iw, ih, *_ in items]
        width = sum(widths)
    nil = "".join(f'<w:{s} w:val="nil"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    cells = []
    for i, ((rid, iw, ih, pid, name, label), w) in enumerate(zip(items, widths)):
        cx = (w - pad) * 635                             # dxa -> EMU
        cy = int(cx * (aspects[i] if aspects else ih / iw))
        pic = image_inline(rid, cx, cy, pid, name)
        lines = label.split("\n")
        lab_runs = "".join(run(line, ea=SONG, sz=label_sz)
                           + ('<w:r><w:br/></w:r>' if j < len(lines) - 1 else "")
                           for j, line in enumerate(lines))
        lab = para(lab_runs,
                   '<w:keepNext/><w:spacing w:before="20" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/>',
                   dict(sz=label_sz))
        cells.append(f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/><w:vAlign w:val="top"/></w:tcPr>{pic}{lab}</w:tc>')
    return (f'<w:tbl><w:tblPr><w:tblW w:w="{width}" w:type="dxa"/><w:jc w:val="center"/>'
            f'<w:tblBorders>{nil}</w:tblBorders><w:tblLayout w:type="fixed"/>'
            f'<w:tblCellMar><w:left w:w="{mar}" w:type="dxa"/><w:right w:w="{mar}" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"
            f'<w:tr><w:trPr><w:cantSplit/><w:jc w:val="center"/></w:trPr>{"".join(cells)}</w:tr></w:tbl>')


def image_inline(rid, cx_emu, cy_emu, pic_id, name):
    """Inline picture paragraph (centered) referencing relationship `rid`."""
    d = (f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
         f'<wp:extent cx="{cx_emu}" cy="{cy_emu}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
         f'<wp:docPr id="{pic_id}" name="{escape(name)}"/>'
         '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
         '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
         '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
         '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
         f'<pic:nvPicPr><pic:cNvPr id="{pic_id}" name="{escape(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
         f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
         f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx_emu}" cy="{cy_emu}"/></a:xfrm>'
         '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
         '</a:graphicData></a:graphic></wp:inline></w:drawing>')
    return para(f"<w:r>{d}</w:r>",
                '<w:keepNext/><w:spacing w:before="60" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/>')
