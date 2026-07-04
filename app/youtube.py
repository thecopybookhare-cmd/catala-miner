"""yt-dlp download: video (<=720p mp4) + Catalan subtitles if available."""
from pathlib import Path

from . import config, jobs


def download(jid: str, url: str) -> dict:
    import yt_dlp

    def hook(d):
        if d.get("status") == "downloading" and d.get("total_bytes"):
            jobs.set_progress(jid, 0.9 * d["downloaded_bytes"] / d["total_bytes"],
                              "Descarregant…")

    opts = {
        "format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "outtmpl": str(config.DL_DIR / "%(title).80s-%(id)s.%(ext)s"),
        "writesubtitles": True,
        "subtitleslangs": ["ca"],
        "subtitlesformat": "vtt",
        "noplaylist": True,
        "progress_hooks": [hook],
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        media = Path(ydl.prepare_filename(info))
    vtt = Path(str(media.with_suffix("")) + ".ca.vtt")
    return {"media_path": str(media),
            "title": info.get("title") or media.stem,
            "subtitles": str(vtt) if vtt.exists() else None,
            "duration": float(info.get("duration") or 0)}
