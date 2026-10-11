# 第1期：彩色相机宽带星云后期（PixInsight 进阶教程，BV14LthzDEyh）

素材：IC 434 马头星云 + 火焰星云，ZWO 2600MC（彩机、无滤镜），72ED 折射镜，一晚积分。起点是 WBPP 输出的 `integration_autocrop`（线性主图）。
原始材料：`transcript.txt`（Whisper 转写，带时间戳）、`sheets/`（每 10 s 截图）、`keyframes/`（读参数用的原分辨率帧）。
对应配方：`astroflow/pipeline.py` → `osc_broadband_nebula`。

## 线性阶段

| 顺序 | 操作 | 参数 / 做法 | 时间 | 判断标准 |
|---|---|---|---|---|
| 0 | STF 查看 | **关掉锁链**（unlinked）自动拉伸；Shift+核弹做强拉伸看梯度 | 00:59–01:28 | 只是预览，不改数据 |
| 1 | 背景提取 | **GC（GradientCorrection）默认参数**；可选 ABE/DBE | 01:41–02:20 | 提取的背景模型应与观察到的梯度一致（本例左暗右亮的横向梯度），**不能含星云结构** |
| 2a | 色彩校准（手动 BNCC） | ① 背景选区：满屏星云时用 SetiAstro **FindBackground** 脚本自动找一小块背景（03:13）；② **BN**：参考区=背景选区，上限取选区内 RGB 最大值稍上（0.019→**0.02**），目标背景 0.001；③ **CC**：背景参考同一选区，上限 ~**0.001**（BN 后背景已≈0.001）；白参考=整幅图的星点（Structure Detection 开），下限取一颗较暗星的亮度（**0.01**），上限 0.9 | 02:43–05:33 | 背景中性灰、星点以白为基准、星云颜色符合常理（马头：棕+粉） |
| 2b | 色彩校准（自动 SPCC，**优先**） | 先 ImageSolver（NINA/ASIAIR 的 FITS 自带坐标/时间/像元 3.76µm/焦距，不用搜天体库）；SPCC：Narrowband 不勾，白参考 **Average Spiral Galaxy**，QE **Ideal QE curve**，滤镜 **Sony Color Sensor R/G/B-UVIRcut**（ZWO/QHY/ToupTek 彩色冷冻相机都用它；改机 5100 等另选），Catalog **Gaia DR3/SP**，背景参考选背景小区域 | 06:10–10:10 | 白平衡拟合图上点都落在拟合线上=准；结果比 BNCC 更准（BNCC 有一层黄雾） |
| 3 | 反卷积 BXT | **默认参数**；**BXT 之前不做任何降噪**（RC 官方建议，修正了入门篇的顺序） | 11:30–13:16 | 星点修复，四角因后截距不匹配的拉线也被修正；严重拉线修后可能有黑边，可裁掉 |
| 4 | 线性降噪 NXT | AI 版本选 **3**；勾 **Intensity/color separation**；Denoise Intensity **0.30**，Denoise Color **0.40**（默认 0.9 太高），Iterations 2 | 13:36–16:08 | 中档力度；**线性阶段不要暴力降噪**，否则非线性时信息不够 |

## 拉伸

| 操作 | 参数 | 时间 |
|---|---|---|
| **EZ Soft Stretch**（EZ Processing Suite，Script 菜单倒数第二个） | 默认后：Target Median **0.20**（可 0.20–0.23，图会更亮），Expand Low **0.05**，Aggressiveness **5**；Contrast 看预览微调 | 16:21–17:03 |

算法（已移植到 `AF.ezSoftStretch`）：累计直方图线性拟合求黑点 → MTF 把中值映射到 (目标中值 − Expand Low) → HT 低端扩展 −Expand Low（抬起阴影，中值最终约 0.19）。

## 非线性阶段（星云图）

| 顺序 | 操作 | 参数 | 时间 | 说明 |
|---|---|---|---|---|
| 1 | 去星 SXT | 拉伸后立即去星（新手推荐非线性去星）；Generate Star Image ✓，Unscreen Stars ✓，Large Overlap ✗；SXT v2.3.11 AI11 | 17:05–18:12 | 亮星（参宿一）留下光晕属正常，入门阶段不处理 |
| 2 | 暗部细节拉伸 | 范围选择蒙版 + 曲线把旁边暗星云拉起来 | 18:15–18:50 | **本例跳过**：暗星云本身已明显，再拉会抢主体，破坏层次 |
| 3 | 结构强化 LHE | Kernel Radius **162**，Contrast Limit **1.3**，Amount **0.8**，8-bit，Circular | 18:52–19:28 | 满屏星云时不打蒙版 |
| 4 | 调色 + 饱和度 | 拆 L 通道做 **L 蒙版**，HT 把蒙版暗部切掉一点（shadows≈**0.10**）以少算噪声；蒙版朝向：越亮越裸露；CT 选 **S 通道**提饱和度（不要太高，否则“暴力”；可分两次少量提）；有偏色再微调 RGB 曲线（本例暗星云发绿 → 压一点 G、补一点 R） | 19:45–21:57 | 宽带星云刚做完色彩校准，调色最简单 |
| 5 | 对比度 / 背景 | **HT**：左滑块定黑点（本例 shadows **0.0405**，裁 0.044% 像素），中间调 **0.454** | 22:00–22:49 | 看感觉，不要切掉太多 |
| 6 | 非线性降噪 NXT | AI3，separation ✓；明度 **0.65**（一般 ≥0.5），彩色 **0.9** | 22:51–24:17 | 力度比线性阶段高；看暗星云区域 |
| 7 | USM 锐化 | StdDev **2.0**，Amount **0.6**，Target Lightness | 24:40–25:41 | 力度按口径的分辨能力，72mm 不要太高 |

## 星点图

| 操作 | 参数 | 时间 |
|---|---|---|
| 星点调色 | 曲线 S 通道少量提饱和；ED 双分离色差大，提多了边缘“炸” | 25:47–26:24 |
| SCNR | Green，Average Neutral，Amount **0.81**，Preserve lightness（去掉星点外圈绿圈） | 26:29–26:40 |

## 合并与导出

- PixelMath **`~((~starless)*(~stars))`**（screen 混合，配合 Unscreen Stars），Replace target image。（26:47–27:06）
- 可导出 JPG/PNG。
- 多看高质量作品：寻星客（每日一图、甄选）、AstroBin，感受同目标的水准。（27:19–27:39）

## 要点
- 两种色彩校准都会，但**能用 SPCC 就用 SPCC**。
- **先 BXT 后 NXT**；线性降噪温和，非线性降噪较强。
- 非线性阶段灵活，视目标取舍（暗部拉伸、蒙版与否）。
