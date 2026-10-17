"""Build 论文.docx from the three-module backup: two-difficulty storyline, AS + GR + GT, compressed to <= 9 pages.

Input : 论文_三模块版.docx (backup of the three-module version, never modified)
Output: 论文.docx
Re-runnable: every run starts again from the backup. Stop using it once 论文.docx is edited by hand.

Steps
  1. unpack backup -> _work/
  2. renumber the OLD content (equations >=6 -> +3, section refs, figure 5 -> 7)
  3. anchor-based edits (replace / insert / delete); all new text comes from as_content.py in final numbering
  4. insert the PNG figures (Fig.5, Fig.6) and the new tables
  5. pack + validate -> 论文.docx, then run check_refs.py
An anchor that is missing or not unique aborts the run.
"""
import html
import os
import re
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import as_content as C  # noqa: E402
from docx_blocks import (COL_W, PAGE_W, SONG, HEI, KAI, SECT_1COL, SECT_2COL, run, para, h2, h3, body,  # noqa: E402
                         equation, caption, figure_placeholder, reference_raw, end_section, image_row, table, table_grouped,
                         image_inline, note)

ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "论文_三模块版.docx")
DST = os.environ.get("PAPER_DST") or os.path.join(ROOT, "论文.docx")   # override to build elsewhere
WORK = os.path.join(ROOT, "_work")
FIG_DIR = os.path.join(ROOT, "figures")
SKILL = r"C:\Users\mingjiachen\.codebuddy\plugins\marketplaces\codebuddy-plugins-official\plugins\docx\scripts\office"


# --------------------------------------------------------------------------- old -> new numbering
def _eq(n):
    return n + 3 if n >= 6 else n


SEC_MAP = {"2.2": "2.3", "2.3": "2.4.1", "2.4": "2.4.2"}


def renum_text(s):
    """Map numbering of the three-module version to the final version (plain or XML-escaped text)."""
    s = re.sub(r"式（\d+）(?:[—～、\-](?:式)?（\d+）)*",
               lambda m: re.sub(r"（(\d+)）", lambda k: f"（{_eq(int(k.group(1)))}）", m.group(0)), s)
    s = re.sub(r"第\s*(2\.[234])\s*节", lambda m: f"第 {SEC_MAP[m.group(1)]} 节", s)
    s = re.sub(r"(图\s*|Fig\.\s*|【图)5(?!\d)", r"\g<1>7", s)
    return s


def renum_block(b):
    b = re.sub(r"(<w:t(?: [^>]*)?>)([^<]*)(</w:t>)", lambda m: m.group(1) + renum_text(m.group(2)) + m.group(3), b)
    if "<m:oMath" in b and "<w:tab/>" in b:            # display equation: right-aligned "(n)"
        b = re.sub(r"(<w:t(?: [^>]*)?>)\((\d+)\)(</w:t>)", lambda m: f"{m.group(1)}({_eq(int(m.group(2)))}){m.group(3)}", b)
    return b


# --------------------------------------------------------------------------- document model
TOKEN = re.compile(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>|<w:p/>|<w:sectPr.*?</w:sectPr>", re.S)


def block_text(b):
    return html.unescape("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", b)))


class Doc:
    def __init__(self, xml):
        i0 = xml.index("<w:body>") + len("<w:body>")
        i1 = xml.rindex("</w:body>")
        self.head, self.tail = xml[:i0], xml[i1:]
        inner = xml[i0:i1]
        self.blocks = [m.group(0) for m in TOKEN.finditer(inner)]
        rest = TOKEN.sub("", inner).strip()
        assert rest == "", f"unparsed body content: {rest[:200]}"
        assert self.blocks[-1].startswith("<w:sectPr"), "body must end with its sectPr"

    def xml(self):
        return self.head + "\n".join(self.blocks) + self.tail

    def find(self, anchor, startswith=False, kind="p", exact=False):
        hits = []
        for k, b in enumerate(self.blocks):
            if kind == "p" and not b.startswith("<w:p"):
                continue
            if kind == "tbl" and not b.startswith("<w:tbl"):
                continue
            t = block_text(b)
            if exact:
                ok = t.strip() == anchor
            else:
                ok = t.startswith(anchor) if startswith else anchor in t
            if ok:
                hits.append(k)
        if len(hits) != 1:
            raise SystemExit(f"anchor {'^' if startswith else ''}{anchor!r} ({kind}) matched {len(hits)} blocks")
        return hits[0]

    def replace(self, k, new):
        self.blocks[k:k + 1] = split_blocks(new)

    def insert_after(self, k, new):
        self.blocks[k + 1:k + 1] = split_blocks(new)

    def insert_before(self, k, new):
        self.blocks[k:k] = split_blocks(new)

    def delete(self, k, n=1):
        for b in self.blocks[k:k + n]:
            assert "<w:sectPr" not in b, "refusing to delete a section break"
        del self.blocks[k:k + n]


def split_blocks(x):
    if isinstance(x, (list, tuple)):
        out = []
        for e in x:
            out += split_blocks(e)
        return out
    return [m.group(0) for m in TOKEN.finditer(x)]


def P(text):
    return body(text, shift=False)


# --------------------------------------------------------------------------- title-page author blocks
def _rpr(b, sup):
    """rPr of the first (non-)superscript run of block b."""
    for r in re.findall(r"<w:r>\s*(<w:rPr>.*?</w:rPr>)", b, re.S):
        if ("superscript" in r) == sup:
            return r
    raise SystemExit("run template not found")


def restyle_runs(b, segs):
    """Rebuild paragraph b with the run formats it already has. segs: list of (text, superscript?)."""
    m = re.match(r"(<w:p(?: [^>]*)?>\s*(?:<w:pPr>.*?</w:pPr>)?)", b, re.S)
    rn, rs = _rpr(b, False), (_rpr(b, True) if any(s for _, s in segs) else None)
    runs = "".join(f'<w:r>{rs if s else rn}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>' for t, s in segs if t)
    return m.group(1) + runs + "</w:p>"


def author_segs(authors):
    segs = []
    for i, (name, sup) in enumerate(authors):
        segs += [(("，" if i else "") + name, False), (sup, True)]
    return segs


def fill_authors(D, work):
    k = D.find("作者一", startswith=True)
    D.blocks[k] = restyle_runs(D.blocks[k], author_segs(C.AUTHORS_CN))
    ks = [D.find("（单位一", startswith=False), D.find("（单位二", startswith=False)]
    for k, (sup, text) in zip(ks, C.AFFIL_CN):
        D.blocks[k] = restyle_runs(D.blocks[k], [(sup, True), (text, False)])
    k = D.find("E-mail：", startswith=True)
    D.blocks[k] = restyle_runs(D.blocks[k], [("E-mail：" + C.EMAIL, False)])
    k = D.find("AUTHOR One", startswith=True)
    D.blocks[k] = restyle_runs(D.blocks[k], author_segs(C.AUTHORS_EN))
    ks = [i for i, b in enumerate(D.blocks) if "（Department, University, City Postcode, China）" in block_text(b)]
    assert len(ks) == len(C.AFFIL_EN), ks
    for k, (sup, text) in zip(ks, C.AFFIL_EN):
        D.blocks[k] = restyle_runs(D.blocks[k], [(sup, True), (text, False)])

    # first-page footers: 收稿日期 / 基金项目 / 作者简介, names in bold 黑体, the rest 6号宋体.
    # footer3 is the one shown on page 1; footer4 (first-page footer of the continuous EN front-matter
    # section) is normally hidden but still carried the template authors / fund text -> fill both identically.
    rn = '<w:rPr><w:rFonts w:hint="eastAsia"/><w:sz w:val="15"/></w:rPr>'
    rb = '<w:rPr><w:rFonts w:eastAsia="黑体" w:hint="eastAsia"/><w:b/><w:bCs/><w:sz w:val="15"/></w:rPr>'
    r = lambda t, fmt=rn: f'<w:r>{fmt}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>'
    fund = f"　基金项目：{C.FUND}资助." if C.FUND else "　"           # punctuation as in the template
    runs = r(f"收稿日期：{C.RECEIVED}") + r(f"{fund}作者简介：")
    for i, (name, mark, bio) in enumerate(C.BIOS):
        last = i == len(C.BIOS) - 1
        runs += r(name, rb) + (r(mark) if mark else "") + r("，" + bio + ("." if last else "；"))
    for fn in ("footer3.xml", "footer4.xml"):
        f = os.path.join(work, "word", fn)
        x = open(f, encoding="utf-8").read()
        m = re.search(r"<w:p [^>]*>(?:(?!</w:p>).)*?收稿日期(?:(?!</w:p>).)*</w:p>", x, re.S)
        assert m, f"footer paragraph not found in {fn}"
        p = m.group(0)
        head = re.match(r"<w:p [^>]*>\s*<w:pPr>.*?</w:pPr>", p, re.S).group(0)
        x = x.replace(p, head + runs + "</w:p>")
        assert "作者一" not in x and "基金中文完整名称" not in x, fn
        open(f, "w", encoding="utf-8").write(x)


def fix_running_headers(work):
    """Odd-page running header (header2 / header5): template author '作者一' and the old title -> first author + current
    title. The full-width spaces after '期' are dropped: the centre tab already positions the title, and the longer
    title would otherwise collide with them and push the page number to a second line."""
    old = "作者一　等：基于跨层几何一致性的高斯泼溅细结构恢复"
    new = f"{C.AUTHORS_CN[0][0]}　等：{C.TITLE_CN}"
    for fn in ("header2.xml", "header5.xml"):
        f = os.path.join(work, "word", fn)
        x = open(f, encoding="utf-8").read()
        assert x.count(old) == 1, fn
        x = x.replace(old, escape(new))
        x, n = re.subn(r"(<w:t(?: [^>]*)?>)期[\u3000 ]+(</w:t>)", r"\1期\2", x)
        assert n == 1, fn
        open(f, "w", encoding="utf-8").write(x)
    # the journal's contact address left over from the template: an external mailto relationship that no part uses
    rels_p = os.path.join(work, "word", "_rels", "document.xml.rels")
    rels = open(rels_p, encoding="utf-8").read()
    doc = open(os.path.join(work, "word", "document.xml"), encoding="utf-8").read()
    for m in re.finditer(r'<Relationship Id="(\w+)"[^>]*Target="mailto:[^"]*"[^>]*/>', rels):
        if f'"{m.group(1)}"' not in doc:
            rels = rels.replace(m.group(0), "")
    open(rels_p, "w", encoding="utf-8").write(rels)


def fix_metadata(work):
    """Template document properties: title '文章题目', template creator / company and the journal mailto in HLinks."""
    first = C.AUTHORS_CN[0][0]
    p = os.path.join(work, "docProps", "core.xml")
    x = open(p, encoding="utf-8").read()
    x = re.sub(r"<dc:title>[^<]*</dc:title>|<dc:title/>", f"<dc:title>{escape(C.TITLE_CN)}</dc:title>", x)
    x = re.sub(r"<dc:creator>[^<]*</dc:creator>", f"<dc:creator>{first}</dc:creator>", x)
    x = re.sub(r"<cp:lastModifiedBy>[^<]*</cp:lastModifiedBy>", f"<cp:lastModifiedBy>{first}</cp:lastModifiedBy>", x)
    x = re.sub(r"<cp:lastPrinted>[^<]*</cp:lastPrinted>", "", x)
    open(p, "w", encoding="utf-8").write(x)
    p = os.path.join(work, "docProps", "app.xml")
    x = open(p, encoding="utf-8").read()
    x = re.sub(r"<HLinks>.*?</HLinks>", "", x, flags=re.S)
    x = re.sub(r"<Company>[^<]*</Company>", "<Company/>", x)
    open(p, "w", encoding="utf-8").write(x)


# --------------------------------------------------------------------------- figures (PNG)
def add_image(work, png, rid):
    media = os.path.join(work, "word", "media")
    os.makedirs(media, exist_ok=True)
    name = os.path.basename(png)
    shutil.copy(png, os.path.join(media, name))
    rels_p = os.path.join(work, "word", "_rels", "document.xml.rels")
    rels = open(rels_p, encoding="utf-8").read()
    if rid not in rels:
        rels = rels.replace("</Relationships>",
                            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                            f'relationships/image" Target="media/{name}"/></Relationships>')
        open(rels_p, "w", encoding="utf-8").write(rels)
    ct_p = os.path.join(work, "[Content_Types].xml")
    ct = open(ct_p, encoding="utf-8").read()
    ext = os.path.splitext(name)[1][1:].lower()
    mime = {"png": "image/png", "emf": "image/x-emf"}[ext]
    if f'Extension="{ext}"' not in ct:
        ct = ct.replace("<Default ", f'<Default Extension="{ext}" ContentType="{mime}"/><Default ', 1)
        open(ct_p, "w", encoding="utf-8").write(ct)
    return rid


# --------------------------------------------------------------------------- main
def main():
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if not os.path.isfile(SRC):
        raise SystemExit(f"missing backup {SRC}")
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    subprocess.run([sys.executable, os.path.join(SKILL, "unpack.py"), SRC, WORK], check=True, env=env,
                   stdout=subprocess.DEVNULL)
    doc_p = os.path.join(WORK, "word", "document.xml")
    D = Doc(open(doc_p, encoding="utf-8").read())
    n_before = len(D.blocks)

    # ---- 1. renumber old content
    D.blocks = [renum_block(b) for b in D.blocks]

    # ---- 2. title + front matter (CN + EN abstract and keywords)
    k = D.find("基于跨层几何一致性的高斯泼溅细结构恢复", exact=True)
    old = block_text(D.blocks[k])
    D.blocks[k] = D.blocks[k].replace(escape(old), escape(C.TITLE_CN))
    k = D.find("Thin Structure Recovery for Gaussian Splatting via Cross-Level Geometric Consistency", exact=True)
    old = block_text(D.blocks[k])
    D.blocks[k] = D.blocks[k].replace(escape(old), escape(C.TITLE_EN))
    k = D.find("摘　要：", startswith=True)
    D.replace(k, para(run("摘", ea=HEI, ascii_=HEI, sz=18, b=True) + run("　", ea=HEI, sz=18, b=True)
                      + run("要：", ea=HEI, ascii_=HEI, sz=18, b=True) + run(C.ABSTRACT, ea=KAI, sz=18),
                      "", dict(ea=KAI, sz=18, b=True)))
    k = D.find("关键词：", startswith=True)
    D.replace(k, para(run("关键词：", ea=HEI, sz=18, b=True) + run(C.KEYWORDS, ea=SONG, sz=18), "", dict(sz=18)))
    k = D.find("Abstract:", startswith=True)
    assert C.EN_ABSTRACT_OLD in D.blocks[k]
    D.blocks[k] = D.blocks[k].replace(C.EN_ABSTRACT_OLD, escape(C.EN_ABSTRACT))
    k = D.find("Keywords:", startswith=True)
    assert C.EN_KW_OLD in D.blocks[k]
    D.blocks[k] = D.blocks[k].replace(C.EN_KW_OLD, C.EN_KW_NEW)
    fill_authors(D, WORK)
    fix_running_headers(WORK)
    fix_metadata(WORK)

    # ---- 3. introduction
    D.replace(D.find("三维高斯泼溅（3D Gaussian Splatting，3DGS）[1] 已成为", startswith=True), P(C.INTRO_P1))
    D.replace(D.find("然而，非结构化、面向致密化", startswith=True), P(C.INTRO_P2))
    D.replace(D.find("现有细节恢复方法通过图像驱动", startswith=True), P(C.INTRO_P3))
    D.replace(D.find("因此，本文通过锚点生命周期处理", startswith=True), [P(C.INTRO_P4), P(C.INTRO_P5)])
    k = D.find("1. 本文将场景级细结构组织", startswith=True)
    assert block_text(D.blocks[k + 1]).startswith("2. 本文提出一个统一") and block_text(D.blocks[k + 2]).startswith("3. 在多个")
    D.delete(k, 3)
    D.insert_before(k, [P(t) for t in C.CONTRIB])
    # figure 1 (failure examples) removed for space, together with its spacer paragraph
    k = D.find("【图1占位】", kind="tbl")
    assert block_text(D.blocks[k + 1]).startswith("图1") and block_text(D.blocks[k + 2]).startswith("Fig.1")
    assert D.blocks[k - 1].startswith("<w:p") and not block_text(D.blocks[k - 1]).strip()
    D.delete(k - 1, 4)

    # ---- 4. related work: three subsections
    k0 = D.find("1.1　精细细节与细结构恢复", startswith=True)
    k1 = D.find("对于细结构而言，锚点的价值", startswith=True)
    D.delete(k0, k1 - k0 + 1)
    new = []
    for no, title, paras in C.RW:
        new.append(h2(no, title))
        new += [P(t) for t in paras]
    D.insert_before(k0, new)

    # ---- 5. figure 2 (framework figure exported from overview.pptx slide 2) + caption
    from PIL import Image
    k = D.find("【图2占位】", kind="tbl")
    png = os.path.join(FIG_DIR, C.FIG2_FILE)
    rid = add_image(WORK, png, rid="rIdFig2")
    iw, ih = Image.open(png).size
    cx = int(PAGE_W * C.FIG2_WIDTH) * 635                 # dxa -> EMU
    D.replace(k, image_inline(rid, cx, int(cx * ih / iw), 1020, "fig2_overview"))
    assert block_text(D.blocks[k + 1]).startswith("图2") and block_text(D.blocks[k + 2]).startswith("Fig.2")
    D.delete(k + 1, 2)
    D.insert_after(k, caption(C.FIG2_CAP, C.FIG2_EN, "fig"))

    # ---- 6. method overview + preliminaries
    D.replace(D.find("本文通过 Scaffold-GS 的锚点接口处理", startswith=True), [P(t) for t in C.METHOD_OVERVIEW])
    D.delete(D.find("这里的“跨层”包含", startswith=True))
    D.delete(D.find("本文不改变 Scaffold-GS 的基本渲染表达", startswith=True))
    D.delete(D.find("Scaffold-GS", exact=True))
    D.replace(D.find("个去重后的体素中心"), P(C.PRE_P1))
    D.replace(D.find("式（2）—（4）体现了锚点表示中的两级参数关系", startswith=True), P(C.PRE_P2))
    D.replace(D.find("是独立的增长阶段体素尺度"), P(C.PRE_P3))
    D.replace(D.find("在锚点增长过程中", startswith=True), P(C.PRE_GROW))

    # Fill the second-page columns before switching to the full-width framework figure. The method
    # overview explains that figure and can precede it; keeping 2.1 after the figure preserves the
    # detailed method order while avoiding the large blank area caused by the early section break.
    fig = next(i for i, b in enumerate(D.blocks) if 'r:embed="rIdFig2"' in b)
    assert not block_text(D.blocks[fig - 1]).strip()
    assert block_text(D.blocks[fig + 1]).startswith("图2") and block_text(D.blocks[fig + 2]).startswith("Fig.2")
    overview = D.find("2　本文方法", startswith=True)
    pre = D.find("2.1　预备知识", startswith=True)
    method_overview = D.blocks[overview:pre]
    del D.blocks[overview:pre]
    fig = next(i for i, b in enumerate(D.blocks) if 'r:embed="rIdFig2"' in b)
    D.blocks[fig - 1:fig - 1] = method_overview
    D.replace(D.find("2.1　预备知识", startswith=True), h2("2.1", C.PRE_TITLE))

    # ---- 7. new section 2.2 anchor seeding (before the GR heading) + GR compression
    k = D.find("2.2　离散度引导几何细化", startswith=True)
    new = [h2("2.2", C.AS_TITLE)]
    for kind, pl in C.AS_BLOCKS:
        new.append(P(pl) if kind == "p" else h3(pl) if kind == "h3" else equation(pl[0], pl[1], COL_W))
    D.replace(k, new + [h2("2.3", C.GR_TITLE)])
    D.replace(D.find("Scaffold-GS 的致密化由位置梯度驱动", startswith=True), P(C.GR_P1))
    D.replace(D.find("本文利用两个互补的高斯级线索补充原有准则", startswith=True), P(C.GR_P2))
    D.replace(D.find("为相对尺度比例的均值"), P(C.GR_P3))
    D.delete(D.find("以组内均值为参照，对三个轴上的相对尺度偏差进行平均"))
    D.delete(D.find("组合权重", startswith=True))
    D.replace(D.find("在锚点生命周期早期", startswith=True), P(C.GR_CONF_INTRO))
    D.replace(D.find("仅在以下条件满足时启用离散度引导细化"), P(C.GR_GATE))
    D.replace(D.find("通过验证视角选择。成熟度门控抑制过早细化"), P(C.GR_P4))
    D.delete(D.find("可见次数刻画的是某个锚点实际接受优化证据的充分程度", startswith=True))

    # ---- 8. GI + GP -> 2.4 GT
    k = D.find("2.3　父锚点感知几何继承", startswith=True)
    D.replace(k, [h2("2.4", C.GT_TITLE), P(C.GT_INTRO), h3(C.GT_SUB1)])
    D.replace(D.find("细化本身并不能决定所得子锚点的几何", startswith=True), P(C.GT_P1))
    D.delete(D.find("父锚点在被选中细化之前，已经通过多个训练视角", startswith=True))
    D.replace(D.find("该规则在传递父锚点基础尺度的同时"), P(C.GT_P2))
    k = D.find("分裂与克隆对应两种不同的容量调整需求", startswith=True)
    assert block_text(D.blocks[k + 1]).startswith("逐元素最小值还保留了尺度的轴向差异")
    D.delete(k, 2)
    D.replace(D.find("2.4　置信度引导几何保持", startswith=True), h3(C.GT_SUB2))
    D.replace(D.find("传递后的出生尺度在优化早期仍可能发生漂移", startswith=True), P(C.GT_P3))
    D.delete(D.find("会影响全部"))
    D.delete(D.find("这种选择在稳定性与适应性之间形成了分层约束", startswith=True))
    D.replace(D.find("对于每个锚点", startswith=True), P(C.GP_PRIOR))
    D.replace(D.find("在出生时最大"), P(C.GP_PRESERVE))
    D.replace(D.find("成熟锚点开始具备"), P(C.GP_LOSS))
    # "birth" is uncommon in 3DGS parameter notation; use the standard initialization superscript instead.
    n_birth = sum(b.count("<m:t>birth</m:t>") for b in D.blocks)
    assert n_birth == 1
    D.blocks = [b.replace("<m:t>birth</m:t>", "<m:t>init</m:t>") for b in D.blocks]

    # ---- 9. experiments: setup, figure 3, table 1, comparison text, figure 4
    from PIL import Image

    def panels(spec, prefix, pid0):
        items = []
        for j, (fname, label) in enumerate(spec):
            png = os.path.join(FIG_DIR, fname)
            rid = add_image(WORK, png, rid=f"{prefix}{j + 1}")
            iw, ih = Image.open(png).size
            items.append((rid, iw, ih, pid0 + j, os.path.splitext(fname)[0], label))
        return items

    gap = para("", '<w:keepNext/><w:spacing w:line="60" w:lineRule="exact"/>')

    D.replace(D.find("数据集与评价方式。", startswith=True),
              [h3(pl) if kind == "h3" else P(pl) for kind, pl in C.SETUP_BLOCKS])
    D.delete(D.find("三类指标从不同角度衡量新视图质量", startswith=True))
    D.delete(D.find("基线与实现。", startswith=True))

    k = D.find("【图3占位】", kind="tbl")
    assert C.FIG3_FILES_OLD in D.blocks[k]
    D.blocks[k] = D.blocks[k].replace(C.FIG3_FILES_OLD, C.FIG3_FILES_NEW)
    assert block_text(D.blocks[k + 1]).startswith("图3") and block_text(D.blocks[k + 2]).startswith("Fig.3")
    D.delete(k + 1, 2)
    # three tall stacks of 6 rows each (method per row, dataset per column), side by side;
    # the stacks are very tall, so cap the picture height to keep figure + caption on one page
    D.replace(k, split_blocks(gap + image_row(panels(C.FIG3_PANELS, "rIdQual", 1031), PAGE_W, max_h=8700)
                              + caption(C.FIG3_CAP, C.FIG3_EN, "fig")))

    n_val = len(C.TABLE_GROUPS) * len(C.TABLE_METRICS)

    def pending(name):
        return [name] + ([f"**{C.TODO}**"] if name.startswith("**") else [C.TODO]) * n_val

    k = D.find("表1", startswith=True)
    assert block_text(D.blocks[k + 1]).startswith("Table 1") and D.blocks[k + 2].startswith("<w:tbl")
    assert block_text(D.blocks[k + 3]).startswith("注：")
    D.blocks[k:k + 4] = split_blocks([caption(C.TAB1_CAP, C.TAB1_EN, "tab"),
                                      table_grouped("方法", C.TABLE_GROUPS, C.TABLE_METRICS,
                                                    C.TAB1_ROWS, PAGE_W, 2000),
                                      note(C.TAB1_NOTE),
                                      para("", '<w:spacing w:line="120" w:lineRule="exact"/>')])

    # old table 2 (manually annotated region metrics) removed together with its full-width section
    k = D.find("表2", startswith=True)
    assert "细结构区域" in block_text(D.blocks[k])
    assert "<w:sectPr" in D.blocks[k - 1] and block_text(D.blocks[k + 1]).startswith("Table 2")
    assert D.blocks[k + 2].startswith("<w:tbl") and "<w:sectPr" in D.blocks[k + 3]
    del D.blocks[k - 1:k + 4]

    D.delete(D.find("本文通过定性比较（图 3）", startswith=True))
    D.replace(D.find("3.2　细结构恢复比较", exact=True), h2("3.2", C.CMP_TITLE))
    D.replace(D.find("定性比较。", startswith=True), [h3(C.QUAL_H), P(C.QUAL_P)])
    D.replace(D.find("整图比较。", startswith=True), [h3(C.GLOBAL_H), P(C.GLOBAL_CMP)])
    D.delete(D.find("细结构区域比较。", startswith=True))
    D.replace(D.find("与体素尺度调整的比较。", startswith=True),
              [h3(C.VOXEL_H), P(C.VOXEL_P1), P(C.VOXEL_P2), P(C.VOXEL_P3)])

    # ---- 10. new 3.3 initial point cloud comparison (after the voxel-size paragraph)

    # figure 4 (voxel size): the 4 panels are too wide for the two-column flow the placeholder sits in,
    # so the figure + caption move into the preceding full-width section, right below table 1
    k = D.find("【图4占位】", kind="tbl")
    assert block_text(D.blocks[k + 1]).startswith("图4") and block_text(D.blocks[k + 2]).startswith("Fig.4")
    assert "<w:sectPr" in D.blocks[k - 2] and not block_text(D.blocks[k - 1]).strip()
    # the four renders differ by a few pixels (1193x1128 vs 1190x1128); without uniform=True that
    # rounding shifts the last panel out of line with the other three
    fig4 = split_blocks(gap + image_row(panels(C.FIG4_PANELS, "rIdVox", 1021), PAGE_W, uniform=True)
                        + caption(C.FIG4_CAP, C.FIG4_EN, "fig"))
    del D.blocks[k:k + 3]
    D.blocks[k - 2:k - 2] = fig4

    # figure 3 (qualitative) sits in its own full-width section right after the two-column text.
    # Being almost a full page tall it cannot start on that page, so Word pushed the whole section
    # to the next page and left a large gap at the bottom of the previous one. Merge that section
    # with the one holding table 1 (the empty two-column section in between is dropped) and put the
    # table first: the table does fit into the remaining space, so the gap disappears.
    t = next(i for i, b in enumerate(D.blocks) if 'r:embed="rIdQual1"' in b)
    assert block_text(D.blocks[t + 1]).startswith("图3") and block_text(D.blocks[t + 2]).startswith("Fig.3")
    assert "<w:sectPr" in D.blocks[t + 3] and "<w:sectPr" in D.blocks[t + 4]
    assert all(not block_text(b).strip() for b in D.blocks[t - 2:t])
    fig3 = D.blocks[t - 2:t + 3]
    del D.blocks[t - 2:t + 5]
    k = D.find("表1", startswith=True)
    assert D.blocks[k + 2].startswith("<w:tbl") and block_text(D.blocks[k + 3]).startswith("注：")
    assert not block_text(D.blocks[k + 4]).strip()
    D.blocks[k + 5:k + 5] = fig3

    # Table 1 and the two full-width figures previously shared one single-column section. The tall
    # qualitative figure then moved wholesale to the next page and left the remainder of page 6
    # empty. Let 3.2.1--3.2.3 flow in two columns after the table, and switch back to one column only
    # for the figures. This fills the page without shrinking either figure.
    k = D.find("表1", startswith=True)
    sect = next(i for i in range(k + 1, len(D.blocks)) if "<w:sectPr" in D.blocks[i])
    analysis = D.find("3.2　实验结果与分析", startswith=True)
    qual = next(i for i, b in enumerate(D.blocks) if 'r:embed="rIdQual1"' in b)
    assert analysis > sect and qual < sect
    analysis_blocks = D.blocks[analysis:]
    # Move exactly 3.2--3.2.3. The sensitivity subsection already exists in the template here and
    # must remain after 3.2.4, otherwise figure 6 would precede figures 2--5.
    sens = next(i for i, b in enumerate(analysis_blocks)
                if block_text(b).startswith("3.3　超参数敏感性分析"))
    analysis_blocks = analysis_blocks[:sens]
    del D.blocks[analysis:analysis + sens]
    qual = next(i for i, b in enumerate(D.blocks) if 'r:embed="rIdQual1"' in b)
    # A sectPr describes the section that PRECEDES it: close the analysis with 2 columns, while the
    # break immediately after table 1 must close a 1-column section. Reversing these two clips the
    # full-width table to the left column (the layout defect visible in Word).
    D.blocks[qual:qual] = [end_section(SECT_2COL)]
    k = D.find("表1", startswith=True)
    D.blocks[k + 5:k + 5] = [end_section(SECT_1COL)] + analysis_blocks

    f049 = panels(C.F049_FIG_PANELS, "rIdF049", 1011)
    items = panels(C.INIT_FIG_PANELS, "rIdInitCmp", 1001)
    # 3.2.4 belongs after the qualitative/voxel figures (figures 2/3); otherwise its figures 4/5
    # would precede them after the page-filling reordering above.
    k = next(i for i, b in enumerate(D.blocks) if 'r:embed="rIdVox1"' in b)
    vox_sect = next(i for i in range(k + 1, len(D.blocks)) if "<w:sectPr" in D.blocks[i])
    new = [h3(C.INIT_TITLE), P(C.INIT_P1), P(C.INIT_P3), P(C.INIT_P4),
           end_section(SECT_2COL), gap,
           image_row(f049, PAGE_W, uniform=True),
           caption(C.F049_FIG_CAP, C.F049_FIG_EN, "fig"), gap,
           image_row(items, PAGE_W, uniform=True),
           caption(C.INIT_FIG_CAP, C.INIT_FIG_EN, "fig"), end_section(SECT_1COL)]
    D.blocks[vox_sect + 1:vox_sect + 1] = split_blocks(new)

    # ---- 11. renumbered experiment headings; sensitivity results pending
    # both the initial point clouds and the sensitivity study are folded into 3.2 (as 3.2.4/3.2.5),
    # so the ablation moves up to 3.3 and 3.2 collects every result subsection
    D.replace(D.find("3.3　超参数敏感性分析", startswith=True), h3(C.SENS_H))
    D.replace(D.find("本文在 Rubble 场景上使用 LPIPS", startswith=True), P(C.SENS_INTRO))
    D.replace(D.find("3.4　消融实验", startswith=True), h3(C.ABL_H))
    # Replace the two raw sensitivity tables plus the redundant figure placeholder by one compact
    # table with two parameter blocks. Numeric results deliberately remain blank until supplied.
    t1 = next(i for i, b in enumerate(D.blocks) if b.startswith("<w:tbl") and ">0.03<" in b)
    p = D.find("两个参数均呈 U 形趋势")
    assert t1 < p and not any("<w:sectPr" in b for b in D.blocks[t1:p + 1])
    label_a = para(run(C.SENS_SUB_A, ea=SONG, sz=15),
                   '<w:keepNext/><w:spacing w:before="40" w:after="20" w:line="240" w:lineRule="auto"/>')
    label_b = para(run(C.SENS_SUB_B, ea=SONG, sz=15),
                   '<w:keepNext/><w:spacing w:before="60" w:after="20" w:line="240" w:lineRule="auto"/>')
    D.blocks[t1:p + 1] = split_blocks([caption(C.SENS_CAP, C.SENS_EN, "tab"),
                                      label_a, table(C.SENS_TAU_ROWS, COL_W, 950),
                                      label_b, table(C.SENS_N_ROWS, COL_W, 950), note(C.SENS_NOTE),
                                      P(C.SENS_P)])
    # The template contained a second paragraph with concrete LPIPS values; remove it because all
    # sensitivity results are intentionally left blank in this revision.
    D.delete(D.find("取 0 时不提供有效", startswith=False))

    # ---- 12. ablation (now table 3)
    k = D.find("表3　GI、GP 和 GR", startswith=True)
    assert block_text(D.blocks[k + 1]).startswith("Table 3") and D.blocks[k + 2].startswith("<w:tbl")
    D.blocks[k:k + 3] = split_blocks([caption(C.ABL_CAP, C.ABL_EN, "tab"),
                                      table_grouped("变体", C.TABLE_GROUPS, C.TABLE_METRICS,
                                                    C.ABL_ROWS, PAGE_W, 2000),
                                      note(C.ABL_NOTE)])
    k = D.find("表 3 报告了从 Scaffold-GS", startswith=True)
    assert block_text(D.blocks[k + 1]).startswith("仅加入 GI 后") and block_text(D.blocks[k + 2]).startswith("在该累加顺序下")
    D.delete(k, 3)
    D.insert_before(k, [P(C.ABL_P1), P(C.ABL_P2)])

    # ---- 13. conclusion (renamed); the conflict-of-interest and data-availability statements are dropped
    k = D.find("4　结  论", startswith=True)
    D.blocks[k] = D.blocks[k].replace("结  论", "总  结")
    D.replace(D.find("本文处理了锚点式 3DGS 中的跨层几何不一致问题", startswith=True), [P(t) for t in C.CONCLUSION])
    k = D.find("利益冲突声明", exact=True)
    assert block_text(D.blocks[k + 1]).startswith("作者声明")
    assert block_text(D.blocks[k + 2]) == "数据可用性"
    assert "场景作为 Mega-NeRF" in block_text(D.blocks[k + 3])
    D.delete(k, 4)

    # ---- 14. references: the complete list is rebuilt in journal style, dropped entries removed, citations renumbered
    k = D.find("References:", startswith=True)
    old = [i for i in range(k + 1, len(D.blocks)) if re.match(r"\[\d+\] ", block_text(D.blocks[i]))]
    assert old == list(range(k + 1, k + 1 + len(old))) and len(old) == 30, old
    D.delete(k + 1, len(old))
    # numbering by order of first citation (GB/T 7714 sequential system)
    cite_re = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]")
    wt_re = re.compile(r"(<w:t(?: [^>]*)?>)([^<]*)(</w:t>)")

    def parse(s):
        nums = []
        for part in s.split(","):
            a, _, b = part.replace("-", "–").partition("–")
            nums += list(range(int(a), int(b or a) + 1))
        return nums

    order = []
    for i in range(k):
        for m in wt_re.finditer(D.blocks[i]):
            for c in cite_re.finditer(m.group(2)):
                for n in parse(c.group(1)):
                    assert n not in C.DROP_REFS, f"citation {c.group(0)} refers to dropped reference {n}"
                    if n not in order:
                        order.append(n)
    keep = [n for n in range(1, len(C.REFS) + 1) if n not in C.DROP_REFS]
    missing = sorted(set(keep) - set(order))
    assert not missing, f"references never cited: {missing}"
    new_no = {n: i for i, n in enumerate(order, start=1)}

    def recite(m):
        nums = sorted(new_no[n] for n in parse(m.group(1)))
        runs, out = [[nums[0]]], []
        for n in nums[1:]:
            if n == runs[-1][-1] + 1:
                runs[-1].append(n)
            else:
                runs.append([n])
        for r in runs:
            out.append(f"{r[0]}–{r[-1]}" if len(r) >= 3 else ",".join(map(str, r)))
        return "[" + ",".join(out) + "]"

    for i in range(k):
        D.blocks[i] = wt_re.sub(lambda m: m.group(1) + cite_re.sub(recite, m.group(2)) + m.group(3), D.blocks[i])
    D.insert_after(k, [reference_raw(new_no[n], C.REFS[n - 1]) for n in order])
    print(f"references: {len(order)} (dropped {sorted(C.DROP_REFS)}), numbered by first citation")

    # ---- 15. figure 1 was removed: shift every figure number (captions, placeholders, references) by -1
    fig_re = re.compile(r"(图\s*|Fig\.\s*|【图)(\d+)(?!\d)")
    assert not any(re.search(r"(图\s*|Fig\.\s*|【图)1(?!\d)", block_text(b)) for b in D.blocks), "figure 1 still referenced"
    D.blocks = [re.sub(r"(<w:t(?: [^>]*)?>)([^<]*)(</w:t>)",
                       lambda m: m.group(1) + fig_re.sub(lambda f: f"{f.group(1)}{int(f.group(2)) - 1}", m.group(2))
                       + m.group(3), b) for b in D.blocks]

    # ---- 16. keep every figure (placeholder / image row) on the same page as its CN + EN captions
    def keep_next(b):
        # CT_PPr order: pStyle, keepNext, ...
        # (the unpacked XML is pretty-printed, so allow whitespace between elements)
        b = re.sub(r"<w:keepNext\s*/>", "", b)
        b = re.sub(r"<w:pPr>(\s*(?:<w:pStyle [^>]*/>)?)", r"<w:pPr>\1<w:keepNext/>", b)
        return re.sub(r"<w:p>(?!\s*<w:pPr>)", "<w:p><w:pPr><w:keepNext/></w:pPr>", b)

    for i, b in enumerate(D.blocks):
        t = block_text(b)
        if (b.startswith("<w:tbl") and "占位】" in t) or (b.startswith("<w:p") and re.match(r"图\d+　", t)):
            D.blocks[i] = keep_next(b)

    open(doc_p, "w", encoding="utf-8").write(D.xml())
    print(f"blocks: {n_before} -> {len(D.blocks)}")

    r = subprocess.run([sys.executable, os.path.join(SKILL, "pack.py"), WORK, DST, "--original", SRC],
                       env=env, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip().splitlines()[-2:] if r.stdout else "", r.stderr.strip()[-800:])
    if r.returncode != 0 or "PASSED" not in r.stdout:
        raise SystemExit("pack/validate failed")
    subprocess.run([sys.executable, os.path.join(HERE, "check_refs.py"), doc_p], env=env, check=False)


if __name__ == "__main__":
    main()
