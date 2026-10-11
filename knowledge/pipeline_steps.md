# PixInsight 步骤参考（astroflow/pjsr/steps.js）

每个步骤是 `{"id": "...", "op": "<名称>", ...参数}`。`target` 选窗口（默认 `main`；去星后有 `stars`）。
`params` 里的键直接写入对应 PixInsight 进程（名称必须与进程参数一致，否则报错）。`optional: true` 失败不中断。
蒙版参数（lhe/curves/saturation/usm 支持）：`mask`: `"lum"` | `"range"` | `"object"`，前缀 `inverse_` 反相；
`maskClip`（lum 蒙版黑点，默认 0.10），`rangeLow`/`rangeHigh`/`rangeSmoothness`/`rangeFuzziness`（默认 0.16/1/65/0），`objectScale`/`feather`（object 蒙版，默认 1.2/0.35）。

## 线性阶段
| op | 作用 | 主要参数（默认） |
|---|---|---|
| `find_background` | 自动找一块最暗最平的无星背景框（FindBackground 思路），供 SPCC/BN/CC 参考 | `box`（短边/40），`margin` 0.06，或直接给 `rect` |
| `gradient_correction` | GC 去梯度 | `params`（GradientCorrection 参数，默认即视频），`saveModel`（模型预览 jpg 路径） |
| `abe` | ABE 多项式去梯度 | `params`：`polyDegree` 2 等 |
| `dbe_auto` | 自动 DBE：网格采样避开天体椭圆与亮结构，稳健多项式拟合后相减 | `degree` 2，`nx` 24，`ny` 16，`box`，`objectScale` 1.6（需先 `locate_object`） |
| `locate_object` | 用星图解析把星表位置/大小投影到图上（ctx.object） | `ra`,`dec`,`diameter`(′),`axisRatio`,`posAngle`（Python 自动从星表填） |
| `plate_solve` | ImageSolver（已有解析则跳过） | `ra`,`dec`,`focal`,`pixelSize`,`force` |
| `spcc` | SPCC（默认=视频设置：Average Spiral Galaxy、Sony Color Sensor、Ideal QE、Gaia DR3/SP），背景参考用 find_background 的框 | `params` |
| `bncc` | 手动 BN+CC | `bnHigh`/`ccBackgroundHigh`（默认按背景框统计算），`whiteLow`，`whiteROI: "object"`+`structureDetection: false`（星系） |
| `color_calibration` | 先 SPCC（必要时先解析），失败退回 BNCC；info.method 说明用了哪个 | `method: "bncc"` 强制手动；`spcc`/`bncc`/`solve` 子参数 |
| `bxt` | BlurXTerminator | `params`：`sharpen_stars` 0.5，`adjust_halos` 0，`sharpen_nonstellar` 0.5，`correct_only` false |
| `nxt` | NoiseXTerminator（AI3，明度/彩色分离） | `params`：`denoise`（明度），`denoise_color`，`iterations` 2 |

## 拉伸与非线性
| op | 作用 | 主要参数（默认） |
|---|---|---|
| `stretch` | `method`: `ez_soft`（EZ Soft Stretch 移植）/ `stf`（AutoSTF 转 HT）/ `mas`（MultiscaleAdaptiveStretch） | `targetMedian` 0.20，`expandLow` 0.05，`aggressiveness` 5 |
| `sxt` | StarXTerminator：主图变无星，星点图放到 `stars` 窗口 | `unscreen` true，`largeOverlap` false |
| `hdr` | EZ HDR 移植：HDRMT 后经反相背景蒙版混合 | `layers` 5，`amount` 0.3 |
| `lhe` | LocalHistogramEqualization | `params`：`radius` 162（`auto` = clamp(0.35×天体半长轴, 24, `radiusMax`)），`slopeLimit` 1.3，`amount` 0.8；可加蒙版 |
| `saturation` | 经 L 蒙版用曲线 S 通道提饱和；`rgb` 可做小幅色彩平衡 | `boost`（x=0.5 处 y，默认 0.60；0.5=不变），`passes` 1，`mask` "lum"，`rgb`: {"R": +0.01, "G": -0.01} |
| `curves` | 任意曲线 | `channels`: {"K": [[0,0],[0.5,0.55],[1,1]], "S": ...}（R,G,B,K,L,S,a,b,c,H） |
| `ht` | 对比度/背景：黑点+中间调 | `shadows` 数值或 `"auto"`（按 `clipFraction` 裁掉的像素比例，默认 0.0004），`midtones` 0.5，`maxShadows` 0.08 |
| `usm` | UnsharpMask | `params`：`sigma` 2.0，`amount` 0.6 |
| `scnr` | 去绿；`color: "magenta"` 时反相→去绿→反相，去品红（窄带/多波段星点） | `params`：`amount` 0.81（星系星点 0.53） |
| `recombine` | 星点合并 | `mode` "screen"（`~((~a)*(~b))`）或 "add"，`starsAmount` 1.0（<1 减弱星点） |
| `pixelmath` | 任意 PixelMath | `expression`（`$T` = 目标；其他窗口用 id，如 `stars`） |

## 工具
| op | 作用 |
|---|---|
| `crop` | DynamicCrop（**会删除星图解析结果**：SPCC 之前不要裁）；`rect`: `{x0,y0,x1,y1}` 或 `[x0,y0,x1,y1]`，或 `fraction`/`pixels` 四边等量裁 |
| `preview` | 存一张预览 jpg（线性图自动 STF；色彩校准前 unlinked） |
| `measure` | 返回统计、噪声、背景框统计 |
| `save` | 存检查点 |

## 星云/星系配方阶段（pipeline.py）
`linear`（10_linear）→ `stretch`（20_stretched）→ `stars`（30_starless + 31_stars）→ `starless`（40_starless_final）→ `stars_color`（41_stars_final）→ `combine`（50_final + 成品 tif/jpg/png）。
配方：`osc_broadband_nebula`（第1期）、`osc_galaxy`（第2期）、`osc_multiband_nebula`（多波段滤镜，暂定，见 filters.md）。
重跑某阶段会让其后的阶段失效。
