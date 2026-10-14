# 资料库（knowledge/）

agent（`read_knowledge` 工具）和人都从这里查：后期流程、参数、检查标准、目标参考。
按任务组织的“怎么做”在根目录 `skills/`：agent 先看技能索引，按需 `load_skill`，技能再指向这里的细节文档。

| 文档 | 内容 |
|---|---|
| `videos/ep1-osc-broadband-nebula.md` | 进阶教程第1期：彩机宽带星云全流程与参数（IC 434） |
| `videos/ep2-osc-galaxy.md` | 进阶教程第2期：彩机星系全流程与差异（M31） |
| `videos/ep3-mono-lrgb-broadband.md` | 进阶教程第3期：黑白相机 LRGB（M51）：通道对齐合成、L 与 RGB 分开处理、LRGB 合成 |
| `videos/<ep>/transcript.txt`, `sheets/`, `keyframes/` | 视频原始材料：转写、每10秒截图、读参数用的关键帧 |
| `filters.md` | 每晚滤镜对处理的影响（宽带 / Antlia 四通道多波段） |
| `comets.md` | 彗星：少帧混合曝光、云、卫星轨迹、SXT 吃彗发等的处理方法与教训（`astroflow/comet.py` + `comet` 配方） |
| `pipeline_steps.md` | 每个自动化步骤（PJSR）的作用与参数 |
| `checklists.md` | 每个阶段“好结果”的标准，agent 据此判断是否重跑 |
| `pitfalls.md` | 无界面 PixInsight 与本机环境的坑 |
| `pi_icon_set_from_M42_project.txt` | 用户 M42 项目里那套流程图标（与教程作者同款）的全部参数 |
| `targets/<目标>/notes.md` | 同目标高赞作品（AstroBin）总结：颜色基准、关键结构、常见坑、参数建议 |
| `targets/<目标>/refs.json`, `refs/` | 参考作品清单（作者、链接、点赞、器材）与缩略图、数值指纹（仅本地参考） |
| `targets/<目标>/agent_notes.md` | agent 处理该目标时记下的经验（跨次运行的记忆） |
| `agent_lessons.md` | 通用经验 |

## 新增一期教程视频
1. `python -m astroflow.video "<视频.mp4>" --out knowledge/videos/<名字>` —— 转写 + 截图 + 缩略图总览。
2. 读 `sheets/` 与 `transcript.txt`，用 `astroflow.video.keyframes()` 截关键帧读对话框参数。
3. 写 `videos/<名字>.md`（按本目录两期的格式），把新流程加成 `astroflow/pipeline.py` 的一个配方，必要时在 `pjsr/steps.js` 增加步骤。
