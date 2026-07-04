import re

_TS = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->\s*"
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})")
_TAG = re.compile(r"<[^>]+>")


def _secs(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_subtitles(text: str) -> list[dict]:
    """Parse SRT or WebVTT into [{start, end, text}]. Strips markup tags."""
    segs = []
    cur = None
    for line in text.splitlines():
        m = _TS.search(line)
        if m:
            if cur and cur["text"]:
                segs.append(cur)
            g = m.groups()
            cur = {"start": _secs(*g[:4]), "end": _secs(*g[4:]), "text": ""}
        elif cur is not None:
            clean = _TAG.sub("", line).strip()
            if clean and not clean.isdigit():
                cur["text"] = (cur["text"] + " " + clean).strip()
    if cur and cur["text"]:
        segs.append(cur)
    return segs
