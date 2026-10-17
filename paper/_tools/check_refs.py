"""Consistency report for the paper's document.xml (unpacked) or a .docx file.

Checks: equation numbers consecutive and every 式（n） resolvable; figure/table captions consecutive and
every 图n/表n reference resolvable; every 第 x.y 节 reference points to an existing heading; leftover
terms of the three-module version; list of 【待填】 positions; abstract length; Chinese chars per section.
Exit code 1 if a hard error is found.
"""
import html
import re
import sys
import zipfile

src = sys.argv[1]
if src.endswith(".docx"):
    xml = zipfile.ZipFile(src).read("word/document.xml").decode("utf-8")
else:
    xml = open(src, encoding="utf-8").read()
body = xml[xml.index("<w:body>"):]
blocks = re.findall(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>", body, re.S)
text = lambda b: html.unescape("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", b)))
paras = [(b, text(b)) for b in blocks]
errors, warns = [], []

# ---- equations
eq_nos = []
for b, t in paras:
    if b.startswith("<w:p") and "<m:oMath" in b and "<w:tab/>" in b:
        m = re.search(r"\((\d+)\)\s*$", t)
        if m:
            eq_nos.append(int(m.group(1)))
if eq_nos != list(range(1, len(eq_nos) + 1)):
    errors.append(f"equation numbers not consecutive: {eq_nos}")
all_text = "\n".join(t for _, t in paras)
for m in re.finditer(r"式（\d+）(?:[—～、\-](?:式)?（\d+）)*", all_text):
    for n in map(int, re.findall(r"（(\d+)）", m.group(0))):
        if n not in eq_nos:
            errors.append(f"reference {m.group(0)} -> equation ({n}) does not exist")

# ---- figures / tables
def captions(prefix):
    return [int(m.group(1)) for _, t in paras for m in [re.match(prefix + r"(\d+)　", t)] if m]


figs, tabs = captions("图"), captions("表")
for name, nos in (("figure", figs), ("table", tabs)):
    if nos != list(range(1, len(nos) + 1)):
        errors.append(f"{name} captions not consecutive: {nos}")
body_text = "\n".join(t for _, t in paras if not re.match(r"(图|表)\d+　|Fig\.\d|Table \d", t))
for m in re.finditer(r"(图|表)\s*(\d+)(?![\d.])", body_text):
    nos = figs if m.group(1) == "图" else tabs
    if int(m.group(2)) not in nos:
        errors.append(f"reference {m.group(0)} has no caption")
for m in re.finditer(r"【图(\d+)占位】", all_text):
    if int(m.group(1)) not in figs:
        errors.append(f"placeholder 图{m.group(1)} has no caption")
en_figs = [int(m.group(1)) for _, t in paras for m in [re.match(r"Fig\.(\d+) ", t)] if m]
en_tabs = [int(m.group(1)) for _, t in paras for m in [re.match(r"Table (\d+) ", t)] if m]
if en_figs != figs:
    errors.append(f"English figure captions {en_figs} != Chinese {figs}")
if en_tabs != tabs:
    errors.append(f"English table captions {en_tabs} != Chinese {tabs}")

# ---- sections
heads = [m.group(1) for _, t in paras for m in [re.match(r"(\d+(?:\.\d+){0,2})　\S", t)] if m]
for m in re.finditer(r"第\s*(\d+(?:\.\d+)+)\s*节", all_text):
    if m.group(1) not in heads:
        errors.append(f"section reference {m.group(0)} has no heading")

# ---- leftovers of the three-module version
for pat in (r"(?<![A-Za-z])GP(?![A-Za-z])", "置信度引导几何保持", "父锚点感知几何继承",
            "检测—传递—保持", "传承", "成熟度", "出生尺度", "几何细化", "【待定", "三个组成部分共同",
            # wording unified in the journal-style revision
            "覆盖像素率", "补种", "细结构点", r"(?<![A-Za-z])AS(?![A-Za-z])", "[Ss]eed", "多视图实体性", "细长性", "实体性", "悬空性", "空缺性", "几何条件",
            "[Ee]longation", "[Ss]olidity", "[Vv]acancy", "本文模型",
            "置信度", r"\*\*"):
    for m in re.finditer(pat, all_text):
        ctx = all_text[max(0, m.start() - 25): m.end() + 25].replace("\n", " ")
        warns.append(f"leftover {pat!r}: …{ctx}…")

# ---- 【待填】
todo = [(t[:40].replace("\n", " "), t.count("【待填】")) for _, t in paras if "【待填】" in t]

# ---- lengths
han = lambda s: len(re.findall(r"[\u4e00-\u9fff]", s))
abstract = next(t for _, t in paras if t.startswith("摘　要："))
abs_n = han(abstract[4:])
if abs_n > 300:
    warns.append(f"abstract has {abs_n} Chinese chars (> 300)")
sec, counts = "front", {}
for b, t in paras:
    m = re.match(r"(\d+)　(\S.*)$", t)
    if m and "<w:keepNext/>" in b and len(t) < 20:
        sec = t
    elif t.startswith("References:"):
        sec = "References"
    if b.startswith("<w:p") and not re.match(r"(图|表)\d+　|Fig\.|Table ", t):
        counts[sec] = counts.get(sec, 0) + han(t)

print("==== check_refs")
print("equations:", f"(1)-({len(eq_nos)})", "| figures:", figs, "| tables:", tabs)
print("headings:", " ".join(heads))
print(f"abstract: {abs_n} Chinese chars")
print("Chinese chars per part:", ", ".join(f"{k}={v}" for k, v in counts.items()))
print(f"【待填】: {sum(n for _, n in todo)} in {len(todo)} blocks")
for t, n in todo:
    print(f"   x{n}  {t}")
for w in warns:
    print("WARN", w)
for e in errors:
    print("ERROR", e)
print("OK" if not errors else f"{len(errors)} error(s)")
sys.exit(1 if errors else 0)
