---
name: astro-postprocess
description: Automated deep-sky and comet post-processing for the user's ZWO ASI2600MC + 72ED data on F:\AstroPhotograph - organise new sessions (lights + matched darks/bias/flats), stack with headless WBPP, post-process in headless PixInsight following the user's tutorial videos (OSC broadband nebula / galaxy recipes), compare with top-rated AstroBin works of the same target, and drive it all with the DeepSeek agent. Use when the user asks to organise, stack, process, re-process, tune ("饱和度再高一点"), review or compare astrophotos, to add a new tutorial video to the workflow, or asks about the astroflow framework.
---

# astroflow — 深空后期自动化

Project root: this repository. Code in `astroflow/`, knowledge base in `knowledge/` (start with `knowledge/README.md`), distilled processing skills for the app's agent in `skills/<name>/SKILL.md` (same format as this skill; read the matching one before processing a target type). Python is `python` (3.14, user site-packages; do not use `-I`). Paths, LLM providers and preferences live in the user settings (`astroflow/settings.py`, file `%APPDATA%\astroflow\settings.json`; API keys in the OS credential store); `config.py` reads them at access time.

There is also a desktop app (`desktop/`, Electron + React, backend `python -m astroflow.api`): see `desktop/README.md` for running it in a browser (`--dev-origin`, `npm run dev:web`) or as Electron, and for packaging. After changes run `python -m pytest -q` and `cd desktop && npm run typecheck`; regenerate the TypeScript API types with `npm run gen:api` when `astroflow/api/models.py` changes.

## Data layout
- New nights land as `F:\AstroPhotograph\<Target>\Light_*.fit` (NINA/ASIAIR names, local time in filename), or the user imports a folder in the app.
- `python -m astroflow organize [--source <folder>] [--apply] [--copy]` → `F:\AstroPhotograph\In Processing\<YYYYMonDD night>\<Target>\{Light,Dark,Bias,Flat,Thumbnails}` (`astroflow/organize.py`). Frames are recognised by FITS header (IMAGETYP, else file/folder name), in any layout and from any capture program, including DSLRs (ISO, no temperature). Each target's calibration comes from the imported folder first, else from the libraries. Darks and bias are matched on camera/gain/offset/exposure and set-point ±1 °C, closest first. Flats are matched by night and filter, at any gain. A calibration-only folder goes to the library and fills the targets that lack those frames. `--refresh` fills staged targets from the library. Lights are moved unless `--copy` (the app copies by default); calibration is always copied. Dry run by default: show the plan before `--apply`.
- Only the user moves finished targets to `F:\AstroPhotograph\Processed\` (ask first).
- Darks shot later on the ASIAIR: `python -m astroflow.darks --source "\\10.0.0.161\EMMC Images\Autorun\Dark" --exptime 300 --settemp -10 --count 10 --since <date> --wait --then process` (run from PowerShell — the SMB share is invisible to Git-Bash processes) imports them into the Dark Library, refreshes calibration, stacks and runs the agent.

## Pipeline
1. Stack: `python -c "from astroflow import wbpp; print(wbpp.run(r'<target dir>'))"` — WBPP automation mode, plate solves the masters (online VizieR, 3–4 min each). Output in `<target>/Output/master/*_autocrop.xisf`.
2. Post-process: `python -m astroflow.pipeline "<target dir>" [--stage S | --from S] [--set stage.step.param=value]`
   - recipe auto-chosen from the target type (`astroflow/objects.py`) and the night's filter in `In Processing/<night>/session.json` (`filter_class`: `osc_broadband` | `osc_multiband`): `osc_broadband_nebula` (video ep1), `osc_galaxy` (video ep2), `osc_multiband_nebula` (Antlia Quad Band nights; provisional, see `knowledge/filters.md`). Ask the user which filter was used for a new night and write `session.json` — FITS headers do not record it.
   - stages: linear → stretch → stars → starless → stars_color → combine; checkpoints + `state.json` in `<target>/Post/`, previews in `Post/previews/`, final `<target>_<date>.tif/.jpg/.png` in `Post/` (the user wants a PNG of every finished image; `pipeline.export_final()` re-exports).
   - `Post/params.json` holds the parameter edits the user saved in the desktop app. Every run applies them (CLI and agent too), and `--set` / agent overrides go on top. Leave the file to the user; to change a default for good, edit the recipe.
   - examples: `--set starless.sat.boost=0.66`, `--set linear.nxt.params.denoise=0.25`, `--set combine.recombine.starsAmount=0.85`.
3. Agent (DeepSeek, judgement + tuning): `python -m astroflow.agent.run "M8"` or `--task "只重做 starless，饱和度高一点"`. Log: `<target>/Post/agent_log.jsonl`, report: `Post/report.md`. Key in `.env` (`api_key=`); never print it.
4. References: `python -m astroflow.references "M8" --fov 1.44 [--peer multiband]` → `knowledge/targets/<SLUG>/` (AstroBin best/peer thumbnails + fingerprints, filtered to the catalogue position; peer = colour-sensor broadband or, for multiband nights, colour-sensor + narrowband/multiband filters; local reference only, keep credits). Notes per target in `notes.md`.

## Comets (moving target, few frames, clouds)
Read `knowledge/comets.md` first. After WBPP (only its `Output/registered` frames are used):
`python -m astroflow.comet --target "<target dir>"` (converts registered XISF → FITS, per-frame background / photometric scale / cloud + satellite-trail masks / SXT star removal with the coma restored, star-aligned star layer + comet-aligned comet layer; add `--reuse-sxt` when re-running) → `python -m astroflow.pipeline "<target dir>" --recipe comet --master "<target dir>/Post/comet_stack.fits"`. Check `Post/weights.jpg` (black = rejected) and `Post/diag.json`. Never run SXT on a comet image in the pipeline: it takes the bright coma for a star (the recipe splits stars with `split_stars` instead). References: `python -m astroflow.references "C/2025 R3" --fov 1.44 --published <first> <last>` (the comet's look changes within days).

## Rules that must hold
- One PixInsight at a time. A second instance gets settings slot 2: SPCC fails (no Gaia path) and BlurXTerminator crashes. `pi.py` serialises jobs and waits while the user's GUI is open — tell the user to close PixInsight if a job waits.
- Never crop before SPCC (DynamicCrop deletes the astrometric solution); start from the WBPP `_autocrop` master.
- Read `.runs/<job>/console.txt` when a PixInsight job fails; RC tools return false instead of throwing.
- Judgement calls (gradient model clean? colour right? better than before?) go to the vision model via the agent's `look` tool, or to you looking at `Post/previews/*.jpg` — not to hard-coded thresholds.
- Broadband OSC data should not imitate narrowband SHO/HOO palettes from references.

## Reviewing a result yourself
Read `Post/previews/10a_after_cc.jpg` (colour), `20_stretched.jpg`, `30_starless.jpg`, `50_final_2k.jpg` and `knowledge/targets/<SLUG>/refs/peer_*.jpg`; check against `knowledge/checklists.md`; rerun only the stage that needs it.

## Adding a tutorial video (new workflow)
`python -m astroflow.video "<video.mp4>" --out knowledge/videos/<name>` (Whisper GPU transcript + frames + contact sheets) → read sheets/transcript, grab dialogs with `astroflow.video.keyframes()` → write `knowledge/videos/<name>.md` like ep1/ep2 → add a recipe to `astroflow/pipeline.py` (new ops in `astroflow/pjsr/steps.js`, syntax-check with `node --check`) → map target types in `objects.py`.
