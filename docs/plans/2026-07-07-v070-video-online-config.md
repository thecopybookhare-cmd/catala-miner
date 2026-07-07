# CatalàMiner v0.7.0 — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (ejecución inline). Checkboxes por tarea.

**Goal:** Implementar el spec `docs/specs/2026-07-07-v070-video-online-config-design.md` (video online por URL, panel ⚙️, diccionario enriquecido, i+1, export/import).

**Architecture:** Extensiones a FastAPI + JS vanilla existentes; dos módulos nuevos (`examples.py`, `tts.py`); settings.json como única fuente de configuración con defaults en servidor.

**Convenciones:** tests pytest con `client(tmp_path)` (patrón `tests/test_api_v3.py`); `node --check static/app.js` tras cada edición JS; commit por tarea; verificación en navegador con preview al final de cada bloque.

---

### Task 0: Rama
- [ ] `git checkout -b feature/v070-online-config`

### Task 1: Sesiones por URL (backend)
**Files:** `app/main.py`, `tests/test_api_v4.py` (nuevo)
- [ ] `class UrlReq(BaseModel): url: str` + `POST /api/sessions/url`: valida `url.startswith(("http://","https://"))`; `dur = media.duration(req.url)`; si `dur <= 0` → 400 `{"error":"no se pudo leer el video de esa URL"}`; `db.create_session(source_type="url", media_path=req.url, srt_source="none", model_size="-", duration_secs=dur, transcript_json="[]")` → `{"session_id"}`.
- [ ] `session_detail`: `s["media_url"] = s["media_path"] if s["source_type"]=="url" else "/media-file/"+sid`.
- [ ] `_session_meta`: envolver la generación de thumb con marcador `thumb-<sid>.failed` (si existe, no reintentar; en excepción, escribirlo).
- [ ] Tests: crear sesión url con `media.duration` mockeado (dur=10) → 200 + `media_url` == URL en el detail; dur=0 → 400.
- [ ] pytest verde; commit `feat: sesiones de video online por URL directa (streaming sin descarga)`.

### Task 2: Sesiones por URL (frontend)
**Files:** `static/index.html`, `static/app.js`
- [ ] Botón `<button id="url-btn" title="Ver online sin descargar">🔗 Ver online</button>` junto a `#yt-btn`; placeholder del input pasa a «URL de YouTube o enlace directo (.mp4, .m3u8)…».
- [ ] Handler: POST `/api/sessions/url`; error → toast; ok → `openSession`.
- [ ] Verificar con una URL mp4 pública en preview (reproduce + popup + tarjeta). Commit `feat: boton Ver online`.

### Task 3: Settings backend
**Files:** `app/main.py`, `tests/test_api_v4.py`
- [ ] `DEFAULT_SETTINGS` (dict del spec §B) módulo-level; `_settings()` fusiona defaults ← archivo (keymap clave a clave).
- [ ] `GET /api/settings` → fusionado; `POST /api/settings` (body dict parcial) → merge sobre el archivo (keymap merge), guarda, devuelve fusionado. Validar: solo claves conocidas; keymap solo letras a-z únicas por acción.
- [ ] Tests: GET trae defaults; POST parcial persiste y fusiona; keymap inválido (tecla duplicada) → 400.
- [ ] Commit `feat: endpoints de configuracion con defaults fusionados`.

### Task 4: Panel ⚙️ + keymap (frontend)
**Files:** `static/index.html`, `static/app.js`, `static/style.css`
- [ ] Botón ⚙️ en header; `#settings-view` modal (patrón stats) con secciones Anki / Subtítulos / Reproducción / Diccionario / Atajos / Datos.
- [ ] Al init: `SETTINGS = await api("/api/settings")`; aplicar `--sub-scale`; en `openSession`: `setDual(SETTINGS.dual_default)`, `setAutopause(SETTINGS.autopause_default)`, `V.playbackRate = SETTINGS.speed_default` (sincronizar `SPEED_IX`).
- [ ] CSS: `#overlay-ca { font-size: calc(<actual> * var(--sub-scale, 1)); }` (igual overlay-es); slider actualiza la variable en vivo y guarda al soltar.
- [ ] Keymap: `KEY2ACTION` invertido de `SETTINGS.keymap`; el keydown despacha por acción (`prev/next/replay/mine/subs/browser/copy/dual/autopause/fullscreen/recommended`); flechas/espacio/Enter/Esc/1-4 fijos; ⇧+mine = editar. Editor de atajos: botón por fila → estado «pulsa una tecla» → captura, valida conflicto, POST. «Restaurar» → POST keymap por defecto.
- [ ] Anki: select de mazos (de `/api/anki/status.decks`) → POST `/api/anki/deck`; input puerto → POST `/api/anki/port`.
- [ ] Diccionario: checkboxes `ipa_enabled`, `online_enabled` → POST settings; popup respeta ambos.
- [ ] `node --check`; verificación preview (cambiar tamaño en vivo, remapear D→L y probar); commit `feat: panel de configuracion con atajos remapeables`.

### Task 5: Ejemplos propios + popup enriquecido
**Files:** `app/examples.py` (nuevo), `app/tts.py` (nuevo), `app/main.py`, `static/*`, `tests/test_api_v4.py`
- [ ] `examples.find(con, lemma, limit=4, exclude_sid="", exclude_idx=-1)` → lista de `{text, text_es, session_id, session_title, index, start}`, dedupe por `text`, corta en `limit`.
- [ ] `GET /api/examples?lemma=&session_id=&index=` → `{"examples":[...]}`.
- [ ] `tts.speak(text) -> str` (nombre de archivo en MEDIA_DIR o "" sin espeak): `espeak-ng -v ca -w media/tts-<md5>.wav`, cache por hash. `GET /api/tts?text=` → `{"file": ...}`.
- [ ] `GET /api/define?word=` → extracto plano de ca.wiktionary (requests, timeout 6s, best-effort `""`), recortado a 800 chars.
- [ ] Popup: tras `renderPopupLookup`, fetch ejemplos (cache en LOOKUP_CACHE) → `#wp-examples` (máx 3, texto + título dim); `#wp-word-es` contenteditable → actualiza `POP.chosen`; botón 🗣 (si `r.ipa` no vacío ⇒ espeak presente) reproduce `/api/tts`; botón 🌐 (solo `online_enabled`) → muestra extracto en bloque scrollable.
- [ ] Tests backend: examples encuentra el lema en otra sesión y excluye la actual; tts sin espeak (which→None) → `{"file":""}`; define con requests mockeado.
- [ ] Commit `feat: ejemplos del propio contenido, traduccion editable, TTS y Viccionari opcional`.

### Task 6: i+1 + export/import
**Files:** `static/app.js`, `static/index.html`, `static/style.css`, `app/main.py`, `tests/test_api_v4.py`
- [ ] JS: `updateRecs()` — `RECS = [i…]` con exactamente 1 lema `unknown`; chip `#rec-chip` «⭐ N recomendadas»; clic o acción `recommended` (tecla R) → siguiente rec tras `V.currentTime` (cíclico); `.seg.rec` borde ámbar en navegador; recalcular en `updateComp()`.
- [ ] `GET /api/words/export` → JSONResponse con `Content-Disposition: attachment; filename=catalaminer-paraules.json`.
- [ ] `POST /api/words/import {statuses, overwrite=false}` → valida estados, fusiona, `{imported, skipped}`.
- [ ] UI en ⚙️ Datos: enlace de descarga + file input que lee JSON y hace POST; toast con resultado.
- [ ] Tests: export refleja estados; import respeta overwrite=false (no pisa) y cuenta bien.
- [ ] Commit `feat: recomendador i+1 y export/import de palabras`.

### Task 7: Versión, verificación y merge
- [ ] `?v=0.7.0` en index.html; `version = "0.7.0"` en pyproject; README: sección enlaces online + ⚙️ + i+1 + export (breve).
- [ ] Suite completa + `node --check`; criterios de aceptación del spec §final con preview.
- [ ] Merge `--no-ff` a main; reiniciar servidor del usuario.
