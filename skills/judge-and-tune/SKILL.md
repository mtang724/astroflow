---
name: judge-and-tune
description: 每个处理阶段之后的检查与调参——怎么读指标、怎么问视觉模型、和参考作品比什么、看到某种问题该改哪个参数。处理过程中每跑完一个阶段、或用户说“饱和度太低/背景太亮/星点太多”之类时加载。
---

# 检查与调参

先看数字（run_stage 返回的 metrics、compare_with_references），再看图（`look`），两者一致才下结论。详细标准：`read_knowledge('checklists')`；每个步骤的参数：`read_knowledge('steps')`。

## 每个阶段看什么
| 阶段 | 看的图 | 合格标准 | 常见问题 → 改法 |
|---|---|---|---|
| linear | `10_gc_model`（背景模型）、`10a_after_cc` | 背景模型只是平滑梯度；背景中性（background_cast R/G、B/G 0.95–1.05）；星点大多白 | 模型里有天体形状 → 星系改 `dbe_auto`；偏色 → 看 color_calibration 的 info.method，bncc 表示 SPCC 失败 |
| stretch | `20_stretched` | lum_median 约 0.15–0.25；核心不过曝；暗部没被切 | 核心过曝 → `stretch.targetMedian` 降到 0.15–0.18，或后面加 `hdr` |
| stars | `30_starless`、`31_stars` | 无星残留、无黑洞；星点图里没有星云 | 残留多 → `sxt.largeOverlap: true` |
| starless | `40_starless_final` | 结构自然、无晕圈结块；色度比在目标范围；暗区不塑料 | 偏淡 → `sat.boost` 0.72→0.8 或 `passes` 2；噪声 → `nxt2.params.denoise` |
| stars_color | `41_stars_final` | 冷暖分明不“炸”；无绿星 | 色差大 → `star_sat.boost` 降低 |
| combine | `50_final_2k` + 参考图 | 星点不抢主体；整体与 peer 接近 | 星太强 → `recombine.starsAmount` 0.8–0.9 |

## 饱和度（用户最在意的一条）
- 用 `compare_with_references` 返回的 `subject_chroma.ratio`（主体 Lab 色度 / peer 中位数）判断，目标范围见系统提示（默认 0.8–1.2）。
- 低于下限：提高 `sat.boost`（0.72→0.8）或 `passes`（1→2），检查 `maskMidtones`（默认 0.3，越小作用越强）。彩色噪声交给 NXT 的 `denoise_color`；不要拿“积分时间短”当理由接受明显偏淡的颜色。
- 高于 1.3、出现荧光感或彩色斑块才算过度。
- 星点合并会略微冲淡颜色：combine 之后再核一次。

## 问视觉模型的方式
- 问具体问题，例如：“背景模型里有没有星系的形状？”“背景是不是中性灰？哪里偏色？”“和参考图比：饱和度、对比、背景亮度、星点大小各差多少，该怎么改？”
- 要结构化结论时 `want_json=true`。
- 视觉模型的话要和数字对照；二者矛盾时以数字为主，并在报告里写明。
- 当前服务商没有视觉模型时 `look` 会报错：只按数字判断，并在报告里说明没有看图。

## 宽带 vs 窄带参考
宽带彩机数据不要模仿 SHO/HOO 配色；参考作品若是窄带，只借鉴结构与对比，不借鉴颜色。
