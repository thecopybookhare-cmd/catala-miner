"""Resolución de streams reproducibles (YouTube, 3cat…) sin descargar.

yt-dlp extrae las URLs de los formatos progresivos (video+audio en un solo
archivo, proto http) que un <video> puede reproducir directo y ffmpeg puede
leer para las tarjetas. Las URLs caducan y van atadas a la IP, así que se
re-resuelven al abrir la sesión y al minar."""
import re

_DIRECT = re.compile(r"\.(mp4|m3u8|webm|mov|m4v)(\?|$)", re.I)


def is_direct(url: str) -> bool:
    return bool(_DIRECT.search(url or ""))


def _progressive(info: dict) -> list[dict]:
    """Formatos reproducibles directo (un solo archivo http con video+audio).

    La distinción fiable es el PROTOCOLO: 'https'/'http' progresivo vs
    'http_dash_segments' (fragmentado) o 'm3u8'. Los códecs pueden venir
    como None (3cat no los reporta) — no se puede filtrar por ahí."""
    out = []
    for f in info.get("formats", []):
        proto = f.get("protocol") or ""
        if "dash" in proto or "m3u8" in proto or not proto.startswith("http"):
            continue
        if not f.get("url") or not f.get("height"):
            continue
        note = (f.get("format_note") or "").lower()
        if "only" in note:
            continue
        if f.get("acodec") == "none" or f.get("vcodec") == "none":
            continue                     # explícitamente pista suelta
        out.append({"height": f.get("height") or 0,
                    "label": f.get("format_note") or f"{f.get('height')}p",
                    "url": f["url"]})
    # dedupe por altura (quedarse con el primero)
    seen, uniq = set(), []
    for f in sorted(out, key=lambda x: x["height"]):
        if f["height"] in seen:
            continue
        seen.add(f["height"])
        uniq.append(f)
    return uniq


def _subs_url(info: dict) -> tuple[str, bool]:
    """(url del .vtt en catalán, es_automático) o ('', False)."""
    for key, auto in (("subtitles", False), ("automatic_captions", True)):
        tracks = (info.get(key) or {}).get("ca") or []
        for t in tracks:
            if (t.get("ext") == "vtt" or "vtt" in (t.get("url") or "")) and t.get("url"):
                return t["url"], auto
        if tracks and tracks[-1].get("url"):
            return tracks[-1]["url"], auto
    return "", False


def _extract(url: str) -> dict:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
            "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as y:
        return y.extract_info(url, download=False)


def resolve(url: str) -> dict:
    """{title, duration, formats:[{height,label,url}], best_url, subs_url,
    subs_auto} — o {} si no se pudo resolver."""
    try:
        info = _extract(url)
    except Exception:
        return {}
    formats = _progressive(info)
    if not formats:
        return {}
    subs_url, subs_auto = _subs_url(info)
    return {"title": info.get("title") or url,
            "duration": float(info.get("duration") or 0),
            "formats": formats,
            "best_url": formats[-1]["url"],
            "best_height": formats[-1]["height"],
            "subs_url": subs_url, "subs_auto": subs_auto}


def stream_url(url: str, height: int = 0) -> tuple[str, list[dict]]:
    """URL fresca para la altura pedida (o la mejor) + lista de alturas."""
    r = resolve(url)
    if not r:
        return "", []
    fmts = r["formats"]
    chosen = r["best_url"]
    if height:
        exact = [f for f in fmts if f["height"] == height]
        if exact:
            chosen = exact[0]["url"]
    return chosen, [{"height": f["height"], "label": f["label"]} for f in fmts]
