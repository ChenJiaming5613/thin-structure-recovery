"""Text content of the paper (final numbering; the template numbers the introduction 0).

Kept separate from restructure.py so the wording can be edited without touching the XML logic.
Storyline: suspended thin structures are hard to recover because (1) the initial point cloud is missing there and
(2) they cover few pixels. IE answers (1); GR + GT answer (2).
Sections: 1.1 detail recovery in 3DGS, 1.2 anchor-based 3DGS, 1.3 point cloud initialization;
2.1 preliminaries, 2.2 IE (2.2.1-2.2.4), 2.3 GR, 2.4 GT (2.4.1 inheritance / 2.4.2 preservation);
3.1 setup (3.1.1-3.1.3), 3.2 results (3.2.1-3.2.6) -- every result subsection lives under 3.2.
Style follows the journal (Journal of Chinese Computer Systems): numbered subsections instead of bold run-in heads,
"1）……；" lists, few semicolon chains. Terms: 锚点初始化增强 / 几何致密化 / 几何继承 (full names 细结构感知的锚点初始化增强 /
几何离散度引导的致密化 / 局部结构感知的几何继承), IE steps 细结构候选提取、多视图验证、悬空检测和点云去重, 初始点云缺失 / 像素覆盖率低, 补充点 / 补充锚点, loop 初始化—致密化—继承.
Equations: (1)-(5) preliminaries, (6)-(8) IE, (9)-(13) GR, (14)-(15) inheritance, (16)-(17) preservation.
Tables: 1 main comparison, 2 ablation.
Figures: the text below still numbers them 2-7 (old Fig.1 = failure examples, removed for space); restructure.py
deletes Fig.1 and shifts every figure number by -1 in a final pass, so the paper has Figures 1-6.
Datasets: UrbanAerial3D, Mill-19 (Rubble + Building pooled), Waymo (9 scenes). Baselines: 3DGS, ResGS, EDGS, Scaffold-GS,
Octree-GS. Results that are not measured yet are written as TODO.
"""

TITLE_CN = "基于跨层级几何一致性的三维高斯泼溅细结构恢复"
TITLE_EN = "Thin-Structure Recovery for 3D Gaussian Splatting via Cross-Level Geometric Consistency"

TODO = "【待填】"

# --------------------------------------------------------------------------- authors (title page + first-page footer)
AUTHORS_CN = [("陈佳明", "1"), ("张严辞", "1,2")]                  # (name, affiliation superscript)
AUTHORS_EN = [("CHEN Jiaming", "1"), ("ZHANG Yanci", "1,2")]
AFFIL_CN = [("1", "（四川大学 视觉合成图形图像国家重点学科实验室，成都 610065）"),
            ("2", "（工程数值模拟基础算法与模型全国重点实验室，成都 620107）")]
AFFIL_EN = [("1", "（National Key Laboratory of Fundamental Science on Synthetic Vision, Sichuan University, "
                  "Chengdu 610065, China）"),
            ("2", "（National Key Laboratory of Fundamental Algorithms and Models for Engineering Simulation, "
                  "Chengdu 620107, China）")]
EMAIL = "yczhang@scu.edu.cn"                                      # corresponding author only (template: one address)
RECEIVED = ""                                                     # filled in by the editorial office
FUND = TODO                                                       # 基金中文完整名称（项目号）
BIOS = [("陈佳明", "", "男，2002 年生，硕士研究生，研究方向为计算机图形学"),
        ("张严辞", "（通信作者）", "男，1975 年生，博士，教授，CCF 专业会员，研究方向为计算机图形学")]

# --------------------------------------------------------------------------- front matter
ABSTRACT = (
    "3D高斯泼溅（3DGS）凭借高质量实时渲染，已成为新视图合成的重要表示，并为巡检与检测等下游应用提供"
    "三维场景基础。然而，输电线、塔吊臂等细结构仍易出现缺失与断裂，主要原因是弱纹理导致初始点云缺失，以及低像素覆盖削弱优化信号。"
    "为此，本文提出基于跨层级几何一致性的细结构恢复方法，在场景层补充缺失的几何支撑，并在表示层维持锚点与细结构以及"
    "父子锚点之间的几何一致性，形成“初始化—致密化—继承”闭环。具体而言，多视图几何增强建立细结构的初始表示，几何离散度驱动"
    "锚点致密化，局部结构继承则稳定新增锚点的尺度。该设计既弥补场景层到表示层的几何缺失，又抑制锚点层级增长中的尺度漂移。"
    "实验结果表明，本文方法在 UrbanAerial3D、Mill-19 和 Waymo 等细结构丰富场景上均提升了 PSNR 并降低了 LPIPS，"
    "同时改善了细结构的完整性与连续性。"
)
KEYWORDS = "三维高斯泼溅；新视图合成；细结构恢复；锚点式表示；点云初始化；跨层级几何一致性"
EN_ABSTRACT_OLD = "【待补：英文摘要】"
EN_ABSTRACT = (
    "With high-quality real-time rendering, 3D Gaussian Splatting (3DGS) has become an important representation for "
    "novel-view synthesis and provides a 3D scene basis for downstream applications such as inspection and detection. "
    "However, thin structures, including power lines and tower-crane jibs, are still prone to missing geometry and "
    "discontinuities, mainly because weak textures cause missing initial point clouds and low pixel coverage weakens "
    "optimization signals. To address these issues, we propose a thin-structure recovery "
    "method based on cross-level geometric consistency. It supplements missing geometric support at the scene level and "
    "maintains geometric consistency between anchors and thin structures, as well as between parent and child anchors, "
    "at the representation level, forming an initialization-densification-inheritance loop. Specifically, multi-view "
    "geometric enhancement establishes initial representations for thin structures, geometric dispersion drives anchor "
    "densification, and local-structure inheritance stabilizes the scales of newly added anchors. This design both "
    "bridges missing geometry from the scene level to the representation level and suppresses scale drift during "
    "hierarchical anchor growth. Experimental results show that "
    "on the thin-structure-rich UrbanAerial3D, Mill-19, and Waymo scenes, our method improves PSNR and reduces LPIPS "
    "while improving the completeness and continuity of thin structures."
)
EN_KW_OLD = "novel view synthesis; 3D Gaussian splatting; anchor-based representation; cross-level geometric consistency; thin structure"
EN_KW_NEW = ("3D Gaussian splatting; novel view synthesis; thin-structure recovery; anchor-based representation; "
             "point cloud initialization; cross-level geometric consistency")

# --------------------------------------------------------------------------- introduction
INTRO_P1 = (
    "三维高斯泼溅（3D Gaussian Splatting，3DGS）[1] 以显式高斯表示和可微光栅化兼顾了高保真重建与实时渲染，已成为新视图合成的"
    "重要技术，并开始服务于无人机输电线路巡检[3]等依赖三维场景的检测应用。然而，输电线、塔吊臂、太阳能板边缘等细结构仍易出现"
    "缺失、断裂或与背景粘连，直接影响场景几何的完整性及后续检测的可靠性。"
)
INTRO_P2 = (
    "细结构恢复面临两个共性难点。其一是初始点云缺失。现有 3DGS 方法通常由运动恢复结构（Structure from Motion，SfM）[20] 的稀疏"
    "点云初始化。细结构普遍缺少稳定角点，沿结构方向的外观高度重复，且仅跨越少量像素，因而难以建立可靠对应并生成 SfM 点；悬空细"
    "结构以天空或远处表面为背景时，这一问题尤为突出。由于后续致密化通常局限于已有基元邻域，初始点云中完全缺失的结构在训练过程中"
    "仍难以获得有效表示。稠密匹配初始化[33]虽能增加点数，但在细线上易沿用背景对应，新增点仍可能落在背景表面。"
)
INTRO_P3 = (
    "其二是像素覆盖率低。细结构仅占据少量像素，其光度贡献容易被大面积背景稀释，使基于视角平均梯度的致密化[1,4,5]难以触发；背景"
    "主导的优化还会使基元尺度扩张，同时拟合细前景与宽背景。增强梯度统计[4,5]只能使致密化更易触发，却无法判断局部表示是否已被细"
    "前景与背景共同占据而需要拆分，因此仅依赖光度梯度难以稳定恢复细结构。"
)
INTRO_P4 = (
    "为对细结构施加结构级约束，本文选择 Scaffold-GS [2] 作为基础。不同于原始 3DGS 中相互独立的高斯基元，Scaffold-GS 以锚点组织"
    "局部高斯，使锚点成为连接场景几何与高斯表示的中间层，既可在锚点层控制局部结构，又保留高斯层的表达自由度。然而，其锚点仍由 "
    "SfM 点云初始化并在已有表示附近增长，致密化也依赖累计位置梯度；新增锚点按体素层级重置尺度，未利用父锚点已经学习到的局部结构。"
    "因此，Scaffold-GS 仍受初始点云缺失与低像素覆盖限制，并在锚点与细结构、父锚点与子锚点之间产生几何失配。"
)
INTRO_P5 = (
    "基于上述分析，本文在 Scaffold-GS 上沿锚点的初始化、致密化与层级增长依次处理上述难点，使锚点及其解码高斯的尺度与所覆盖的"
    "细结构保持一致，本文将这一目标称为跨层级几何一致性。"
)
CONTRIB = [
    "1）针对初始点云缺失，提出细结构感知的锚点初始化增强，以细结构距离变换代替光度代价进行多视图深度扫描，并在全深度扫描后进行"
    "悬空判定，仅在 SfM 未覆盖的悬空细结构处补充锚点；",
    "2）针对像素覆盖率低，提出几何离散度引导的致密化与局部结构感知的几何继承：前者以锚点内解码高斯的尺度与方向分歧提供不依赖"
    "像素数量的致密化依据，后者使子锚点继承父锚点已优化的基础尺度并在充分观测前加以保持，避免新增锚点被背景重新主导；",
    "3）在 UrbanAerial3D、Mill-19 和 Waymo 上的实验表明，本文方法能够有效恢复不同类型的细结构并提升新视图合成质量。",
]

# --------------------------------------------------------------------------- related work (three subsections)
RW = [
    ("1.1", "三维高斯泼溅的细节恢复", [
        "神经辐射场（Neural Radiance Fields，NeRF）[7] 奠定了高质量新视图合成的基础。Kerbl 等人[1]提出的 3DGS 以可微光栅化"
        "替代射线步进，实现了实时渲染，其细节由自适应致密化决定：当视角平均的位置梯度超过阈值时，高斯会被克隆或分裂。针对欠重建区域，"
        "Ye 等人[4]提出的 AbsGS 累加梯度的绝对值，避免了不同像素的梯度相互抵消。Lyu 等人[5]提出的 ResGS 以残差分裂补充缩小的"
        "高斯，从而恢复欠重建的细节。FreGS [6] 对渲染频谱施加渐进式正则，Mip-Splatting [14] 则依据采样率约束高斯带宽以抑制混叠。"
        "此外，2DGS [15]、SuGaR [16]、GeoGaussian [17]、GaussianPro [18] 和 PGSR [19] 引入了表面、平面或点云先验，以改善重建"
        "的几何。",
        "然而，这些方法均假设待恢复区域已经存在高斯，并且其光度误差足以产生梯度，而悬空细结构同时违背了这两个前提。一方面，没有"
        "初始点时，致密化没有作用对象；另一方面，像素覆盖率低时，细结构的梯度在视角平均中被背景稀释，即使是强化后的准则也难以触发。"
        "此外，表面先验同样不适用于悬空的线状结构。",
    ]),
    ("1.2", "锚点式三维高斯泼溅", [
        "Lu 等人[2]提出的 Scaffold-GS 将 SfM 点云体素化为锚点，每个锚点以共享特征解码一组局部高斯，并在已有锚点所解码高斯的附近"
        "增长新锚点。在此基础上，Ren 等人[23]提出的 Octree-GS 以八叉树组织多分辨率锚点，以支持细节层次渲染。SOGS [24] 以二阶"
        "锚点增强表达能力，Proxy-GS [25] 引入遮挡先验以约束训练与推理，HAC++ [27] 则以上下文模型压缩锚点表示。这些工作主要改进了"
        "锚点的层级组织、表达能力或存储效率。",
        "锚点为局部高斯组提供了结构载体，但现有锚点式方法尚未显式约束同一锚点内解码高斯的几何一致性。当组内高斯分别拟合细前景与背景"
        "时，锚点仍被视为统一载体，缺少依据尺度与方向分歧调整局部结构的机制。同时，锚点致密化仍依赖跨视角聚合的累计位置梯度，细结构"
        "有限的像素贡献容易在聚合中被稀释；新增锚点又按体素层级初始化基础尺度，丢弃父锚点已经学习到的局部宽度与各向异性。现有方法"
        "虽改进了锚点的层级组织、表达能力或存储效率，但仍未解决锚点内部及父子层级间的几何一致性问题。",
    ]),
    ("1.3", "点云初始化", [
        "SfM [20] 依赖角点特征匹配，对缺少纹理且仅跨越少量像素的细长结构通常是病态的。Liu 等人[21]提出的 LIMAP 能够重建场景中的"
        "三维线段，但对与核面近似平行的线段存在退化，下垂曲线也需要切分为短段。Vid2Curve [31] 与 Slender3D [32] 通过曲线重投影"
        "重建细长物体，但二者依赖前景掩码，并且需要重新估计相机位姿。另一类方法致力于降低 3DGS 对初始化的依赖。Kheradmand 等人[22]"
        "提出的 3DGS-MCMC 将高斯视为马尔可夫链蒙特卡洛样本，以重定位替代启发式致密化。Kotovenko 等人[33]提出的 EDGS 则在训练前"
        "以稠密匹配一次性三角化大量点，以此替代致密化。",
        "上述方法或者重建全部线结构而不区分其是否已被 SfM 覆盖，或者依赖外观对应与梯度生长，而这两者在细线上均不可靠。与之不同，"
        "本文的锚点初始化增强不追求重建完整的曲线，而是依据多视图几何识别悬空且未被 SfM 覆盖的细结构，只在这些位置补充锚点，并与锚点式表示的"
        "增长机制相衔接。",
    ]),
]

# --------------------------------------------------------------------------- method overview + preliminaries
PRE_TITLE = "Scaffold-GS锚点表示与增长机制"
METHOD_OVERVIEW = [
    "本节首先在第 2.1 节介绍 Scaffold-GS 的锚点表示与增长机制及其不足，随后沿锚点的生命周期给出所提方法的三个组成部分：",
    "1）细结构感知的锚点初始化增强（第 2.2 节）：训练前固定 SfM 位姿，经细结构候选提取、多视图验证、悬空检测和点云去重，"
    "在 SfM 的空缺处补充初始锚点；",
    "2）几何离散度引导的致密化（第 2.3 节）：以锚点内解码高斯的几何分歧检测同时拟合细前景与背景的锚点，并对其进行致密化；",
    "3）局部结构感知的几何继承（第 2.4 节）：以父锚点已优化的局部尺度初始化子锚点，并在其获得充分观测前加以保持。",
    "如图 2 所示，三者依次作用于锚点的初始化、致密化与层级增长，构成“初始化—致密化—继承”闭环。",
]
PRE_P1 = (
    "其中，$V\\in\\mathbb{R}^{N\\times3}$ 为 $N$ 个去重后的体素中心，$\\epsilon$ 为初始体素尺度。每个体素中心 $x_v\\in V$ 作为"
    "一个锚点，包含特征 $f_v$、位置尺度 $l_v\\in\\mathbb{R}^{3}$、基础尺度 $s_v\\in\\mathbb{R}^{3}$ 以及 $K$ 个可学习偏移 "
    "$\\{O_v^i\\}_{i=1}^{K}$。可见锚点所解码的第 $i$ 个神经高斯的中心为"
)
PRE_P2 = (
    "式（4）的乘性分解使基础尺度 $s_v$ 同步作用于该锚点所解码的全部高斯，而相对尺度 $r_v^i$ 保留了高斯之间的差异，因此本文以 "
    "$s_v$ 作为几何继承的对象。"
)
PRE_P3 = (
    "其中，$\\epsilon_g$ 为增长阶段的体素尺度，$m$ 为增长层级。该初始化只由全局增长日程决定，丢弃了父锚点已学到的各向异性尺度。"
    "对于覆盖像素少的细结构，新增锚点获得的有效梯度有限，体素尺度可能使其重新吸收背景像素。此外，新锚点仅由已有锚点所解码高斯的"
    "中心 $\\mu_v^i$ 体素化产生，因此初始点云 $P$ 中完全缺失的结构在训练中不会获得锚点。"
)
PRE_GROW = "在锚点增长过程中，新增锚点根据由层级决定的体素尺度进行初始化："

# --------------------------------------------------------------------------- 2.2 anchor initialization enhancement
AS_TITLE = "细结构感知的锚点初始化增强"          # edited by the author in Word (2026-10-16)
AS_BLOCKS = [
    ("p", "SfM 在悬空细结构上的失效发生在对应关系阶段，而非几何阶段：背景区域保证了相机位姿的可靠性，细结构的三维位置仍然可以由"
          "多视图几何确定。据此，本文在训练前固定 COLMAP 位姿，依据多视图几何识别悬空细结构，并在其附近补充点。由于锚点由初始点云体素化得到（式（1）），向初始点云中补充点即可增强锚点初始化。由于锚点的位置与偏移"
          "均可优化，补充点只需落在结构的若干个体素尺度 $\\epsilon$ 以内，精确的对齐由后续的致密化与继承完成。"),
    ("h3", "2.2.1　补充点集构造"),
    ("p", "补充点集的构造分为四个步骤：细结构候选提取在图像中提取细长结构的候选像素，多视图验证在邻近视图中确定并验证候选的深度，"
          "悬空检测保留位于后方表面之前的点，点云去重则剔除已被原始点云覆盖的点。其中，前两个步骤保证补充点位于真实的细结构上，"
          "后两个步骤将补充点限定在锚点缺失的悬空区域。记参考视图 $r$ 中像素 $p$ 的视线为 $X_r(p,d)=C_r+d\\,\\mathbf{r}_r(p)$，其中 $C_r$ 为相机中心，"
          "$d$ 为相机坐标系深度，则补充点集定义为"),
    ("eq", (r"\begin{array}{l}P_{\text{thin}}=\{X_r(p,d_p^{*})\mid p\in\mathcal{C}_r,\ S_p(d_p^{*})\ge n_{\min},\\"
            r"\quad d_p^{*}<\rho\,Z_r^{\text{bg}}(p),\ \mathrm{dist}(X_r(p,d_p^{*}),P)>\lambda_f\,\xi_p\}\end{array}", 6)),
    ("p", "其中，$p\\in\\mathcal{C}_r$ 表示 $p$ 为细结构候选像素，其后的三个不等式依次为多视图验证、悬空检测和点云去重的判据。"
          "$\\rho<1$ 为前方比例，$\\xi_p=d_p^{*}/f$ 为像素足迹（$f$ 为焦距），它使距离阈值与场景尺度无关。每幅图像轮流作为参考"
          "视图，分别按式（6）生成补充点。"),
    ("h3", "2.2.2　细结构候选提取与多视图验证"),
    ("p", "候选像素集 $\\mathcal{C}_j$ 由多尺度 Hessian 脊线响应[34,35]与小尺度亮斑响应给出。脊线响应经过方向一致的线积分连接"
          "断续的线段，并预先计算到同类候选的距离变换 $\\mathcal{D}_j(\\cdot)$。二维检测不区分语义，误检交由后续的几何步骤"
          "剔除。多视图验证沿视线进行固定位姿的深度扫描[36]，以细结构距离变换代替光度代价，统计投影落在邻近视图 $\\mathcal{N}(r)$ 中"
          "同类候选附近的视图数："),
    ("eq", (r"\begin{array}{l}S_p(d)=\sum_{j\in\mathcal{N}(r)}v_j(d)\,\mathbf{1}\left[\mathcal{D}_j\left(\pi_j(X_r(p,d))\right)\le\delta\right],\\"
            r"d_p^{*}=\underset{d}{\mathrm{arg\,max}}\,S_p(d)\end{array}", 7)),
    ("p", "其中，$\\pi_j$ 为视图 $j$ 的投影，$\\delta$ 为像素容差。有效指示 $v_j(d)$ 剔除细线与核线近似平行的退化视图[21]，以及"
          "样本位于该视图背景表面之后的遮挡视图。此外，$d_p^{*}$ 还须在有效视图中占多数且沿视线唯一，以排除平行导线、重复灯泡等"
          "造成的多重解。该过程以细结构几何而非外观建立对应，因而不受天空等无纹理背景的影响，其几何含义与曲线重投影对齐[31,32]一致。"),
    ("h3", "2.2.3　悬空检测"),
    ("p", "悬空细结构与表面纹理边缘都能通过候选提取与多视图验证，二者的区别在于前者的深度显著小于同一视线后方的表面。由于弱纹理表面与远处"
          "背景上往往没有 SfM 点，本文使用单目深度估计网络 Depth Anything V2 [37] 重建每幅图像的背景深度。设其预测的相对视差为 "
          "$\\omega_j(x)$，本文以视图 $j$ 中可见的 SfM 点集 $P_j$ 为样本，在视差空间中鲁棒拟合仿射变换，并对结果进行局部最大值"
          "滤波："),
    ("eq", (r"\begin{array}{l}Z_j^{\text{bg}}(x)=\max_{y\in\mathcal{W}(x)}\frac{1}{a_j\omega_j(y)+b_j},\\"
            r"(a_j,b_j)=\underset{a,b}{\mathrm{arg\,min}}\sum_{X\in P_j}\left|a\,\omega_j(\pi_j(X))+b-\frac{1}{z_j(X)}\right|\end{array}", 8)),
    ("p", "其中，$z_j(X)$ 为点 $X$ 在视图 $j$ 中的深度，$\\mathcal{W}(x)$ 为以 $x$ 为中心的 $b\\times b$ 邻域。局部最大值滤波使"
          "细结构像素继承其后方表面的深度，拟合误差过大的视图则不进行悬空检测。需要注意的是，悬空检测作用于全深度区间扫描得到的最优"
          "深度，最优解不在背景之前时即丢弃该候选。若将扫描截断在背景之前，位于表面上的候选会被迫取得表面前方的次优解，反而会产生"
          "悬浮伪点。"),
    ("h3", "2.2.4　点云去重与合并"),
    ("p", "点云去重按式（6）的最后一个不等式剔除与原始点云重合的点，使补充点只出现在原始点云未覆盖的位置。此外，每个点还须在半径 $\\lambda_s\\xi_p$ 内被至少 $n_r$ 个其他参考视图的"
          "结果印证，以剔除单视图的偶然对齐。最终，本文以体素 $\\epsilon$ 对 $P_{\\text{thin}}$ 降采样，并以 "
          "$P'=P\\cup P_{\\text{thin}}$ 代替式（1）中的 $P$。补充锚点作为初始锚点进入后续的生命周期：其观测充分度按式（12）随"
          "可见次数累积；达到充分观测前受第 2.4.2 节的保持项约束，达到充分观测后由第 2.3 节的离散度检测决定是否致密化。"),
]

# --------------------------------------------------------------------------- 2.3 GR
GR_TITLE = "几何离散度引导的致密化"
GR_P1 = (
    "Scaffold-GS 的致密化由累计位置梯度驱动，其幅值主要取决于像素残差与可见范围。对于仅覆盖少量像素的细结构，即使锚点内部的高斯"
    "已经分别趋向细前景与背景，聚合后的梯度也可能不足以触发致密化；单纯降低阈值或增强梯度统计[4,5]又会在背景区域引发冗余致密化。"
    "然而，这种共同承载会直接体现在锚点内部：拟合细结构的高斯沿结构方向变得细长，拟合背景的高斯则保持宽大，二者的相对尺度与朝向"
    "随之分化，且不会因细结构覆盖的像素少而被稀释。因此，本文以锚点内部的几何分歧作为致密化的补充依据。"
)
GR_P2 = (
    "对于锚点 $v$，本文以相对尺度离散度 $D_v^r$ 和方向离散度 $D_v^q$ 分别度量其解码高斯之间的形状差异与朝向差异，并将二者组合为"
    "锚点几何离散度 $D_v$："
)
GR_P3 = (
    "其中，$\\bar{r}_v=\\tfrac{1}{K}\\sum_{i=1}^{K}r_v^i$，系数 $\\tfrac{4}{3}$ 将 $D_v^r$ 归一化，$D_v^q$ 中的绝对值消除了"
    "四元数的符号歧义 $q\\equiv -q$，$\\lambda_r$ 与 $\\lambda_q$ 用于平衡形状差异与朝向差异。式（9）以组内均值为参照，与基础"
    "尺度的绝对量级无关，因而不同层级的锚点之间可以直接比较。$D_v$ 只用于判断锚点是否仍适合作为其高斯的共同载体，无需语义标签或"
    "掩膜监督。"
)
GR_CONF_INTRO = (
    "新增锚点在优化早期尚未累积充分观测，此时其几何离散度估计并不稳定。令 $n_v(t)$ 表示迭代 $t$ 时锚点 $v$ 在训练视角中"
    "累计可见的次数，并定义观测充分度："
)
GR_GATE = (
    "其中，$N_{\\text{conf}}\\in\\mathbb{N}_{+}$ 为观测充分度的饱和阈值。仅当锚点获得充分观测且几何离散度超过阈值时，才启用"
    "离散度引导的致密化："
)
GR_P4 = (
    "其中，$\\tau_{\\text{disp}}$ 根据场景特性调节。观测充分度 $c_v(t)$ 由锚点的累计可见次数归一化得到，刻画其实际获得的优化证据，因而不同时刻生成的"
    "锚点均可按自身观测状态接受调度。该门控仅在观测充分后启用离散度判定，避免将初始化噪声或偶然观测误判为几何冲突，同时为"
    "第 2.4.2 节的尺度保持提供统一的调度变量。"
)

# --------------------------------------------------------------------------- 2.4 GT
GT_TITLE = "局部结构感知的几何继承"
GT_INTRO = (
    "致密化决定何时增加表示容量，但并不决定新增锚点如何初始化其几何属性。局部结构感知的几何继承作用于子锚点的基础尺度 $s_v$，"
    "包括初始化时继承父锚点尺度（第 2.4.1 节）和达到充分观测前保持该尺度（第 2.4.2 节）两个环节。二者缺一不可：缺少保持时，"
    "继承的尺度会在背景主导的早期更新中丢失；缺少继承时，被保持的只是与局部结构无关的体素尺度。"
)
GT_SUB1 = "2.4.1　继承式尺度初始化"
GT_SUB2 = "2.4.2　观测充分度引导尺度保持"
GT_P1 = (
    "父锚点在被选中致密化之前，已经由多个训练视角拟合，其基础尺度包含了局部结构的宽度与各向异性。若子锚点改用体素尺度初始化，则需要"
    "依赖细结构本就缺少的光度梯度重新学习尺度。"
)
GT_P2 = (
    "式（14）在传递父锚点尺度的同时，以 $\\epsilon_g^{(m)}$ 作为与层级兼容的逐轴上界。其中，分裂分支以更细的粒度分担父锚点的"
    "区域，克隆分支则不额外收缩，以免在本已较小的结构上产生覆盖缺口。由于最小值按元素计算，父锚点沿细结构方向较长、垂直方向较短的"
    "各向异性尺度能够在未超过上界的分量上传给子锚点。继承所得的 $s_c$ 记为子锚点的初始尺度先验。"
)
GT_P3 = (
    "继承后的尺度在优化早期仍然可能漂移。这是因为细结构仅占渲染像素的一小部分，背景残差可能主导尺度的更新。由式（4）可知，约束"
    "基础尺度 $s_v$ 即可稳定整组高斯的覆盖范围，同时允许相对尺度 $r_v^i$ 与偏移 $O_v^i$ 由光度目标自由优化。因此，本文以观测充分度 "
    "$c_v(t)$ 调度对 $s_v$ 的正则。"
)
GP_PRIOR = (
    "对于每个锚点 $v$，令 $s_v^{\\text{init}}$ 为其初始尺度先验。其中，增长得到的锚点由第 2.4.1 节给出，初始锚点（包括补充"
    "锚点）则取其初始基础尺度。本文将当前基础尺度 $s_v(t)$ 正则化到该先验："
)
GP_PRESERVE = (
    "其中，$\\mathcal{A}(t)$ 表示迭代 $t$ 时参与优化的锚点集合。权重 $1-c_v(t)$ 在锚点初始化时最大，并随可见次数接近 "
    "$N_{\\text{conf}}$ 衰减至零。同一观测充分度同时调度初始尺度保持与几何离散度判定。"
)
GP_LOSS = (
    "其中，$\\lambda_{\\mathrm{SSIM}}$、$\\lambda_{\\mathrm{vol}}$ 和 $\\lambda_{\\mathrm{pres}}$ 分别表示对应项的权重。当 "
    "$c_v(t)$ 达到饱和后，尺度保持权重归零，该锚点开始具备接受式（13）几何离散度检测的资格，从而衔接初始化阶段的尺度稳定与后续致密化。"
)

# --------------------------------------------------------------------------- experiments: setup
SETUP_BLOCKS = [
    ("h3", "3.1.1　实验环境与实现细节"),
    ("p", "本文所有实验均在一张 NVIDIA A6000 GPU 上进行，所有方法均训练 30 000 次迭代。本文方法在 Scaffold-GS [2] 的基础上实现，"
          "每个锚点解码 $K=10$ 个神经高斯，多层感知机为隐藏维数 32 的两层 ReLU 网络。跨场景固定的超参数为 $\\eta=0.01$、"
          "$\\kappa=1.6$、$\\lambda_{\\text{pres}}=0.01$、$\\lambda_r=0.3$ 和 $\\lambda_q=0.7$；$\\tau_{\\text{disp}}$ 与 "
          "$N_{\\text{conf}}$ 根据不同场景的结构复杂度与观测条件进行调节。"),
    ("p", "锚点初始化增强在训练前于 CPU 上运行一次，依次完成细结构候选提取、多视图验证、悬空检测和点云去重四个步骤。每幅训练视图"
          "选取 16 个邻近视图作为参考视图，沿视线按逆深度采样 192 个深度，并取 $\\delta=2$、$n_{\\min}=5$、$\\rho=0.9$、"
          "$n_r=2$，核线与细线夹角小于 15° 的视图对视为退化情形并予以跳过。"),
    ("h3", "3.1.2　数据集"),
    ("p", "本文使用 3 个数据集进行实验。UrbanAerial3D 为本文自建的城市航拍数据集，覆盖高层建筑、街道与开阔场地等城区环境，"
          "场景中广泛分布横跨街道的架空电线、路灯杆与信号杆等悬空细结构，主要用于检验本文方法在高分辨率航拍视角下恢复细结构的能力。"
          "Mill-19 [29] 为大范围无人机航拍数据集，以废墟工地与厂房屋顶为主体，包含输电线、塔吊臂与屋顶桁架等结构，是评估方法"
          "在大尺度无边界场景下重建质量的常用基准。本文选用其中的 Rubble 与 Building 两个场景，沿用 "
          "Mega-NeRF [29] 的标准训练/测试划分，并汇总两个场景的测试视图报告 Mill-19 上的结果。Waymo Open Dataset [38] 则包含车载相机采集的真实城市街景序列及精确的相机位姿，"
          "场景中的路灯杆、信号杆与架空线缆贴近自动驾驶的实际需求；本文采用 GaussianPro [18] 公开的预处理版本，"
          "用于测试本文方法在车载视角下的表现。"),
    ("h3", "3.1.3　基线方法"),
    ("p", "本文将所提方法与 5 种具有代表性的方法进行比较，包括原始 3DGS [1]、面向细节恢复的致密化方法 ResGS [5]、以稠密匹配初始化"
          "替代致密化的 EDGS [33]，以及锚点式方法 Scaffold-GS [2] 与 Octree-GS [23]。这些方法分别代表了无结构表示、强化致密化、"
          "稠密初始化与锚点式表示 4 条技术路线，其中 ResGS 的发布实现以 AbsGS [4] 为基础。为保证比较的公平性，所有方法均使用相同的"
          "数据划分与训练迭代次数，并统一采用峰值信噪比（Peak Signal-to-Noise Ratio，PSNR）、结构相似性（Structural Similarity，"
          "SSIM）和学习感知图像块相似度（Learned Perceptual Image Patch Similarity，LPIPS）[30] 评价整幅测试图像的新视图合成"
          "质量，其中前两者越高、后者越低表示质量越好。"),
]
FIG3_FILES_OLD = "all-hr10.pdf"
FIG3_FILES_NEW = "all-hr10-labeled.png、all-rubble.png、all-building.png"
FIG3_CAP = "图3　不同场景下的细结构恢复结果"
FIG3_EN = "Fig.3 Thin-structure recovery results in different scenes"
FIG3_PANELS = [("all-hr10-labeled.png", "(a)"),  # 6 rows (methods) x 3 columns (datasets), stacked vertically
               ("all-rubble.png", "(b)"),
               ("all-building.png", "(c)")]
TAB1_CAP = "表1　各方法的定量比较"
TAB1_EN = "Table 1 Quantitative comparison of different methods"
TABLE_GROUPS = ["UrbanAerial3D", "Mill-19", "Waymo"]   # Mill-19 = Rubble + Building, test views pooled
TABLE_METRICS = ["PSNR ↑", "SSIM ↑", "LPIPS ↓"]
# Source: D:/GS/Scaffold-GS/数据.csv (2026-10-16). Values are ordered by TABLE_GROUPS × TABLE_METRICS.
TAB1_ROWS = [
    ["3DGS [1]", "26.54", "0.858", "0.135", "28.22", "0.902", "0.122", "24.95", "0.823", "0.299"],
    ["ResGS [5]", "26.78", "0.864", "0.128", "28.19", "0.916", "__0.091__", "__26.32__", "0.842", "__0.273__"],
    ["EDGS [33]", "__27.15__", "__0.880__", "__0.091__", "__28.95__", "__0.923__", "0.094", "26.30", "**0.897**", "0.277"],
    ["Scaffold-GS [2]", "26.66", "0.865", "0.124", "28.79", "0.911", "0.106", "25.12", "0.811", "0.349"],
    ["Octree-GS [23]", "26.84", "0.873", "0.107", "28.85", "0.912", "0.101", "26.01", "0.836", "0.298"],
    ["**Ours**", "**28.56**", "**0.902**", "**0.072**", "**29.18**", "**0.936**", "**0.061**",
     "**27.13**", "__0.846__", "**0.231**"],
]
TAB1_NOTE = "注：粗体表示最优值，下划线表示次优值。"
ABL_ROWS = [
    ["Scaffold-GS [2]", "26.66", "0.865", "0.124", "28.79", "0.911", "0.106", "25.12", "0.811", "0.349"],
    ["w/o IE", "27.36", "0.882", "0.091", "28.97", "0.922", "0.078", "26.21", "0.835", "0.310"],
    ["w/o GD", "27.94", "__0.897__", "0.087", "29.04", "0.928", "0.072", "26.85", "__0.843__", "0.249"],
    ["w/o GI", "27.73", "0.894", "0.085", "29.01", "0.926", "0.069", "26.52", "0.839", "0.262"],
    ["w/o SP", "__28.03__", "0.896", "__0.077__", "__29.12__", "__0.931__", "__0.065__", "__26.88__", "0.841", "__0.242__"],
    ["**Ours (Full)**", "**28.56**", "**0.902**", "**0.072**", "**29.18**", "**0.936**", "**0.061**",
     "**27.13**", "**0.846**", "**0.231**"],
]
ABL_NOTE = "注：粗体表示最优值，下划线表示次优值。"

# --------------------------------------------------------------------------- experiments: comparison
CMP_TITLE = "实验结果与分析"
QUAL_H = "3.2.1　细结构恢复定性比较"
QUAL_P = ("图 3 给出了代表性方法在不同场景下的细结构恢复结果，红框对应区域的放大结果由黄色框给出。图 3(a) 中，"
          "基线方法对塔吊臂细杆件的恢复存在模糊或断裂，本文方法获得了更清晰、连续的结构；图 3(b) 中，多数基线未能完整恢复"
          "横跨道路的输电线，而本文方法较好地保持了其连续性。图 3(c) 中，本文方法进一步恢复了太阳能板的边界与内部栅格，"
          "表明其不仅适用于悬空细结构，对具有密集边缘的平面细结构同样有效。")
GLOBAL_H = "3.2.2　细结构恢复定量比较"
GLOBAL_CMP = (
    "表 1 给出了各方法在三个数据集上的整图指标，最优与次优结果分别以粗体和下划线标出。"
    "在 UrbanAerial3D 上，本文方法相对最强基线将 PSNR 和 SSIM 分别提高 1.41 dB 和 0.022，并将 LPIPS 降低 0.019；"
    "在 Mill-19 上，三项变化分别为 +0.23 dB、+0.013 和 -0.030。UrbanAerial3D 上的增益最为显著，说明本文方法对航拍场景中"
    "架空电线、灯杆等细结构具有较强的恢复能力。"
    "在 Waymo 上，本文方法取得最高 PSNR 和最低 LPIPS，相对对应的最强基线分别改善 0.81 dB 和 0.042，"
    "表明其在车载场景中仍能有效提升像素重建质量与感知质量。"
)
VOXEL_H = "3.2.3　体素尺度的影响"
VOXEL_P1 = ("为区分细结构恢复失败是由体素分辨率不足还是初始点云缺乏几何支撑所致，本文设置体素尺度对照实验。具体而言，"
            "在保持其余配置不变的条件下，图 4 比较了 Rubble 场景中采用标准体素尺度（$\\epsilon=10^{-3}$）与更细体素尺度"
            "（$\\epsilon=10^{-5}$）的 Scaffold-GS，并以相同标准体素尺度下的本文方法作为对照。四列依次为标准体素化的 "
            "Scaffold-GS、加密体素化的 Scaffold-GS、本文方法和真值。")
VOXEL_P2 = ("缩小体素尺度后，Scaffold-GS 在灌木等已被 SfM 点云覆盖的纹理区域呈现出更多细节（黄框），但横跨道路的架空电线"
            "仍然缺失（绿框），灯杆顶部的灯头也依然模糊（红框）。与此同时，体素尺度缩小两个数量级使模型存储由 168 MB 增至 "
            "334 MB，增加 98.8%，却未改善上述细结构的恢复。相比之下，本文方法在 $\\epsilon=10^{-3}$ 下仅将模型存储增至 "
            "182 MB，较 Scaffold-GS 增加 8.3%，即可恢复电线与灯头，其结果与真值更为一致。")
VOXEL_P3 = ("该对照表明，细结构恢复的主要制约因素并非体素分辨率，而是初始点云能否为目标结构提供几何支撑。缩小体素尺度只能增加 "
            "SfM 已覆盖区域内的锚点密度，无法在点云空缺处生成有效锚点，因而会引入较大的存储开销而不能恢复缺失结构。本文方法通过"
            "补充初始几何支撑，使锚点能够在 SfM 空缺处建立，从而以较小的额外存储开销实现细结构恢复。")
FIG4_CAP = "图4　不同体素尺度下的细结构恢复比较"
FIG4_EN = "Fig.4 Thin-structure recovery under different voxel sizes"
FIG4_PANELS = [("fig4-scaffoldgs-standard.png", "Scaffold-GS [2]\n(Standard)"),  # rendered from the PDFs (scale 1.5)
               ("fig4-scaffoldgs-dense.png", "Scaffold-GS [2]\n(Dense)"),
               ("fig4-ours.png", "Ours"),
               ("fig4-gt.png", "Ground-Truth")]
SENS_H = "3.2.5　超参数敏感性分析"
SENS_INTRO = ("本文在 Mill-19 上使用 LPIPS 分析几何离散度阈值 $\\tau_{\\text{disp}}$ 与观测充分度饱和阈值 "
              "$N_{\\text{conf}}$。前者控制致密化判定，后者共同调度尺度保持与几何离散度判定。由于 $D_v$ 由归一化的尺度离散度与"
              "方向离散度加权得到，本文在 $[0.03,0.45]$ 内由密到疏采样 $\\tau_{\\text{disp}}$，以覆盖从易触发到严格触发的判定范围；"
              "$N_{\\text{conf}}$ 则在 5～1000 次累计可见范围内近似对数采样，以比较快速调度与充分观测后的保守调度。")
SENS_CAP = "表2　Mill-19 上不同超参数取值对应的 LPIPS"
SENS_EN = "Table 2 LPIPS under different hyperparameters on Mill-19"
SENS_NOTE = "注：粗体表示最优值，下划线表示次优值。"
SENS_SUB_A = "(a) 几何离散度阈值"
SENS_SUB_B = "(b) 观测充分度饱和阈值"
SENS_TAU_ROWS = [
    ["$\\tau_{\\mathrm{disp}}$", "0.03", "0.05", "0.08", "0.12", "**0.18**", "__0.25__", "0.35", "0.45"],
    ["LPIPS ↓", "0.076", "0.072", "0.067", "0.064", "**0.061**", "__0.063__", "0.071", "0.089"],
]
SENS_N_ROWS = [
    ["$N_{\\mathrm{conf}}$", "5", "25", "50", "100", "**200**", "__400__", "700", "1000"],
    ["LPIPS ↓", "0.085", "0.083", "0.074", "0.066", "**0.061**", "__0.064__", "0.073", "0.087"],
]
SENS_P = ("表 2 给出了两个关键超参数在 Mill-19 上的敏感性结果。随着 $\\tau_{\\mathrm{disp}}$ 增大，LPIPS 先降低后升高，"
          "并在 $\\tau_{\\mathrm{disp}}=0.18$ 时取得最低值。较小的阈值容易将轻微几何扰动判定为结构冲突，引发冗余致密化；"
          "较大的阈值则会遗漏需要增加表示容量的锚点。$N_{\\mathrm{conf}}$ 呈现相似趋势，并在取 200 时取得最优结果。过小的取值"
          "会使观测不足的锚点过早参与几何判定，过大的取值则会延长尺度保持并推迟有效致密化。结果表明，本文方法在适中的参数范围内"
          "具有较稳定的性能。")

# --------------------------------------------------------------------------- 3.2.4 initial point clouds
INIT_TITLE = "3.2.4　初始点云对比"
INIT_P1 = (
    "为检验锚点初始化增强能否在 SfM 空缺处的悬空细结构上产生初始点，本文在 Rubble 场景上比较了 SfM、EDGS [33] 与本文的初始"
    "点云，并以一幅训练视图为例展示各步骤的中间结果，该视图中一根输电线斜跨道路，其背景为地面。EDGS 以 RoMa 稠密匹配在各参考"
    "视图上采样对应点，经两视图三角化后以其输出替代 SfM 点云。本文的初始点云则为 SfM 点云与补充点的并集。"
)
INIT_P3 = (
    "图 5 按锚点初始化增强的步骤给出了该视图上的中间结果。二维脊线检测（图 5(a)，青色为脊线，黄圈为亮斑）给出的候选像素中，"
    "除电线与电线杆外，还包括大量"
    "路面标线、路缘与列车边缘，这说明仅凭二维候选提取无法区分悬空结构与表面纹理。在按式（8）对齐的单目深度中（图 5(b)，红近蓝远，"
    "黑色为无效），电线与电线杆"
    "明显近于其后方的地面，而路面标线与路缘的深度与地面一致。图 5(c) 以该视图为参考视图，按式（6）逐一判定了全部候选。其中，"
    "多数候选虽取得了一致的多视图深度，但该深度不在背景之前，因而被悬空检测剔除（红色），这些候选几乎覆盖了全部路面标线与路缘；"
    "另有一部分候选因多视图支持不足或深度不唯一、与 SfM 点重合或未被其他参考视图印证而被剔除（橙色），它们主要分布在列车边缘等重复"
    "纹理上。最终被接受的候选（绿色）沿电线连续分布，并覆盖了部分电线杆。"
)
INIT_P4 = (
    "图 6 进一步从同一自由视角比较了三种初始点云。EDGS 的点数远多于补充点，但这些点集中在地面上，红框标出的电线区域内几乎"
    "为空（图 6(a)）。SfM 稀疏点在电线处完全缺失，电线杆上也只有零星的点（图 6(b)）。相比之下，本文的补充点在同一红框内沿电线连成"
    "带有下垂弧度的连续曲线，并覆盖了电线杆（图 6(c)，绿色标注见图 6(d)）。"
)
F049_FIG_CAP = "图5　Rubble 场景锚点初始化增强可视化"
F049_FIG_EN = "Fig.5 Visualization of anchor initialization enhancement on Rubble"
F049_FIG_PANELS = [("f049_ridge.png", "(a)"),
                   ("f049_mono_depth.png", "(b)"),
                   ("f049_decision.png", "(c)")]
INIT_FIG_CAP = "图6　同一自由视角下的初始点云对比"
INIT_FIG_EN = "Fig.6 Initial point clouds rendered from the same free viewpoint"
INIT_FIG_PANELS = [("edgs_init_custom_view_box.png", "(a)"),
                   ("colmap_init_custom_view_box.png", "(b)"),
                   ("ours_init_custom_view_box.png", "(c)"),
                   ("ours_init_custom_view_mark_box.png", "(d)")]

# --------------------------------------------------------------------------- 3.2.6 ablation
ABL_H = "3.2.6　消融实验"
ABL_CAP = "表3　所提方法的消融实验"
ABL_EN = "Table 3 Ablation study of the proposed method"
ABL_P1 = (
    "表 3 采用逐项移除的方式验证各组成部分，其中 IE、GD、GI 和 SP 分别表示锚点初始化增强、几何离散度引导的致密化、"
    "局部结构感知的几何继承和观测充分度引导的尺度保持。移除任一模块均使三个数据集上的指标下降，完整模型在全部指标上取得最优结果。"
    "其中，移除 IE 的综合退化最明显：在 UrbanAerial3D、Mill-19 和 Waymo 上，PSNR 分别降低 1.20、0.21 和 0.92 dB，LPIPS 分别增加 "
    "0.019、0.017 和 0.079，说明初始点云补充是恢复细结构的重要前提。"
)
ABL_P2 = (
    "移除 GD 后，三个数据集上的 LPIPS 分别增加 0.015、0.011 和 0.018，验证了几何分歧驱动致密化对局部细节的作用。移除 GI 的退化"
    "整体大于仅移除 SP，尤其在 Waymo 上 PSNR 降低 0.61 dB、LPIPS 增加 0.031；仅移除 SP 时对应变化为 0.25 dB 和 0.011。"
    "这表明父锚点局部尺度为新增锚点提供了有效的几何先验，而观测充分前的尺度保持能够进一步抑制背景主导的尺度漂移。上述结果说明，"
    "初始化增强、几何致密化和几何继承在锚点生命周期的不同阶段发挥互补作用。"
)

# --------------------------------------------------------------------------- conclusion
CONCLUSION = [
    "本文针对细结构恢复中的初始点云缺失与像素覆盖率低问题，在锚点式 3DGS 上提出一种基于跨层级几何一致性的恢复方法。该方法由细结构"
    "感知的锚点初始化增强、几何离散度引导的致密化与局部结构感知的几何继承三个部分构成：初始化增强在 SfM 空缺处补充细结构表示；几何"
    "致密化以锚点内部的几何分歧补充光度梯度；几何继承则在新增锚点的初始化过程中保持局部结构尺度。初始点云对比表明，补充点能够覆盖稠密匹配"
    "初始化遗漏的电线；在 UrbanAerial3D、Mill-19 和 Waymo 上，本文方法相对 Scaffold-GS 分别将 PSNR 提高 1.90、0.39 和 2.01 dB，"
    "并将 LPIPS 降低 0.052、0.045 和 0.118。敏感性与消融实验进一步验证了各模块的有效性及方法对参数的稳定性。",
    "本文方法仍存在一定的局限性。一方面，$N_{\\text{conf}}$ 与 $\\tau_{\\text{disp}}$ 需要按场景校准；另一方面，对于投影宽度"
    "小于约一个像素的细线，以及细线在全部视图对中均与核线近似平行的采集方式（例如航线与输电线走向一致），本文方法仍难以获得"
    "补充点。未来的工作将研究这些参数的自适应调度。",
]

# --------------------------------------------------------------------------- figure 2
FIG2_CAP = "图2　本文方法的算法流程"
FIG2_EN = "Fig.2 Overview of the proposed method"
FIG2_FILE = "fig2_overview.emf"        # vector, exported from _ov/lambda_fix.pptx slide 2 (paper/_ov/preview.py)
FIG2_WIDTH = 1.0                       # fraction of the page width
FIG2_NOTES = [
    "修改要求：左侧增加训练前阶段“多视图图像 + SfM 点云 → 细结构候选提取 → 多视图验证 → 悬空检测 → 点云去重 → 补充锚点”，以箭头接入锚点生命周期；",
    "循环改为“初始化增强（IE）→ 致密化（GD）→ 继承（GI：继承 + 保持）→ 观测充分后再次致密化”",
]

# --------------------------------------------------------------------------- references (complete list, journal style)
# Text above cites in the numbering of REFS (1-based). Entries in DROP_REFS are removed and the remaining ones are
# renumbered consecutively; restructure.py rewrites every citation in the body accordingly.
DROP_REFS = {8, 9, 10, 11, 12, 13, 26, 28}
_CVPR = "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)"
_ICCV = "Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)"
_ECCV = "Proceedings of the European Conference on Computer Vision (ECCV)"
_NIPS = "Advances in Neural Information Processing Systems (NeurIPS)"
_TOG = "ACM Transactions on Graphics (TOG)"
_TPAMI = "IEEE Transactions on Pattern Analysis and Machine Intelligence (TPAMI)"
_TVCG = "IEEE Transactions on Visualization and Computer Graphics (TVCG)"
REFS = [
    "KERBL B, KOPANAS G, LEIMKÜHLER T, et al. 3D Gaussian splatting for real-time radiance field rendering[J]. "
    f"{_TOG}, 2023, 42(4): 139:1-139:14.",
    f"LU T, YU M, XU L, et al. Scaffold-GS: Structured 3D Gaussians for view-adaptive rendering[C]//{_CVPR}, 2024: "
    "20654-20664.",
    "YU S, LIN Z, CUI W, et al. An automatic planning method for UAV power line inspection routes based on improved 3D "
    "Gaussian splatting[C]//Proceedings of the IEEE 7th International Conference on Civil Aviation Safety and "
    "Information Technology (ICCASIT), 2025: 431-434.",
    "YE Z, LI W, LIU S, et al. AbsGS: Recovering fine details in 3D Gaussian splatting[C]//Proceedings of the 32nd ACM "
    "International Conference on Multimedia (ACM MM), 2024: 1053-1061.",
    "LYU Y, CHENG K, KANG X, et al. ResGS: Residual densification of 3D Gaussian for efficient detail recovery[C]//"
    f"{_ICCV}, 2025: 28093-28102.",
    f"ZHANG J, ZHAN F, XU M, et al. FreGS: 3D Gaussian splatting with progressive frequency regularization[C]//{_CVPR}, "
    "2024: 21424-21433.",
    "MILDENHALL B, SRINIVASAN P P, TANCIK M, et al. NeRF: Representing scenes as neural radiance fields for view "
    f"synthesis[C]//{_ECCV}, 2020: 405-421.",
    "BARRON J T, MILDENHALL B, TANCIK M, et al. Mip-NeRF: A multiscale representation for anti-aliasing neural radiance "
    f"fields[C]//{_ICCV}, 2021: 5855-5864.",
    "BARRON J T, MILDENHALL B, VERBIN D, et al. Mip-NeRF 360: Unbounded anti-aliased neural radiance fields[C]//"
    f"{_CVPR}, 2022: 5470-5479.",
    f"BARRON J T, MILDENHALL B, VERBIN D, et al. Zip-NeRF: Anti-aliased grid-based neural radiance fields[C]//{_ICCV}, "
    "2023: 19697-19705.",
    "MÜLLER T, EVANS A, SCHIED C, et al. Instant neural graphics primitives with a multiresolution hash encoding[J]. "
    f"{_TOG}, 2022, 41(4): 102:1-102:15.",
    f"YU A, FRIDOVICH-KEIL S, TANCIK M, et al. Plenoxels: Radiance fields without neural networks[C]//{_CVPR}, 2022: "
    "5491-5500.",
    f"CHEN A, XU Z, GEIGER A, et al. TensoRF: Tensorial radiance fields[C]//{_ECCV}, 2022: 333-350.",
    f"YU Z, CHEN A, HUANG B, et al. Mip-Splatting: Alias-free 3D Gaussian splatting[C]//{_CVPR}, 2024: 19447-19456.",
    "HUANG B, YU Z, CHEN A, et al. 2D Gaussian splatting for geometrically accurate radiance fields[C]//Proceedings of "
    "the ACM SIGGRAPH Conference Papers (SIGGRAPH), 2024: 32:1-32:11.",
    "GUÉDON A, LEPETIT V. SuGaR: Surface-aligned Gaussian splatting for efficient 3D mesh reconstruction and "
    f"high-quality mesh rendering[C]//{_CVPR}, 2024: 5354-5363.",
    f"LI Y, LYU C, DI Y, et al. GeoGaussian: Geometry-aware Gaussian splatting for scene rendering[C]//{_ECCV}, 2024: "
    "441-457.",
    "CHENG K, LONG X, YANG K, et al. GaussianPro: 3D Gaussian splatting with progressive propagation[C]//Proceedings of "
    "the 41st International Conference on Machine Learning (ICML), 2024: 8123-8140.",
    "CHEN D, LI H, YE W, et al. PGSR: Planar-based Gaussian splatting for efficient and high-fidelity surface "
    f"reconstruction[J]. {_TVCG}, 2025, 31(9): 6100-6111.",
    "SCHÖNBERGER J L, FRAHM J M. Structure-from-motion revisited[C]//Proceedings of the IEEE Conference on Computer "
    "Vision and Pattern Recognition (CVPR), 2016: 4104-4113.",
    f"LIU S, YU Y, PAUTRAT R, et al. 3D line mapping revisited[C]//{_CVPR}, 2023: 21445-21455.",
    f"KHERADMAND S, REBAIN D, SHARMA G, et al. 3D Gaussian splatting as Markov chain Monte Carlo[C]//{_NIPS}, 2024, 37: "
    "80965-80986.",
    "REN K, JIANG L, LU T, et al. Octree-GS: Towards consistent real-time rendering with LOD-structured 3D Gaussians[J]. "
    f"{_TPAMI}, 2025: 1-15. DOI: 10.1109/TPAMI.2025.3568201.",
    f"ZHANG J, ZHAN F, SHAO L, et al. SOGS: Second-order anchor for advanced 3D Gaussian splatting[C]//{_CVPR}, 2025: "
    "11167-11176.",
    "GAO Y, GONG Y, LIU Y, et al. Proxy-GS: Unified occlusion priors for training and inference in structured 3D "
    f"Gaussian splatting[C]//{_CVPR}, 2026: 7330-7339.",
    "FANG G, WANG B. Mini-Splatting: Representing scenes with a constrained number of Gaussians[C]//"
    f"{_ECCV}, 2024: 165-181.",
    f"CHEN Y, WU Q, LIN W, et al. HAC++: Towards 100X compression of 3D Gaussian splatting[J]. {_TPAMI}, 2025, 47(11): "
    "10210-10226.",
    f"LIN J, LI Z, TANG X, et al. VastGaussian: Vast 3D Gaussians for large scene reconstruction[C]//{_CVPR}, 2024: "
    "5166-5175.",
    "TURKI H, RAMANAN D, SATYANARAYANAN M. Mega-NeRF: Scalable construction of large-scale NeRFs for virtual "
    f"fly-throughs[C]//{_CVPR}, 2022: 12912-12921.",
    "ZHANG R, ISOLA P, EFROS A A, et al. The unreasonable effectiveness of deep features as a perceptual metric[C]//"
    "Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2018: 586-595.",
    "WANG P, LIU L, CHEN N, et al. Vid2Curve: Simultaneous camera motion estimation and thin structure reconstruction "
    f"from an RGB video[J]. {_TOG}, 2020, 39(4): 38:1-38:12.",
    "WANG S, WANG Z, SHI M, et al. Slender3D: Curve-guided multi-view reconstruction of slender structures[C]//"
    "Proceedings of the AAAI Conference on Artificial Intelligence (AAAI), 2026, 40(12): 10118-10126.",
    f"KOTOVENKO D, GREBENKOVA O, OMMER B. EDGS: Eliminating densification for efficient convergence of 3DGS[C]//{_CVPR}, "
    "2026: 41065-41076.",
    "FRANGI A F, NIESSEN W J, VINCKEN K L, et al. Multiscale vessel enhancement filtering[C]//Proceedings of the "
    "International Conference on Medical Image Computing and Computer-Assisted Intervention (MICCAI), 1998: 130-137.",
    "STEGER C. An unbiased detector of curvilinear structures[J]. IEEE Transactions on Pattern Analysis and Machine "
    "Intelligence (TPAMI), 1998, 20(2): 113-125.",
    "COLLINS R T. A space-sweep approach to true multi-image matching[C]//Proceedings of the IEEE Computer Society "
    "Conference on Computer Vision and Pattern Recognition (CVPR), 1996: 358-363.",
    f"YANG L, KANG B, HUANG Z, et al. Depth Anything V2[C]//{_NIPS}, 2024, 37: 21875-21911.",
    "SUN P, KRETZSCHMAR H, DOTIWALLA X, et al. Scalability in perception for autonomous driving: Waymo open dataset[C]//"
    f"{_CVPR}, 2020: 2446-2454.",
]
