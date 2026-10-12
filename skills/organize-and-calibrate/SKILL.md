---
name: organize-and-calibrate
description: 导入新拍的数据与校准帧——任何拍摄软件、任何文件夹结构，按 FITS 头认帧类型并配暗场/偏置/平场（先用同一批拍的，再用校准帧库），缺暗场时怎么办，ASIAIR 的坑，每晚的滤镜记录。用户说“整理/导入/新拍了/补拍暗场”或校准警告里有“缺少暗场”（旧目标写作 NO DARKS）时加载。
---

# 整理与校准帧

## 目录约定（数据根目录见系统提示）
- `In Processing/<YYYYMonDD>/<目标>/{Light,Dark,Bias,Flat,Thumbnails}`：未完成后期的目标；夜晚 = 本地时间减 12 小时（午夜后的帧归前一晚）。
- `Dark Library`、`Bias Library`、`Flat`：校准帧库；`Processed/`：用户自己把完成的目标移过去（不要替用户移动）。
- 每晚用的滤镜写在 `In Processing/<night>/session.json`（filter、filter_class：osc_broadband | osc_multiband），FITS 头里没有。

## organize 工具
- 默认 dry run，返回计划（每行：kind = target 新目标 / fill 补全已有目标 / library 加入校准帧库；lights/darks/bias/flats 各自的数量、说明和来源 origin = import 随数据 / library 校准帧库 / target 目标已有；warnings；notes 说明没用上的文件）。**apply 只在用户明确要求时做**。
- `source=<文件夹>`：任何拍摄软件（ASIAIR、NINA、SharpCap、Ekos …）、任何结构都行，包括已经分好 Light/Dark/Bias/Flat 的目标文件夹。帧类型看 IMAGETYP，没有就看文件名/文件夹名；目标看 OBJECT，没有就看文件夹名。WBPP 输出、master、ASIAIR 的 Preview_* 不导入。不想动原文件：`copy=true`。
- 匹配（全看文件头，文件夹名不可信：这台机器的 Bias Library 里 -5degree 和 0degree 是反的）：暗场 = 同相机/尺寸/binning/增益（单反是 ISO）/偏移/曝光 + 制冷温度 ±1 °C（最接近的优先；单反等没有温度时优先同一晚）；偏置同理不看曝光；平场 = 同相机/尺寸/binning/滤镜、同一晚（增益不限）；暗平场随平场一起。先用导入文件夹里同一批拍的，没有再用校准帧库。
- 只有校准帧的文件夹（比如后来补拍的暗场）：放进校准帧库，并自动补给 In Processing 里缺这些帧的目标。
- `refresh=true`：用校准帧库给已整理的目标补上缺的校准帧。

## 缺暗场
- warnings 里有“缺少暗场”（旧目标写作 NO DARKS）：不要直接叠加。告诉用户缺哪个曝光/温度的暗场；用户明确说可以不用暗场时再叠加。
- 用户在 ASIAIR 上补拍后：命令行 `python -m astroflow.darks --source <ASIAIR Dark 文件夹> --exptime <s> --settemp <C> --count 10 --then restack`（网络共享在 Windows 上要从 PowerShell 启动的进程才看得到）。
- ASIAIR 切换计划时，盖着镜头盖拍的“暗场”可能被存成 Light_<目标>：darks 模块按统计特征识别（dark-like）并在库里改名，不动原件。

## 其他
- ASIAIR 的 Preview 模式文件名是 `Preview_*`，不会被当作 Light 整理（彗星那次就是手工整理的）。
- 缺平场时成品仍可做，但暗角和灰尘靠背景模型兜底，报告里写明。
