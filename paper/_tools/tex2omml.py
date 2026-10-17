"""LaTeX -> OMML (Word native equation) via latex2mathml + Office MML2OMML.XSL."""
import re

from latex2mathml.converter import convert
from lxml import etree

XSL = r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"
_xslt = etree.XSLT(etree.parse(XSL))
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _prep(tex):
    t = tex.strip()
    t = t.replace(r"\!", "").replace(r"\,", r"\;")
    t = re.sub(r"\\operatorname\{([^}]*)\}", r"\\mathrm{\1}", t)
    t = t.replace(r"\tfrac", r"\frac").replace(r"\dfrac", r"\frac")
    t = t.replace(r"\lfloor", "⌊").replace(r"\rceil", "⌉")
    t = re.sub(r"\\tag\{[^}]*\}", "", t)
    t = re.sub(r"\\\\\s*\[[^\]]*\]", r"\\\\", t)          # '\\[6pt]' row spacing -> plain row break
    t = t.replace(r"\qquad", "\\text{\u2003\u2003}").replace(r"\quad", "\\text{\u2003}")
    return t


UPRIGHT = {"min", "max", "exp", "log", "sin", "cos", "arg"}


FUNC_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(sorted(UPRIGHT)) + r")(?![A-Za-z])")


def _upright_funcs(s):
    """Typeset min/max/... upright; split them out of merged runs such as '(t)=min'."""
    def fix(m):
        body = m.group(0)
        if "<m:sty" in body or "<m:nor" in body:
            return body
        mt = re.search(r"(<m:t[^>]*>)([^<]*)</m:t>", body)
        text = mt.group(2)
        if not FUNC_RE.search(text):
            return body
        mrpr = re.search(r"<m:rPr>(.*?)</m:rPr>", body, re.S)
        wrpr = re.search(r"<w:rPr>.*?</w:rPr>", body, re.S)
        mr_in = mrpr.group(1) if mrpr else ""
        w = wrpr.group(0) if wrpr else ""
        out = []
        for k, piece in enumerate(FUNC_RE.split(text)):
            if not piece:
                continue
            up = k % 2 == 1
            rp = f"<m:rPr>{mr_in}{'<m:sty m:val=\"p\"/>' if up else ''}</m:rPr>" if (mr_in or up) else ""
            sp = ' xml:space="preserve"' if piece != piece.strip() else ""
            out.append(f"<m:r>{rp}{w}<m:t{sp}>{piece}</m:t></m:r>")
        return "".join(out)
    return re.sub(r"<m:r>.*?</m:r>", fix, s, flags=re.S)


def _left_align_rows(om):
    """Rows of an equation array are centred by default; put an alignment point (m:aln) on the first run
    of every row so that all rows start at the same x (left-aligned multi-line equation)."""
    q = lambda t: f"{{{M_NS}}}{t}"
    for arr in om.iter(q("eqArr")):
        for e in arr.findall(q("e")):
            r = next(e.iter(q("r")), None)
            if r is None:
                continue
            rp = r.find(q("rPr"))
            if rp is None:
                rp = etree.Element(q("rPr"))
                r.insert(0, rp)
            if rp.find(q("aln")) is None:
                etree.SubElement(rp, q("aln"))


def tex_to_omml(tex, size_half_pt=18):
    """Return an <m:oMath> XML string (no xml declaration)."""
    mml = convert(_prep(tex))
    doc = etree.fromstring(mml.encode("utf-8"))
    om = _xslt(doc).getroot()
    if om.tag != f"{{{M_NS}}}oMath":
        found = om.find(f".//{{{M_NS}}}oMath")
        om = found if found is not None else om
    if r"\begin{array}{l}" in tex:
        _left_align_rows(om)
    s = etree.tostring(om, encoding="unicode")
    s = re.sub(r'\s+xmlns:\w+="[^"]+"', "", s)
    s = re.sub(r'\s+xmlns="[^"]+"', "", s)
    # run properties: Cambria Math, body size
    rpr = (f'<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/>'
           f'<w:sz w:val="{size_half_pt}"/><w:szCs w:val="{size_half_pt}"/></w:rPr>')
    s = re.sub(r"<m:r>(\s*<m:rPr>.*?</m:rPr>)?", lambda m: "<m:r>" + (m.group(1) or "") + rpr, s, flags=re.S)
    s = re.sub(r"(<m:r>(?:\s*<m:rPr>.*?</m:rPr>)?)" + re.escape(rpr) + r"\s*<w:rPr>.*?</w:rPr>",
               r"\1" + rpr, s, flags=re.S)
    return _upright_funcs(s)


if __name__ == "__main__":
    for t in [r"\mu_v^i=x_v+O_v^i\odot l_v",
              r"V=\left\{\left\lfloor \frac{P}{\epsilon}\right\rceil\right\}\cdot\epsilon",
              r"D_v^q=\frac{2}{K(K-1)}\sum_{1\le i<j\le K}\left(1-\left|\langle q_v^i,q_v^j\rangle\right|\right)",
              r"s_c=\begin{cases}\min\left(\dfrac{s_p}{\kappa},\epsilon_g^{(m)}\right), & \max(s_p)>\eta\Phi_{\text{scene}},\\[6pt]\min\left(s_p,\epsilon_g^{(m)}\right), & \text{其他情况},\end{cases}"]:
        print(tex_to_omml(t)[:300], "\n")
