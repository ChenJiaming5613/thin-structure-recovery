# 面向悬空细结构的初始点补充（方法章节草稿）

> **编写说明（不属于投稿正文）**
> 1. 本文档描述 `point_cloud_init/` 的当前实现（仓库提交 `22deb5a`），公式与默认参数均与代码逐项核对；正文中的代码文件仅在本说明与附录中出现。
> 2. 记号与主稿 `paper_zh.md` 保持一致：$P$ 为 COLMAP 稀疏点云，$\epsilon$ 为 Scaffold-GS 的初始体素尺度，式（1）指主稿中的体素化公式。本章可作为主稿第 3 节中的一个子节（例如“3.2 细结构感知的初始点补充”），届时公式编号需整体顺延。
> 3. 标注【待定】的设计选择尚未由训练实验确认，定稿前需根据消融结果改写。
> 4. 参考文献条目定稿前需逐条核对卷期页码。

---

## 1 动机

Scaffold-GS[16] 以 COLMAP[15] 稀疏点云 $P$ 的体素化结果作为初始锚点（主稿式（1）），并且只在已有锚点所解码的神经高斯附近生成新锚点。因此，若某一场景区域在 $P$ 中没有任何点，该区域在训练全程都缺少锚点生长的起点。悬空细结构（输电线、灯带、塔吊臂架、灯杆等）恰好属于这一情形：其投影宽度通常只有 1–3 个像素，背景多为天空或远处表面，缺乏可重复检测的角点；沿结构方向的局部外观几乎不变，描述子存在孔径歧义；平行导线、重复灯泡等又会造成大量错误匹配。基于关键点检测与描述子匹配的 SfM 流程因而在这些区域几乎不产生三维点。

上述失效发生在对应关系建立阶段，而非三角化阶段。只要相机位姿可靠（背景区域纹理充分时，COLMAP 位姿通常是可靠的），细结构的三维位置仍可由多视图几何确定。基于这一观察，本文在训练之前引入一个**免训练的初始点补充**步骤：在固定 COLMAP 位姿的前提下，以细结构的二维几何响应代替外观描述子，通过沿视线的多视图深度扫描恢复细结构上的三维点，并只保留位于已知表面前方、原始点云尚未覆盖的点，作为对 $P$ 的补充。

由于 Scaffold-GS 的锚点特征初始化为零、颜色由多层感知机解码，初始化阶段仅使用点的空间位置，因此补充点只需提供位置；同时，锚点位置与偏移在训练中均可优化，补充点只需落在真实结构的若干个体素尺度 $\epsilon$ 以内即可发挥作用。这使得问题从“精确重建细结构”放宽为“在细结构附近提供可靠的锚点种子”。

## 2 方法概述

给定 $M$ 张去畸变图像 $\{I_j\}_{j=1}^{M}$、对应的相机内参 $K$ 与外参 $(R_j,t_j)$，以及 COLMAP 稀疏点云 $P$，本方法输出补充点集 $P_{\text{thin}}$，并以 $P'=P\cup P_{\text{thin}}$ 替代 $P$ 作为 Scaffold-GS 的输入。流程包括四个阶段：

1. **细结构二维候选检测**（第 3 节）：在每幅图像中检测细线与小尺度亮斑，构造距离变换图与切线场；
2. **固定位姿多视图深度扫描**（第 4 节）：对每个候选像素沿视线采样深度，统计邻近视图中投影落在同类候选上的视图数，并剔除几何退化与被遮挡的视图；
3. **悬空判据**（第 5 节）：由原始点云（以及可选的对齐单目深度）构造背景深度，仅接受最优深度位于背景表面前方的点；
4. **跨参考帧互证与新颖性筛选**（第 6 节）：保留被其他参考帧印证、且远离原始点云的点，体素降采样后与 $P$ 合并。

**相机模型。** 记相机中心 $C_j=-R_j^{\top}t_j$。三维点 $X$ 在视图 $j$ 中的投影与深度为

$$
\begin{bmatrix} u \\ v \\ 1 \end{bmatrix} z_j(X) = K\left(R_j X + t_j\right),
\qquad \pi_j(X)=(u,v).
\tag{2}
$$

对参考视图 $r$ 中整数像素索引 $p=(p_x,p_y)$，取像素中心 $\tilde p=(p_x+0.5,\,p_y+0.5,\,1)^{\top}$（COLMAP 约定），定义按相机 $z$ 轴归一化的视线方向与深度参数化的射线：

$$
\mathbf{r}_r(p)=R_r^{\top}K^{-1}\tilde p,
\qquad
X_r(p,d)=C_r+d\,\mathbf{r}_r(p),
\tag{3}
$$

其中 $d$ 即参考视图下的相机 $z$ 深度。若输入图像为降采样版本，$K$ 按图像实际尺寸与 COLMAP 记录尺寸之比缩放。

## 3 细结构二维候选检测

### 3.1 多尺度脊线响应

对灰度图 $I$（取 RGB 均值并归一化到 $[0,1]$），在尺度 $\sigma$ 下计算尺度归一化 Hessian 矩阵

$$
\mathcal{H}_\sigma(x)=\sigma^{2}
\begin{bmatrix}
I_{xx}^{\sigma} & I_{xy}^{\sigma}\\
I_{xy}^{\sigma} & I_{yy}^{\sigma}
\end{bmatrix},
\tag{4}
$$

其中 $I_{ab}^{\sigma}$ 为高斯导数滤波结果。记其两个特征值按绝对值排序为 $|\lambda_a|\le|\lambda_b|$：对于一条细线，$\lambda_b$ 对应横跨线的方向、幅值较大，$\lambda_a$ 对应沿线方向、接近零。定义各向异性因子与亮、暗两类脊线响应：

$$
A_\sigma=\exp\!\left(-\frac{(\lambda_a/\lambda_b)^{2}}{2\beta^{2}}\right),
\tag{5}
$$

$$
R^{+}_\sigma=
\begin{cases}
-\lambda_b A_\sigma, & \lambda_b<0\\
0, & \text{otherwise}
\end{cases},
\qquad
R^{-}_\sigma=
\begin{cases}
\lambda_b A_\sigma, & \lambda_b>0\\
0, & \text{otherwise}
\end{cases},
\tag{6}
$$

分别对应比两侧更亮的细线（如反光金属）与更暗的细线（如天空或浅色墙面前的导线）。多尺度响应取各尺度最大值 $R^{\pm}=\max_{\sigma\in\Sigma}R^{\pm}_\sigma$，并记录取得最大值的尺度上的线切线方向 $\theta^{\pm}(x)$。该响应形式属于经典的 Hessian 曲线结构检测[1–3]。

### 3.2 方向一致性线积分

单尺度 Hessian 响应对 1 像素宽、对比度起伏的细线常呈断续状态，且在树叶等纹理区域产生大量方向杂乱的伪响应。为此，在 $N_\phi$ 个离散方向 $\phi_k=k\pi/N_\phi$ 上，仅累积局部切线与该方向一致的响应：

$$
E(x)=\max_{k}\;\Big(G_{L,\phi_k} * \big[R\cdot\mathbb{1}\left(\Delta(\theta,\phi_k)<\delta\right)\big]\Big)(x),
\qquad
\Delta(\theta,\phi)=\tfrac12\left|\arg e^{\,2\mathrm{i}(\theta-\phi)}\right|,
\tag{7}
$$

其中 $G_{L,\phi}$ 为长度 $L$、沿 $\phi$ 方向、横向为窄高斯剖面的归一化线核，$\Delta(\cdot,\cdot)$ 为以 $\pi$ 为周期的角度差。该操作沿直线段对“方向一致”的证据求平均，从而连接断续的细线并抑制方向随机的纹理。为避免把邻近细线的响应扩散到背景，最终响应只在原始响应足够强的像素上保留：$E\leftarrow E\cdot\mathbb{1}\left(R>Q_{q_s}(R)\right)$，其中 $Q_q(\cdot)$ 表示全图第 $q$ 百分位数。

### 3.3 二值化与形状筛选

对 $E$ 采用滞后阈值[4]：以 $Q_{q_h}(E)$ 为强阈值、$Q_{q_l}(E)$ 为弱阈值，保留与强响应连通的弱响应像素。随后对每个八连通分量，计算其像素坐标协方差矩阵的特征值 $\mu_1\ge\mu_2$，仅保留长度 $\ell=4\sqrt{\mu_1}\ge\ell_{\min}$ 且细长度 $\sqrt{\mu_1/\mu_2}\ge e_{\min}$ 的分量。亮、暗两类结果合并为线掩码 $\mathcal{L}$。

### 3.4 小尺度亮斑

灯泡、桁架节点等目标表现为孤立的小亮斑，而非连续线条。采用 Hessian 两特征值同为负时的几何平均作为亮斑响应[5]：

$$
B(x)=\max_{\sigma\in\Sigma_b}\;
\begin{cases}
\sqrt{\lambda_{1,\sigma}\lambda_{2,\sigma}}, & \lambda_{1,\sigma}<0,\ \lambda_{2,\sigma}<0\\
0, & \text{otherwise}
\end{cases},
\tag{8}
$$

在 $7\times7$ 邻域内做非极大值抑制，保留 $B>Q_{q_b}(B)$ 的峰值，并剔除位于大面积高亮区域内部的峰值，得到亮斑集合 $\mathcal{B}$。

### 3.5 几何查询表

二维检测不区分语义，因而会同时检出表面边缘、纹理等非目标结构；这些误检交由后续的多视图几何一致性处理。为支持后续投票，对每幅图像 $j$ 预计算：

- 线距离变换 $D^{L}_j(x)$：像素 $x$ 到 $\mathcal{L}_j$ 的欧氏距离；
- 亮斑距离变换 $D^{B}_j(x)$：像素 $x$ 到 $\mathcal{B}_j$ 的欧氏距离；
- 切线场 $\Theta_j(x)$：距离 $x$ 最近的线像素处的切线方向。

候选像素集合 $\mathcal{C}_j$ 由 $\mathcal{L}_j$ 中随机采样的至多 $N_c$ 个像素与 $\mathcal{B}_j$ 的全部亮斑组成，并记录每个候选的类型 $c\in\{L,B\}$。

## 4 固定位姿多视图深度扫描

### 4.1 邻近视图与深度范围

对参考视图 $r$，记 $\bar z_r$ 为其可见 COLMAP 点深度的中位数。邻近视图集合 $\mathcal{N}(r)$ 由满足基线 $\|C_j-C_r\|\ge b_{\min}\bar z_r$、光轴夹角不超过 $\psi_{\max}$ 的视图中基线最短的 $N_v$ 个组成。深度搜索区间取

$$
d\in\left[\max\!\left(s_n\,z_r^{(2)},\,10^{-2}\right),\;s_f\,z_r^{(98)}\right],
\tag{9}
$$

其中 $z_r^{(q)}$ 为可见 COLMAP 点深度的第 $q$ 百分位数，并在逆深度上均匀采样 $N_d$ 个深度 $\{d_k\}$，以使采样密度与图像空间视差近似均匀。

### 4.2 逐视图投票

对候选像素 $p\in\mathcal{C}_r$（类型为 $c$）的第 $k$ 个深度样本 $X_k=X_r(p,d_k)$，在每个邻近视图 $j\in\mathcal{N}(r)$ 中计算投影 $\pi_j(X_k)$ 及其到同类候选的距离

$$
\rho_{jk}=D^{c}_j\!\left(\pi_j(X_k)\right).
\tag{10}
$$

当投影落在同类二维候选的 $\tau$ 像素以内时，视图 $j$ 被视为支持该深度。与平面扫描立体匹配[6]以光度一致性为代价不同，此处以二维细结构的距离变换作为代价，因而不依赖细结构及其背景的外观，也不需要显式建立对应关系；以投影到二维曲线的距离度量三维曲线的多视图一致性，与 Vid2Curve[7]、Slender3D[8] 中的曲线对齐损失具有相同的几何含义。命中深度在几何上等价于参考像素的核线与邻近视图中细线的交点。

**退化视图剔除。** 线候选的深度只有在核线与二维细线相交时才可确定；当细线在邻近视图中与核线近似平行时，沿核线的任意位置都可能命中，该视图不提供深度约束[9]。对线候选，以微小深度扰动估计投影点在视图 $j$ 中的核线方向

$$
\mathbf{e}_{jk}=\pi_j\!\left(X_r(p,(1+\varsigma)d_k)\right)-\pi_j\!\left(X_r(p,d_k)\right),
\tag{11}
$$

并在 $\Delta\!\left(\angle\mathbf{e}_{jk},\,\Theta_j(\pi_j(X_k))\right)<\gamma$ 时将视图 $j$ 视为退化。亮斑候选为点状特征，不进行该检验。

**遮挡视图剔除。** 若样本位于视图 $j$ 中已知背景表面之后，则其在视图 $j$ 中应被遮挡，投影命中只能来自前景结构的偶然对齐。记 $Z^{\text{bg}}_j(\cdot)$ 为第 5 节定义的背景深度，当 $z_j(X_k)>\kappa\,Z^{\text{bg}}_j(\pi_j(X_k))$ 时将视图 $j$ 视为无效。

综合上述条件，定义有效指示 $v_{jk}$（投影在图像内且深度为正、非退化、非遮挡）与命中指示 $h_{jk}=v_{jk}\,\mathbb{1}(\rho_{jk}\le\tau)$，并统计

$$
S_k=\sum_{j\in\mathcal{N}(r)}h_{jk},
\qquad
N_k=\sum_{j\in\mathcal{N}(r)}v_{jk},
\qquad
\bar\rho_k=\frac{\sum_{j}v_{jk}\min(\rho_{jk},2\tau)}{\max(N_k,1)}.
\tag{12}
$$

### 4.3 深度选择、接受与细化

以支持视图数为主、平均距离为次进行深度选择：

$$
k^{*}=\arg\max_{k}\left(S_k-\eta\,\bar\rho_k\right),
\tag{13}
$$

其中 $\eta$ 取极小值，仅用于打破支持数相同的情形。候选像素 $p$ 被接受当且仅当同时满足：

$$
S_{k^*}\ge n_{\min},
\qquad
S_{k^*}\ge \omega\,N_{k^*},
\qquad
\max_{|k-k^*|>w}S_k\le S_{k^*}-m.
\tag{14}
$$

三个条件分别要求：足够多的视图支持；在能够观测到该深度的有效视图中，支持者占多数；最优深度沿视线是唯一的峰值。第三个条件用于排除重复结构（平行导线、相同灯泡）沿核线产生的多重解。通过检验后，在 $d_{k^*-1}$ 与 $d_{k^*+1}$ 之间按逆深度均匀取 $N_r$ 个深度重新投票，得到细化深度 $d^{*}$ 及对应三维点 $X^{*}=X_r(p,d^{*})$。最后要求支持视图中的最大三角化夹角

$$
\alpha(X^{*})=\max_{j:\,h_j=1}\angle\left(X^{*}-C_r,\;X^{*}-C_j\right)\ge\alpha_{\min},
\tag{15}
$$

以排除基线过小导致深度不确定的点。

## 5 悬空判据

多视图一致性只保证点被多个视角共同解释，并不区分悬空结构与已有表面上的纹理边缘。后者在原始点云中通常已有邻近点，补充它们既不能填补锚点空缺，又可能因与表面点的小幅偏差而引入冗余。本文利用悬空结构的一个基本几何特征：**其深度显著小于同一视线方向上背后表面的深度**；而表面边缘的深度与背景深度近似相等。

### 5.1 背景深度

将原始点云 $P$ 投影到视图 $j$，按 $b\times b$ 像素划分图块。对每个图块 $\mathcal{T}$，取落入其中的点深度的第 $q_t$ 百分位数作为该图块的背景深度：

$$
Z^{\text{tile}}_j(\mathcal{T})=
\begin{cases}
Q_{q_t}\!\left(\{z_j(X):X\in P,\ \pi_j(X)\in\mathcal{T}\}\right), & \left|\{\cdot\}\right|\ge n_t\\
+\infty, & \text{otherwise}
\end{cases}.
\tag{16}
$$

采用较低的百分位数而非最小值，是为了避免少量位于真实表面之前的错误 SfM 点压缩其前方的自由空间；点数不足的图块（天空、未重建区域）视为背景未知。

**单目深度补全【待定】。** 弱纹理表面（墙面、门框等）在 $P$ 中往往没有点，式（16）在这些区域退化为 $+\infty$，悬空判据随之失效。为此，可选地使用单目深度估计网络[10]预测每幅图像的相对视差 $\delta_j(x)$，并以该视图中位于最前表面的可见 COLMAP 点为样本，拟合视差空间的仿射变换[11]：

$$
\frac{1}{z_j(X)}\approx a_j\,\delta_j\!\left(\pi_j(X)\right)+b_j .
\tag{17}
$$

拟合采用迭代重加权最小二乘，残差取相对逆深度误差，权重为 Huber 函数[12]。以相对深度误差的中位数 $e_j$ 评价拟合质量，$e_j>e_{\max}$ 的视图不使用单目深度。对齐深度为 $\hat Z_j=1/(a_j\delta_j+b_j)$（当 $a_j\delta_j+b_j\le10^{-4}$ 时记为 $+\infty$）。由于单目网络往往为灯杆、树干等细物体预测其自身深度，而此处需要的是其背后的表面深度，对 $\hat Z_j$ 施加半径为 $r_d$ 的最大值滤波得到 $\hat Z'_j$。最终背景深度为

$$
Z^{\text{bg}}_j(x)=
\begin{cases}
Z^{\text{tile}}_j(x), & Z^{\text{tile}}_j(x)<+\infty\\
\hat Z'_j(x), & \text{otherwise}
\end{cases}.
\tag{18}
$$

### 5.2 拒绝式判据

对参考视图 $r$ 中经第 4 节接受的点，若其细化深度不在背景前方，即

$$
d^{*}>\rho_f\,Z^{\text{bg}}_r(p),
\tag{19}
$$

则丢弃该点；背景未知（$Z^{\text{bg}}_r(p)=+\infty$）时不施加约束。此外，若候选像素前方可供搜索的深度样本少于 $n_f$ 个，该候选直接跳过。

需要强调的是，深度扫描始终在完整区间（式（9））上进行，判据只作用于扫描得到的最优深度。另一种直观做法是把扫描上限截断为 $\rho_f Z^{\text{bg}}_r(p)$，但对于真实深度恰好位于表面上的候选（如车身边缘），截断会迫使扫描在表面前方寻找次优解；一旦次优解偶然满足式（14），便会生成悬浮于表面前方、且远离原始点云的错误点。拒绝式判据只回答“最优解是否悬空”，不会把非悬空候选改造成悬空点。

## 6 跨参考帧互证与新颖性筛选

每幅图像轮流作为参考视图独立执行第 4、5 节，得到原始点集 $\{X_i\}$，其中每个点记录其参考视图 $r_i$ 与深度 $d^{*}_i$。记像素足迹 $\varphi_i=d^{*}_i/f_x$ 为一个像素在该深度上对应的世界尺寸，以使后续阈值与场景尺度无关。

**跨参考帧互证。** 仅当以 $X_i$ 为中心、半径 $\lambda_s\varphi_i$ 的邻域内包含来自至少 $n_r$ 个其他参考视图的点时，保留 $X_i$：

$$
\left|\left\{r_{i'}:\ \|X_{i'}-X_i\|\le\lambda_s\varphi_i,\ r_{i'}\ne r_i\right\}\right|\ge n_r .
\tag{20}
$$

**新颖性筛选。** 仅保留与原始点云距离足够远的点：

$$
\min_{X\in P}\|X_i-X\|>\lambda_f\varphi_i .
\tag{21}
$$

该条件保证补充点只出现在原始点云的空缺处，避免在已有锚点的区域重复加点。

**体素降采样与合并。** 对保留的点以体素尺寸 $\epsilon_v$（取与 Scaffold-GS 初始体素尺度 $\epsilon$ 相同的量级）求体素内均值，得到 $P_{\text{thin}}$，最终以 $P'=P\cup P_{\text{thin}}$ 代替主稿式（1）中的 $P$。补充点的颜色由参考视图采样，仅用于可视化，不参与 Scaffold-GS 的初始化。

## 7 算法流程

**算法 1** 悬空细结构初始点补充

**输入：** 图像 $\{I_j\}$，内参 $K$，位姿 $\{(R_j,t_j)\}$，稀疏点云 $P$
**输出：** 合并点云 $P'$

1. 对每幅图像 $j$：由式（4）–（8）检测线掩码 $\mathcal{L}_j$ 与亮斑 $\mathcal{B}_j$，计算 $D^{L}_j$、$D^{B}_j$、$\Theta_j$，采样候选 $\mathcal{C}_j$；由式（16）–（18）构造背景深度 $Z^{\text{bg}}_j$。
2. 对每个参考视图 $r$：选择 $\mathcal{N}(r)$ 与深度区间（式（9））；对每个候选 $p\in\mathcal{C}_r$：
   1. 对全部深度样本按式（10）–（12）投票，按式（13）选择 $k^{*}$；
   2. 若式（14）不满足，跳过；否则细化得到 $d^{*}$ 与 $X^{*}$；
   3. 若式（15）不满足或式（19）成立，跳过；否则记录 $(X^{*},r,d^{*})$。
3. 按式（20）保留被其他参考视图印证的点，按式（21）保留远离 $P$ 的点。
4. 以体素 $\epsilon_v$ 降采样得到 $P_{\text{thin}}$，输出 $P'=P\cup P_{\text{thin}}$。

**计算复杂度。** 主要开销为第 2 步的投影与查表，与 $\sum_r|\mathcal{C}_r|\cdot N_d\cdot N_v$ 成正比，各参考视图之间相互独立，可并行。

## 8 实现细节

全部参数如表 1 所示；除体素尺寸外，所有场景使用同一组参数。几何阈值以像素或像素足迹表达，因而与场景的绝对尺度无关。

**表 1.** 默认参数

| 模块 | 符号 | 含义 | 取值 |
|---|---|---|---|
| 脊线 | $\Sigma$ | Hessian 尺度 | $\{0.8,1.2,1.8\}$ 像素 |
| | $\beta$ | 各向异性参数 | 0.5 |
| | $L,\ N_\phi,\ \delta$ | 线积分长度、方向数、方向容差 | 21 像素，16，12° |
| | $q_s$ | 原始响应支撑百分位 | 85 |
| | $q_h,\ q_l$ | 滞后阈值百分位 | 99，96.5 |
| | $\ell_{\min},\ e_{\min}$ | 最小长度、最小细长度 | 25 像素，4 |
| 亮斑 | $\Sigma_b,\ q_b$ | 尺度、阈值百分位 | $\{1.2,1.8,2.5\}$ 像素，99.8 |
| 候选 | $N_c$ | 每幅图像线候选上限 | 3000 |
| 扫描 | $N_v$ | 邻近视图数 | 16 |
| | $b_{\min},\ \psi_{\max}$ | 最小相对基线、最大光轴夹角 | 0.03，60° |
| | $s_n,\ s_f$ | 深度区间系数 | 0.3，1.2 |
| | $N_d,\ N_r$ | 扫描与细化样本数 | 192，9 |
| | $\tau$ | 命中容差 | 2 像素 |
| | $\gamma,\ \varsigma$ | 退化角阈值、核线扰动 | 15°，0.002 |
| | $\kappa$ | 遮挡判定系数 | 1.05 |
| 接受 | $n_{\min},\ \omega$ | 最少支持视图、支持比例 | 5，0.6 |
| | $w,\ m$ | 唯一性窗口、唯一性裕度 | 6 个样本，2 票 |
| | $\alpha_{\min}$ | 最小三角化夹角 | 2° |
| 悬空 | $b,\ q_t,\ n_t$ | 图块尺寸、深度百分位、最少点数 | 8 像素，20，3 |
| | $\rho_f,\ n_f$ | 前方比例、最少前方样本 | 0.9，8 |
| 单目【待定】 | — | 单目深度网络 | Depth Anything V2 Small[10] |
| | $e_{\max}$ | 对齐误差上限 | 0.15 |
| | $r_d$ | 最大值滤波半径 | 8 像素 |
| 后处理 | $\lambda_s,\ n_r$ | 互证半径（足迹倍数）、最少其他参考视图 | 4，2 |
| | $\lambda_f$ | 新颖性距离（足迹倍数） | 8 |
| | $\epsilon_v$ | 体素尺寸 | 与 Scaffold-GS 的 $\epsilon$ 一致 |

全部计算在 CPU 上完成。以 Tanks and Temples 的 Truck 场景为例（979×546 分辨率），40 幅图像的二维检测约 65 s、深度扫描约 95 s；Mill-19 Rubble 子集（198 幅、1147×860）全流程约 22 min，其中单目深度推理约 2.3 min。

## 9 与已有方法的关系

本方法的各组成部分均建立在成熟技术之上：Hessian 曲线结构检测[1–3]、尺度空间亮斑检测[5]、滞后阈值[4]、平面扫描式多视图深度搜索[6]、以二值剪影/掩码代替光度一致性的空间雕刻思想[13]、曲线重投影对齐[7,8]、线三角化退化分析[9]、单目视差的仿射对齐[11]，以及多视图立体中的几何一致性检验[14]；相机位姿与稀疏点云直接取自 COLMAP[15]。本文的工作在于针对“锚点式 3DGS 在悬空细结构处缺少初始锚点”这一具体问题，将上述技术组织为一个固定位姿、免训练、即插即用的补点流程，并给出三处面向该问题的设计：以细结构距离变换代替外观代价，从而在无纹理背景下工作；在投票中显式剔除细线与核线平行的退化视图；以拒绝式悬空判据与新颖性筛选，使补充点集中于原始点云的空缺处。

与 LIMAP[9] 相比，本方法不依赖线段匹配，可处理下垂的曲线结构，并且只对检测到的细结构补点；与 Vid2Curve[7] 和 Slender3D[8] 相比，本方法面向场景级数据，直接复用 COLMAP 位姿而不重新估计，也不要求输入为只含细结构的前景掩码。

## 10 局限性

1. **二维检测决定召回上限。** 投影宽度小于约 1 像素、或与背景对比度过低的细线（如树冠前的导线）难以被二维滤波检出；固定上限的随机采样（$N_c$）也会降低长细线上的采样密度。
2. **成像几何限制。** 若全部视图对中细线均与核线近似平行（例如航线与输电线走向一致），深度在原理上不可确定，需要补充交叉或斜向视角。
3. **悬空判据依赖背景深度。** 背景深度来自稀疏点云或单目估计，在近处前景遮挡（如挂载灯带的灯杆）附近可能偏浅，导致少量真实悬空点被拒绝。
4. **与召回目标的权衡【待定】。** 悬空判据与单目补全以召回为代价提高“悬空”纯度；而弱纹理表面上的补充点同样可能为 Scaffold-GS 提供有益的锚点。两者的取舍需以细结构区域的渲染质量为准，通过消融实验确定。

---

## 附录 B　初步观察（编辑参考，不属于投稿正文）

以下数据为 Truck 场景第 1–40 帧上的**代理指标**，用于说明各设计的作用方向，**不能替代训练后的渲染指标**。“灯带召回”为第 11 帧灯带区域检测到的线像素中，3 像素内存在补充点投影的比例；“下半幅点数”为第 11 帧图像下半部分（车身与地面）可见的补充点数。

| 配置 | 补充点数 | 灯带召回 | 第 11 帧下半幅 | 第 20 帧下半幅 |
|---|---|---|---|---|
| 无悬空判据 | 11,184 | 85.4% | 1,479 | 1,518 |
| 截断式悬空判据（$Z^{\text{bg}}$ 仅用稀疏点） | 8,467 | 85.8% | 1,148 | 741 |
| 拒绝式悬空判据（$Z^{\text{bg}}$ 仅用稀疏点） | 6,971 | 82.5% | 356 | 490 |
| 拒绝式 + 单目补全（当前默认） | 5,362 | 79.8% | 308 | 454 |

截断式判据相对基线新增的 1,704 个点中，有相当部分位于车身表面前方；拒绝式判据新增的 451 个点中不存在位于表面上的点，与第 5.2 节的分析一致。单目补全主要移除墙面与门框边缘上的点。建议在实验章节中以“无判据 / 拒绝式 / 拒绝式 + 单目补全”三组初始点云分别训练 Scaffold-GS，并报告细结构掩码区域内的 PSNR、SSIM、LPIPS，以确定最终配置。

代码对应关系：二维检测 `detect_2d.py`；扫描、悬空判据与后处理 `triangulate.py`；单目深度 `mono_depth.py`；评估与可视化 `diagnose.py`、`compare_sets.py`、`preview.py`、`depth_to_png.py`。

---

## 参考文献

1. FRANGI A F, NIESSEN W J, VINCKEN K L, et al. Multiscale vessel enhancement filtering. In: *Medical Image Computing and Computer-Assisted Intervention*, 1998: 130–137.
2. SATO Y, NAKAJIMA S, SHIRAGA N, et al. Three-dimensional multi-scale line filter for segmentation and visualization of curvilinear structures in medical images. *Medical Image Analysis*, 1998, 2(2): 143–168.
3. STEGER C. An unbiased detector of curvilinear structures. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 1998, 20(2): 113–125.
4. CANNY J. A computational approach to edge detection. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 1986, 8(6): 679–698.
5. LINDEBERG T. Feature detection with automatic scale selection. *International Journal of Computer Vision*, 1998, 30(2): 79–116.
6. COLLINS R T. A space-sweep approach to true multi-image matching. In: *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition*, 1996: 358–363.
7. WANG P, LIU L, CHEN N, et al. Vid2Curve: Simultaneous camera motion estimation and thin structure reconstruction from an RGB video. *ACM Transactions on Graphics*, 2020, 39(4): 132.
8. WANG S, WANG Z, SHI M, et al. Slender3D: Curve-guided multi-view reconstruction of slender structures. In: *Proceedings of the AAAI Conference on Artificial Intelligence*, 2026, 40(12): 10118–10126.
9. LIU S, YU Y, PAUTRAT R, et al. 3D line mapping revisited. In: *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 2023.
10. YANG L, KANG B, HUANG Z, et al. Depth Anything V2. In: *Advances in Neural Information Processing Systems*, 2024.
11. RANFTL R, LASINGER K, HAFNER D, et al. Towards robust monocular depth estimation: Mixing datasets for zero-shot cross-dataset transfer. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 2022, 44(3): 1623–1637.
12. HUBER P J. Robust estimation of a location parameter. *The Annals of Mathematical Statistics*, 1964, 35(1): 73–101.
13. KUTULAKOS K N, SEITZ S M. A theory of shape by space carving. *International Journal of Computer Vision*, 2000, 38(3): 199–218.
14. SCHÖNBERGER J L, ZHENG E, FRAHM J M, et al. Pixelwise view selection for unstructured multi-view stereo. In: *European Conference on Computer Vision*, 2016: 501–518.
15. SCHÖNBERGER J L, FRAHM J M. Structure-from-motion revisited. In: *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition*, 2016: 4104–4113.
16. LU T, YU M, XU L, et al. Scaffold-GS: Structured 3D Gaussians for view-adaptive rendering. In: *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 2024: 20654–20664.
