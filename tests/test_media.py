import shutil
import subprocess

import pytest

from app import media


def test_audio_cmd_pads_and_reencodes():
    cmd = media.audio_cmd("/v.mp4", 10.0, 12.0, "/out.mp3", pad=0.25)
    s = " ".join(cmd)
    assert "-ss 9.75" in s and "-t 2.5" in s and "libmp3lame" in s


def test_audio_cmd_trim_adds_silenceremove():
    raw = media.audio_cmd("/v.mp4", 1.0, 2.0, "/o.mp3", trim=False)
    trimmed = media.audio_cmd("/v.mp4", 1.0, 2.0, "/o.mp3", trim=True)
    assert "-af" not in raw
    assert "-af" in trimmed
    assert any("silenceremove" in a for a in trimmed)


def test_real_trim_removes_silence(tmp_path):
    if shutil.which("ffmpeg") is None:
        return
    src = tmp_path / "s.mp3"
    # 1s silencio + 1s tono + 1s silencio
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-f", "lavfi", "-t", "1", "-i", "anullsrc=r=44100:cl=mono",
         "-f", "lavfi", "-t", "1", "-i", "anullsrc=r=44100:cl=mono",
         "-filter_complex", "[1:a][0:a][2:a]concat=n=3:v=0:a=1",
         "-c:a", "libmp3lame", str(src)],
        check=True, capture_output=True)
    out = tmp_path / "t.mp3"
    media.cut_audio(str(src), 0.0, 3.0, str(out), pad=0.0, trim=True)
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout)
    assert dur < 1.8                       # de 3 s a ~1.2 s (tono + 0.1 s aire)


def test_frame_cmd_midpoint_scale():
    cmd = media.frame_cmd("/v.mp4", 11.0, "/out.jpg")
    s = " ".join(cmd)
    assert "-ss 11.0" in s and "scale=640:-2" in s and "-frames:v 1" in s


def test_clip_cmd_caps_duration_and_is_silent():
    cmd = media.clip_cmd("/v.mp4", 10.0, 30.0, "/out.gif", max_dur=6.0)
    s = " ".join(cmd)
    assert "-t 6.0" in s and "-an" in s and "palettegen" in s and "-loop 0" in s
    cmd2 = media.clip_cmd("/v.mp4", 10.0, 12.5, "/out.gif")
    assert "-t 2.5" in " ".join(cmd2)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="no ffmpeg")
def test_real_cut(tmp_path):
    src = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=3", str(src)],
                   check=True, capture_output=True)
    out = tmp_path / "cut.mp3"
    media.cut_audio(str(src), 1.0, 2.0, str(out))
    assert out.exists() and out.stat().st_size > 1000
