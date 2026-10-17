"""Fill the journal template (unpacked in _tpl/) with paper_zh.md and write _build/ (unpacked docx).

Formatting is copied from the template example paragraphs (《小型微型计算机系统》 例文):
  title 黑体 小2 bold; authors 仿宋 小4; affiliations 宋体 6号; abstract 楷体 小5;
  level-1 heading 黑体 5号 bold; level-2 黑体 小5 bold; level-3 楷体 小5;
  body 宋体 小5, first-line indent 2 chars, 14 pt line pitch; captions CN + EN, 小5;
  tables 6号 three-line; equations = Word (OMML) equations, numbered (n) at the right margin.
Figures are placeholders. Wide figures / tables span both columns via continuous section breaks.
Template headers/footers (journal masthead, 收稿日期/基金/作者简介 footer) are kept unchanged,
except "文章题目" in the running header which is replaced by the paper title.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from docx_blocks import (COL_W, PAGE_W, SONG, HEI, KAI, FANG, TNR, HEAD, SECT_FRONT_CN, SECT_CLC,  # noqa: E402
                         SECT_FRONT_EN, SECT_BODY, INTRO_NO, OFF, TPL, sect_no_titlepg, sect_single_col,
                         rpr, run, para, h1, h2, h3, body, equation, caption, figure_placeholder, table,
                         note, reference, end_section)

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "_build")
MD = os.path.join(ROOT, "paper_zh.md")


# English captions (template requires bilingual figure / table captions)
EN_FIG = {
    1: "Fig.{n} Representative thin-structure reconstruction failures of unstructured (3DGS), "
       "densification-oriented (ResGS) and anchor-based (Scaffold-GS) variants. Yellow boxes indicate zoomed-in regions",
    2: "Fig.{n} Overview of the proposed cross-level geometric consistency framework",
    3: "Fig.{n} Qualitative comparison on Rubble, Building and UrbanAerial3D (left to right). Red boxes mark the "
       "shared thin-structure regions evaluated in Table 2; yellow insets show zoomed-in views",
    4: "Fig.{n} Scaffold-GS still fails to recover thin structures even with denser voxelization",
    5: r"Fig.{n} LPIPS sensitivity to hyperparameters on Rubble. Left: $\tau_{\text{disp}}$; right: $N_{\text{conf}}$",
}
EN_TAB = {
    1: "Table {n} Quantitative comparison on UrbanAerial3D, Rubble and Building",
    2: "Table {n} Quantitative comparison within thin-structure regions selected from ground-truth images and fixed "
       "across methods; representative regions are shown in Fig.3. Rankings are computed from unrounded values",
    3: "Table {n} Ablation of GI, GP and GR on UrbanAerial3D, Rubble and Building. GI: geometry inheritance; "
       "GP: geometry preservation; GR: geometry refinement",
}
WIDE_FIG = {2, 3}
WIDE_TAB = {1, 2, 3}


# --------------------------------------------------------------------------- parse markdown
md = open(MD, encoding="utf-8").read()
md = md.split("\n---\n")[0]                      # drop the editorial appendix
L = md.split("\n")

title = L[0].lstrip("# ").strip()
abstract, keywords = "", ""
blocks = []                                      # (kind, payload)
i, mode, pending_tab = 1, None, None
while i < len(L):
    s = L[i].rstrip()
    if not s.strip():
        i += 1
        continue
    if s.startswith("## "):
        h = s[3:].strip()
        m = re.match(r"(\d+)\s+(.*)", h)
        if h == "摘要":
            mode = "abstract"
        elif h == "参考文献":
            mode = "refs"
            blocks.append(("refs_head", None))
        elif m:
            mode = "body"
            blocks.append(("h1", (int(m.group(1)) + OFF, m.group(2))))
        else:
            mode = "body"
            blocks.append(("h1", (None, h)))
        i += 1
        continue
    if mode == "abstract":
        if s.startswith("**关键词：**"):
            keywords = s.replace("**关键词：**", "").strip()
        else:
            abstract = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        i += 1
        continue
    if mode == "refs":
        m = re.match(r"(\d+)\.\s+(.*)", s)
        if m:
            blocks.append(("ref", (int(m.group(1)), m.group(2))))
        i += 1
        continue
    if s.startswith("### "):
        m = re.match(r"(\d+)\.(\d+)\s+(.*)", s[4:].strip())
        blocks.append(("h2", (f"{int(m.group(1)) + OFF}.{m.group(2)}", m.group(3))))
        i += 1
        continue
    if s.startswith("#### "):
        blocks.append(("h3", s[5:].strip()))
        i += 1
        continue
    if s.strip() == "$$":
        j = i + 1
        buf = []
        while L[j].strip() != "$$":
            buf.append(L[j])
            j += 1
        tex = "\n".join(buf)
        tag = re.search(r"\\tag\{([^}]*)\}", tex)
        blocks.append(("eq", (re.sub(r"\\tag\{[^}]*\}", "", tex).strip(), tag.group(1) if tag else "")))
        i = j + 1
        continue
    if s.startswith("> **图"):
        m = re.match(r"> \*\*图\s*(\d+)\.\*\*\s*(.*)", s)
        no, cap = int(m.group(1)), m.group(2).strip()
        files = []
        if i + 1 < len(L) and L[i + 1].startswith("> 图像文件"):
            files = [os.path.basename(f) for f in re.findall(r"`([^`]+)`", L[i + 1])]
            i += 1
        blocks.append(("fig", (no, cap.rstrip("。"), files)))
        i += 1
        continue
    if re.match(r"\*\*表\s*\d+", s):
        m = re.match(r"\*\*表\s*(\d+)\s*(.*?)\*\*$", s)
        pending_tab = (int(m.group(1)), m.group(2).strip().lstrip("　").rstrip("。"))
        i += 1
        continue
    if s.startswith("|"):
        rows = []
        while i < len(L) and L[i].startswith("|"):
            cells = L[i].strip().strip("|").split("|")
            if not all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells):
                rows.append(cells)
            i += 1
        blocks.append(("table", (pending_tab, rows)))
        pending_tab = None
        continue
    if s.startswith("注："):
        blocks.append(("note", s))
        i += 1
        continue
    blocks.append(("p", s))
    i += 1

# a wide (two-column-spanning) figure right after a heading would leave the heading stranded at the
# bottom of the previous columns -> place the figure before the heading
def _is_wide(b):
    return (b[0] == "fig" and b[1][0] in WIDE_FIG) or (b[0] == "table" and b[1][0] and b[1][0][0] in WIDE_TAB)


for k in range(len(blocks) - 1):
    if blocks[k][0] in ("h1", "h2") and _is_wide(blocks[k + 1]):
        j = k + 2 if (k + 2 < len(blocks) and blocks[k + 2][0] == "note" and blocks[k + 1][0] == "table") else k + 1
        blocks[k:j + 1] = blocks[k + 1:j + 1] + [blocks[k]]

# --------------------------------------------------------------------------- front matter
fm = []
fm.append(para("", "", dict(ea=HEI, sz=10)))
fm.append(para(run(title, ea=HEI, ascii_=HEI, sz=36, b=True), "", dict(ea=HEI, sz=10, b=True)))
fm.append(para("", "", dict(ea=HEI, sz=10, b=True)))
au = "".join([run("作者一", ea=FANG, ascii_=FANG, sz=24), run("1", ea=FANG, ascii_=FANG, sz=24, sup=True),
              run("，作者二", ea=FANG, ascii_=FANG, sz=24), run("2", ea=FANG, ascii_=FANG, sz=24, sup=True),
              run("，作者三", ea=FANG, ascii_=FANG, sz=24), run("1,2", ea=FANG, ascii_=FANG, sz=24, sup=True)])
fm.append(para(au, '<w:pStyle w:val="a5"/>', dict(ea=FANG, sz=10)))
fm.append(para("", "", dict(sz=10)))
for k, aff in ((1, "（单位一 院系，城市 邮编）"), (2, "（单位二 院系，城市 邮编）")):
    fm.append(para(run(str(k), ascii_=SONG, sz=15, sup=True) + run(aff, ascii_=SONG, sz=15), "", dict(ascii_=SONG, sz=15)))
fm.append(para(run("E-mail：", sz=15) + run("author@example.com", sz=15), '<w:spacing w:line="360" w:lineRule="auto"/>', dict(sz=15)))
fm.append(para(run("摘", ea=HEI, ascii_=HEI, sz=18, b=True) + run("　", ea=HEI, sz=18, b=True)
               + run("要：", ea=HEI, ascii_=HEI, sz=18, b=True) + run(abstract, ea=KAI, ascii_=TNR, sz=18),
               "", dict(ea=KAI, sz=18, b=True)))
fm.append(para(run("关键词：", ea=HEI, sz=18, b=True) + run(keywords, ea=SONG, sz=18), "", dict(sz=18)))
fm.append(f'<w:p><w:pPr>{rpr(ea=HEI, sz=18, b=True)}{SECT_FRONT_CN}</w:pPr></w:p>')
fm.append(f'<w:p><w:pPr><w:ind w:left="1" w:rightChars="307" w:right="645"/>{rpr(sz=18)}{SECT_CLC}</w:pPr>'
          + run("中图分类号", ea=HEI, sz=18, b=True) + run("：TP391", sz=18) + run("　　　　　", sz=18)
          + run("文献标识码：", ea=HEI, ascii_=HEI, sz=18, b=True) + run("A", sz=18) + "</w:p>")
en_title = "Thin-Structure Recovery for 3D Gaussian Splatting via Cross-Level Geometric Consistency"
fm.append(para(run(en_title, ea=HEI, sz=24, b=True), '<w:spacing w:line="480" w:lineRule="auto"/>', dict(sz=10, b=True)))
eau = "".join([run("AUTHOR One", sz=18), run("1", sz=18, sup=True), run("，AUTHOR Two", sz=18), run("2", sz=18, sup=True),
               run("，AUTHOR Three", sz=18), run("1,2", sz=18, sup=True)])
fm.append(para(eau, '<w:spacing w:line="360" w:lineRule="auto"/>', dict(sz=18)))
for k in (1, 2):
    fm.append(para(run(str(k), sz=15, sup=True) + run("（Department, University, City Postcode, China）", sz=15), "", dict(sz=15)))
fm.append(para(run("Abstract:", sz=18, b=True) + run(" 【待补：英文摘要】", sz=18), "", dict(sz=18)))
en_kw = ("novel view synthesis; 3D Gaussian splatting; anchor-based representation; "
         "cross-level geometric consistency; thin structure")
fm.append(f'<w:p><w:pPr>{rpr(b=True)}{SECT_FRONT_EN}</w:pPr>' + run("Keywords:", sz=18, b=True)
          + run(" " + en_kw, sz=18) + "</w:p>")

# --------------------------------------------------------------------------- body
WIDE_END = object()                              # sentinel: closes a single-column (wide) section
sect_2col = sect_no_titlepg(SECT_BODY)
sect_1col = sect_single_col(sect_no_titlepg(SECT_BODY))
any_wide = False

body_xml = [para("", '<w:spacing w:line="240" w:lineRule="atLeast"/>', dict(ea=HEI, b=True))]


for kind, pl in blocks:
    if kind == "h1":
        body_xml.append(h1(*pl))
    elif kind == "h2":
        body_xml.append(h2(*pl))
    elif kind == "h3":
        body_xml.append(h3(pl))
    elif kind == "p":
        body_xml.append(body(pl))
    elif kind == "eq":
        body_xml.append(equation(pl[0], pl[1], COL_W))
    elif kind == "note":
        if body_xml and body_xml[-1] is WIDE_END:      # note belongs to the wide table above
            body_xml.insert(len(body_xml) - 1, note(pl))
        else:
            body_xml.append(note(pl))
    elif kind == "fig":
        no, cap, files = pl
        wide = no in WIDE_FIG
        blk = figure_placeholder(no, files, PAGE_W if wide else COL_W, 2600 if wide else 1700)
        blk += caption(f"图{no}　{cap}", EN_FIG[no].replace("{n}", str(no)), "fig")
        if wide:
            any_wide = True
            body_xml += [end_section(sect_2col), blk, end_section(sect_1col)]
        else:
            body_xml.append(blk)
    elif kind == "table":
        cap, rows = pl
        if cap:
            no, txt = cap
            wide = no in WIDE_TAB
            w = PAGE_W if wide else COL_W
            blk = caption(f"表{no}　{txt}", EN_TAB[no].replace("{n}", str(no)), "tab") + table(rows, w, 1800 if wide else 1200)
            if wide:
                any_wide = True
                body_xml += [end_section(sect_2col), blk, WIDE_END]
                continue
            body_xml.append(blk)
        else:
            body_xml.append(para("", '<w:spacing w:line="120" w:lineRule="exact"/>')
                            + table(rows, COL_W, 760)
                            + para("", '<w:spacing w:line="120" w:lineRule="exact"/>'))
    elif kind == "refs_head":
        body_xml.append(para(run("References:", sz=18, b=True), '<w:keepNext/><w:spacing w:before="120" w:line="360" w:lineRule="auto"/>', dict(sz=18)))
    elif kind == "ref":
        body_xml.append(reference(*pl))

body_xml = [end_section(sect_1col) if b is WIDE_END else b for b in body_xml]

final_sect = sect_no_titlepg(SECT_BODY) if any_wide else SECT_BODY
xml = HEAD + "".join(fm) + "".join(body_xml) + final_sect + "</w:body></w:document>"

# --------------------------------------------------------------------------- write package
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
shutil.copytree(TPL, OUT)
open(os.path.join(OUT, "word", "document.xml"), "w", encoding="utf-8").write(xml)
def fix_running_header(s):
    """'1 期 <spaces> 作者一 等：文章题目 <spaces> PAGE' -> left / centre-tab / right-tab layout so that a
    long title does not push the page number to a second line."""
    s = s.replace("文章题目", title)
    pm = next(m for m in re.finditer(r"<w:p[ >].*?</w:p>", s, re.S) if title in m.group(0))
    p = pm.group(0)
    runs = re.findall(r"<w:r>.*?</w:r>|<w:r [^>]*>.*?</w:r>", p, re.S)
    out, state, seen_qi, tab_done = [], 0, False, set()
    for r in runs:
        t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", r))
        only_space = t != "" and not t.strip(" \u3000") and "<w:fldChar" not in r and "<w:instrText" not in r
        if title in t:
            out.append(re.sub(r"(<w:t[^>]*>)[^<]*", lambda m: m.group(1) + t.strip(" \u3000"), r))
            state = 1
            continue
        if only_space and ((state == 0 and seen_qi) or state == 1):
            if state not in tab_done:
                out.append('<w:r><w:tab/></w:r>')
                tab_done.add(state)
            continue
        if "期" in t:
            seen_qi = True
        out.append(r)
    ppr = re.search(r"<w:pPr>.*?</w:pPr>", p, re.S).group(0)
    tabs = ('<w:tabs><w:tab w:val="clear" w:pos="4153"/><w:tab w:val="clear" w:pos="8306"/>'
            f'<w:tab w:val="center" w:pos="{PAGE_W // 2}"/><w:tab w:val="right" w:pos="{PAGE_W}"/></w:tabs>')
    ppr_new = re.sub(r"(<w:pStyle [^>]*/>)", lambda m: m.group(1) + tabs + '<w:jc w:val="left"/>', ppr, count=1)
    p_new = p[: p.find("<w:pPr>")] + ppr_new + "".join(out) + "</w:p>"
    return s[: pm.start()] + p_new + s[pm.end():]


for hf in ("header2.xml", "header5.xml"):
    p = os.path.join(OUT, "word", hf)
    s = fix_running_header(open(p, encoding="utf-8").read())
    open(p, "w", encoding="utf-8").write(s)
print("intro number in template:", INTRO_NO, "| blocks:", len(blocks), "| wide sections:", any_wide)
print("figures:", [b[1][0] for b in blocks if b[0] == "fig"], "tables:", [b[1][0][0] if b[1][0] else None for b in blocks if b[0] == "table"],
      "equations:", sum(b[0] == "eq" for b in blocks), "refs:", sum(b[0] == "ref" for b in blocks))
