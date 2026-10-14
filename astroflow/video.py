"""Turn a tutorial video into material for the knowledge base: transcript + timestamped frames.

    python -m astroflow.video "<video.mp4>" [--out knowledge/videos/<slug>] [--every 10]

Produces in <out>/: transcript.txt / transcript.json (faster-whisper large-v3 on the GPU),
frames/t_XXXX.jpg (one every --every seconds), sheets/sheet_NN.jpg (4x4 contact sheets with timestamps).
Reading the sheets + transcript is how a workflow (steps, tools, parameter values) gets distilled into
knowledge/videos/<slug>.md. Use `keyframes` to grab full-resolution frames at chosen times to read dialogs.
"""
import argparse
import glob
import json
import os
import re
import site
import subprocess
import sys
import time
from pathlib import Path

from . import config

PROMPT = ("这是一期PixInsight天文摄影后期教程。涉及WBPP预处理、叠加、裁剪、GraXpert背景提取、DBE、GC、"
          "SPCC光谱测光颜色校准、BNCC、BlurXTerminator去卷积、NoiseXTerminator降噪、StarXTerminator去星、"
          "直方图拉伸、EZ Soft Stretch、GHS、曲线、饱和度、LHE、HDR、星点合并、PixelMath、掩膜、星系、星云。")


def _ffmpeg():
    return "ffmpeg"


def slug_for(video):
    m = re.search(r"\[(BV[0-9A-Za-z]+)\]", Path(video).name)
    return m.group(1) if m else re.sub(r"\W+", "_", Path(video).stem)[:40]


def extract_audio(video, wav):
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)


def transcribe(wav, out_base, model_size="large-v3"):
    # CTranslate2 on Windows needs the cuBLAS/cuDNN DLLs shipped in the nvidia-* wheels on the DLL path.
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
    from faster_whisper import WhisperModel
    from scipy.io import wavfile
    try:
        model = WhisperModel(model_size, device="cuda", compute_type="float16")
    except Exception:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    sr, pcm = wavfile.read(str(wav))
    wave = pcm.astype("float32") / 32768.0   # passing samples avoids PyAV, whose API drifted from faster-whisper's
    segs, _ = model.transcribe(wave, language="zh", initial_prompt=PROMPT, beam_size=5, vad_filter=True)
    rows = []
    with open(f"{out_base}.txt", "w", encoding="utf-8") as f:
        for s in segs:
            rows.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
            m, sec = divmod(int(s.start), 60)
            f.write(f"[{m:02d}:{sec:02d}] {s.text.strip()}\n")
    Path(f"{out_base}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


def frames(video, out_dir, every=10):
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{every}", "-q:v", "2",
                    str(out_dir / "t_%04d.jpg")], check=True)


def contact_sheets(frames_dir, sheets_dir, every=10, cols=4, rows=4, tw=640, th=360):
    from PIL import Image, ImageDraw, ImageFont
    sheets_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(frames_dir.glob("t_*.jpg"))
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    per = cols * rows
    for s in range(0, len(files), per):
        sheet = Image.new("RGB", (cols * tw, rows * th), "black")
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(files[s:s + per]):
            t = (int(f.stem[2:]) - 1) * every
            x, y = (i % cols) * tw, (i // cols) * th
            sheet.paste(Image.open(f).resize((tw, th)), (x, y))
            d.rectangle([x, y, x + 110, y + 34], fill="black")
            d.text((x + 4, y + 2), f"{t // 60:02d}:{t % 60:02d}", fill="yellow", font=font)
        sheet.save(sheets_dir / f"sheet_{s // per:02d}.jpg", quality=85)


def keyframes(video, times, out_dir):
    """Full-resolution PNG frames at the given times (seconds or 'mm:ss') for reading dialog values."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in times:
        if isinstance(t, str) and ":" in t:
            m, s = t.split(":")
            t = int(m) * 60 + int(s)
        p = out_dir / f"k_{int(t):04d}.png"
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1", str(p)], check=True)
        paths.append(p)
    return paths


def analyze(video, out=None, every=10):
    video = Path(video)
    out = Path(out) if out else config.KNOWLEDGE / "videos" / slug_for(video)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    wav = out / "audio.wav"
    extract_audio(video, wav)
    rows = transcribe(wav, out / "transcript")
    wav.unlink(missing_ok=True)
    frames(video, out / "frames", every)
    contact_sheets(out / "frames", out / "sheets", every)
    meta = {"video": str(video), "segments": len(rows), "every": every, "seconds": round(time.time() - t0)}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out")
    ap.add_argument("--every", type=int, default=10)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")     # video titles are Chinese; a Windows console may be cp1252
    print(json.dumps(analyze(a.video, a.out, a.every), ensure_ascii=False, indent=1))
