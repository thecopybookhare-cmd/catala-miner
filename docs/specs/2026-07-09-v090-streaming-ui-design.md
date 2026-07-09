# CatalàMiner v0.9.0 — Streaming de YouTube/3cat y pulido de UI

**Fecha:** 2026-07-09
**Estado:** APROBADO (streaming: «Ver online» inteligente; calidad: mejor progresivo + selector + auto-bajada).
**Objetivo:** Ver YouTube y 3cat en streaming dentro del reproductor sin descargar, minando tarjetas desde la URL; y una pasada de diseño (estadísticas tipo Migaku, reproductor y menús pulidos).

---

## Investigación (verificada en vivo)

- **3cat (CCMA)**: yt-dlp resuelve MP4 progresivos con audio a `360p` y `576p` (proto https, URL única). ffprobe los lee (h264+aac, duración completa). Sin HLS.
- **YouTube**: formato 18 (360p mp4 progresivo con audio) resuelve a `googlevideo.com/videoplayback`, reproducible. 720p+ es DASH (video suelto) → requiere descarga. El bloqueo anti-bot previo era 429 temporal; el progresivo no usa el reto JS.
- Las URLs resueltas **caducan (~horas) y van atadas a la IP** → hay que guardar la URL de página y **re-resolver al abrir la sesión** y al minar.

## Parte A — Streaming en el reproductor

### A1. Resolvedor (`app/stream.py`)
- `resolve(url, quality="auto") -> dict`: si es enlace directo (.mp4/.m3u8) → passthrough. Si es sitio soportado → yt-dlp `--skip-download` extrae info y elige formatos **progresivos con audio** (`acodec!=none`, proto http/https), ordenados por altura. Devuelve `{title, duration, formats:[{label, height, url}], best_url, subs}`.
- `stream_url(url, height)`: re-resuelve una URL fresca para una altura dada (para abrir sesión y minar).
- Best-effort: excepciones → `{}`; degradación limpia.

### A2. «Ver online» inteligente
- `POST /api/sessions/stream {url}` → job (`resolviendo el enlace…`): resuelve, baja subtítulos (yt-dlp auto/manual .vtt → `clean_auto` si auto), crea sesión `source_type="stream"`, `page_url=<url original>`, `media_path=<best_url>`, `stream_height=<altura>`, transcripción de los subs si los hay.
- Enlace directo (.mp4/.m3u8) sigue el camino actual (`source_type="url"`).
- El botón «Ver online» detecta y hace lo correcto; «Importar» se mantiene para descarga offline (HD).

### A3. Sesión de stream (URLs frescas)
- Migración DB: columnas `page_url TEXT`, `stream_height INTEGER`.
- `GET /api/sessions/{id}/stream-url?height=` → re-resuelve con yt-dlp y devuelve URL fresca + lista de alturas disponibles. Al abrir una sesión `stream`, el frontend pide esto y pone el `src` (nunca usa la URL vieja caducada).
- `_build_preview` para sesiones `stream`: re-resuelve una URL fresca antes de cortar con ffmpeg (si la guardada falló). El fotograma/audio salen de la URL viva.

### A4. Selector de calidad + auto-bajada (reproductor)
- Menú de calidad (Auto / 576p / 360p / …) junto a los controles; cambiar preserva `currentTime` (guardar t, cambiar `src`, `currentTime=t`, play).
- Auto: mejor altura disponible. Auto-bajada: si se acumulan eventos `waiting`/`stalled` (≥3 en 10 s), baja un escalón y avisa con toast.
- Subtítulos ya cargados no dependen de la calidad.

## Parte B — Pulido de UI (aplicar diseño)

### B1. Estadísticas tipo Migaku
- Dashboard más rico: **crecimiento de palabras conocidas en el tiempo** (línea, desde `word_status.updated_at`), **actividad de minado** (heatmap por día del mes en curso), donut de estados mejorado, tarjetas-KPI (conocidas, aprendiendo, minadas, retención). SVG a mano, coherente.
- Nuevo `GET /api/stats` extendido: `known_over_time` (acumulado por fecha), `mined_by_day`.

### B2. Reproductor bonito
- Controles rediseñados (agrupados, iconografía consistente, estados hover/activos claros), barra de progreso con **marcadores de segmento** y realce del actual, subtítulos con mejor tipografía/sombra, transiciones suaves. Chip de calidad integrado.

### B3. Menús y biblioteca
- Tarjetas de biblioteca con badge de fuente (▶ YouTube / 📺 3cat / streaming) y estado; hover y transiciones pulidos; cabecera y chips consistentes; popup y paneles con espaciado y microanimaciones coherentes.

## Fuera de alcance
720p+ en streaming (requiere descarga; queda en Importar), HLS/DASH adaptativo real (ninguna plataforma lo expone por yt-dlp), rediseño de marca más allá del icono ya hecho.

## Criterios de aceptación
1. Pegar un enlace de página de YouTube o 3cat + «Ver online» reproduce en el reproductor en segundos, sin descarga; minar una palabra crea tarjeta con audio+imagen reales.
2. Reabrir esa sesión días después vuelve a reproducir (re-resuelve URL fresca); el selector de calidad cambia resolución preservando el punto; si se atasca, baja sola.
3. Los subtítulos automáticos de YouTube salen limpios; 3cat con sus subs si los trae.
4. Las estadísticas muestran crecimiento de conocidas y actividad, con estética pulida tipo Migaku.
5. Reproductor, biblioteca y menús se ven pulidos y consistentes; suite pytest verde; degradación limpia sin red.
