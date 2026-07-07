# CatalàMiner v0.7.0 — Video online, configuración, diccionario enriquecido y aprendizaje i+1

**Fecha:** 2026-07-07
**Estado:** APROBADO por el usuario (decisiones: 4 áreas A-D; enlaces directos primero; online opcional con local por defecto; imagen de tarjeta = solo fotograma del video; revisión formal del spec omitida a petición del usuario por límite de tokens — diseño ya validado en conversación).
**Objetivo:** Ver videos online sin descargarlos (enlaces directos), panel de configuración real, diccionario enriquecido manteniendo la esencia local, y recomendador de frases i+1 con export/import de progreso.

---

## Contexto de investigación (verificado en vivo)

- ffprobe/ffmpeg leen URLs http(s) remotas (metadata, cortes con seek) → tarjetas completas desde la URL sin descargar. ✓
- yt-dlp para *streaming* de YouTube está bloqueado hoy (429 / anti-bot / requiere runtime JS) → **YouTube incrustado queda fuera de v0.7.0**; la descarga puntual de YouTube (flujo actual) se mantiene.
- DRM (Netflix etc.): imposible localmente; fuera de alcance permanente.

## A. Video online por enlace directo

- Home: junto al campo de YouTube, la misma caja acepta enlaces directos; **botón nuevo «🔗 Ver online»** (además del actual «⬇️ Importar» que descarga).
- `POST /api/sessions/url {url}`: valida con `media.duration(url)` (ffprobe remoto); si duración == 0 → 400 «no se pudo leer el video de esa URL». Crea sesión `source_type="url"`, `media_path=<URL>`, `srt_source="none"`.
- `session_detail`/`media_file`: si `source_type=="url"`, `media_url` es la URL directa (el `<video>` hace streaming por rangos HTTP; nada pasa por nuestro servidor).
- Tarjetas: `_build_preview` ya recibe `media_path` → ffmpeg corta audio/fotograma/GIF leyendo la URL. Sin cambios de lógica.
- Miniaturas: `media.snapshot(URL)` una vez; si falla se escribe un marcador `thumb-<sid>.failed` para no reintentar en cada carga de la biblioteca.
- Subtítulos: adjuntar `.srt` (flujo actual) o Whisper best-effort (PyAV suele abrir mp4 http; si falla, el job reporta error y se pide el .srt).
- HLS (`.m3u8`): reproduce nativo en la app de escritorio/Safari; en Chrome se recomienda mp4 directo (documentado en README).

## B. Panel de configuración ⚙️

Botón ⚙️ en la cabecera → modal (patrón del panel 📊). Persistencia en `settings.json` ampliado, con defaults fusionados en servidor:

```json
{"deck": "Català::Mining", "anki_port": null, "sub_scale": 1.0,
 "dual_default": false, "autopause_default": false, "speed_default": 1.0,
 "ipa_enabled": true, "online_enabled": false,
 "keymap": {"prev":"a","next":"d","replay":"s","mine":"q","subs":"w",
            "browser":"g","copy":"c","dual":"e","autopause":"p",
            "fullscreen":"f","recommended":"r"}}
```

- `GET /api/settings` → dict fusionado (defaults ← archivo). `POST /api/settings {parcial}` → merge + guarda (keymap se fusiona clave a clave).
- Secciones del panel:
  - **Anki**: mazo (desplegable de `deckNames` vía `/api/anki/status`, POST al endpoint existente `/api/anki/deck`), puerto (endpoint existente `/api/anki/port`). El tipo de nota queda fijo («CatalaMiner»): su esquema/plantilla se sincroniza con la versión de la app; hacerlo configurable rompería esa sincronía.
  - **Subtítulos**: tamaño (slider 60–160% → variable CSS `--sub-scale`, vista previa en vivo), dual ES por defecto, y nota de que W/⇧W siguen ocultando líneas.
  - **Reproducción**: velocidad por defecto, auto-pausa por defecto (se aplican al abrir sesión).
  - **Diccionario**: IPA on/off; **funciones online on/off (off por defecto)** — puerta del Viccionari.
  - **Atajos**: fila por acción con su tecla; «Cambiar» → captura la siguiente tecla (a–z, sin conflictos); «Restaurar predeterminados». `1-4`, espacio, flechas, Enter y Esc son fijos.
  - **Datos**: exportar/importar palabras conocidas (ver D).
- `app.js` deja de tener teclas literales: construye `KEY2ACTION` desde settings y despacha por acción.

## C. Diccionario enriquecido (local por defecto)

- **Ejemplos de tu propio contenido** (100% local): `app/examples.py` — busca el lema en las transcripciones de todas las sesiones y devuelve hasta 4 frases distintas (con su `text_es` si está cacheado, título de sesión). `GET /api/examples?lemma=&session_id=&index=` (excluye la frase actual). El popup los muestra bajo las acepciones (carga perezosa tras el lookup, cacheada con el lookup).
- **Traducción editable en el popup**: la línea `→ eres` es editable (contenteditable); al editarla, ese texto pasa a ser el `paraula_es` de la próxima tarjeta (equivale a elegir acepción).
- **Definición online opcional (Viccionari)**: `GET /api/define?word=` — consulta `ca.wiktionary.org` (API MediaWiki, extracto de texto plano, recortado a ~800 caracteres, sección «Català» si se detecta). Best-effort con timeout corto; botón 🌐 en el popup **solo visible con `online_enabled`**.
- **Pronunciación TTS de palabra** (offline): `GET /api/tts?text=` → espeak-ng genera `media/tts-<hash>.wav`; botón 🗣 en el popup (visible solo si espeak-ng está instalado). El audio de la tarjeta sigue siendo el del segmento.
- Sin imágenes web (decisión del usuario): la imagen de tarjeta sigue siendo fotograma/GIF.

## D. Aprendizaje estilo Migaku

- **Recomendador i+1** (cliente, sin backend): frase recomendada = exactamente **1 lema en estado `unknown`** (ignoradas no cuentan). Chip «⭐ N recomendadas» junto al chip de comprensión; clic o tecla `R` → salta a la siguiente recomendada después del tiempo actual (cíclico). Los segmentos recomendados se marcan en el navegador lateral (borde ámbar). Se recalcula con cada cambio de estado.
- **Export**: `GET /api/words/export` → JSON descargable `{"version":1,"exported_at":…,"statuses":{lema:estado}}` (Content-Disposition attachment).
- **Import**: `POST /api/words/import {statuses, overwrite:false}` → fusiona (por defecto solo lemas sin estado local; `overwrite` pisa todo). Devuelve `{imported, skipped}`. UI en Configuración → Datos (descarga + file input).

## Arquitectura

Extensiones sin reescritura: `main.py` (endpoints `/sessions/url`, `/settings`, `/examples`, `/define`, `/tts`, `/words/export|import`), `app/examples.py` (nuevo), `app/tts.py` (nuevo), `app.js`/`index.html`/`style.css` (panel ⚙️, keymap, i+1, ejemplos, botones popup), `settings.json` ampliado. Degradación elegante en todo (sin Anki, sin espeak, sin internet → la función se oculta o devuelve vacío).

## Fuera de alcance v0.7.0

YouTube incrustado (anti-bot), imágenes web, Forvo, banco de frases completo, atajos multi-tecla, tipo de nota configurable.

## Criterios de aceptación

1. Pegar una URL directa de mp4 → «Ver online» → reproduce sin descarga; minar una palabra crea tarjeta con audio+imagen reales de la URL.
2. ⚙️ permite: cambiar mazo, tamaño de subtítulos en vivo, dual/auto-pausa/velocidad por defecto (aplicados al abrir sesión), remapear `D` a otra tecla y que funcione, restaurar atajos.
3. El popup muestra ejemplos de otras sesiones donde aparece el mismo lema; la traducción es editable y la tarjeta la respeta; 🗣 pronuncia la palabra; 🌐 solo aparece con online activado.
4. El chip ⭐ cuenta las frases i+1; `R` salta entre ellas; cambiar estados actualiza el conteo.
5. Exportar descarga un JSON con los estados; importarlo en una DB limpia los restaura.
6. Suite pytest verde; todo lo anterior degradando elegantemente sin Anki/espeak/internet.
