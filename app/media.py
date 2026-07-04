"""ffmpeg helpers: card audio cut, video frame, browser-safe remux."""
import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"
BROWSER_OK = {".mp4", ".m4v", ".mov", ".webm", ".mp3", ".m4a", ".wav", ".aac", ".ogg"}


def audio_cmd(src: str, start: float, end: float, out: str,
              pad: float = 0.25) -> list[str]:
    s = max(0.0, start - pad)
    dur = round(end + pad - s, 3)
    return [FFMPEG, "-y", "-ss", str(round(s, 3)), "-i", src,
            "-t", str(dur), "-vn", "-c:a", "libmp3lame", "-q:a", "4", out]


def frame_cmd(src: str, ts: float, out: str) -> list[str]:
    return [FFMPEG, "-y", "-ss", str(round(ts, 3)), "-i", src,
            "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", out]


def _run(cmd: list[str]):
    subprocess.run(cmd, check=True, capture_output=True)


def cut_audio(src, start, end, out, pad=0.25):
    _run(audio_cmd(src, start, end, out, pad))


def snapshot(src, ts, out):
    _run(frame_cmd(src, ts, out))


def duration(src: str) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", src],
        capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def ensure_browser_playable(src: Path, out_dir: Path) -> Path:
    """Remux (or transcode) into mp4 if the browser can't play `src`."""
    if src.suffix.lower() in BROWSER_OK:
        return src
    out = out_dir / (src.stem + ".mp4")
    if out.exists():
        return out
    try:
        _run([FFMPEG, "-y", "-i", str(src), "-c", "copy",
              "-movflags", "+faststart", str(out)])
    except subprocess.CalledProcessError:
        _run([FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-preset",
              "veryfast", "-crf", "23", "-c:a", "aac",
              "-movflags", "+faststart", str(out)])
    return out
