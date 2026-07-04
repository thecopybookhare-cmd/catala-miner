import shutil
import subprocess
import pytest
from app import media


def test_audio_cmd_pads_and_reencodes():
    cmd = media.audio_cmd("/v.mp4", 10.0, 12.0, "/out.mp3", pad=0.25)
    s = " ".join(cmd)
    assert "-ss 9.75" in s and "-t 2.5" in s and "libmp3lame" in s


def test_frame_cmd_midpoint_scale():
    cmd = media.frame_cmd("/v.mp4", 11.0, "/out.jpg")
    s = " ".join(cmd)
    assert "-ss 11.0" in s and "scale=640:-2" in s and "-frames:v 1" in s


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="no ffmpeg")
def test_real_cut(tmp_path):
    src = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=3", str(src)],
                   check=True, capture_output=True)
    out = tmp_path / "cut.mp3"
    media.cut_audio(str(src), 1.0, 2.0, str(out))
    assert out.exists() and out.stat().st_size > 1000
