# LinguaMiner — Roadmap

Checklist vivo de la investigación (auditoría del repo + ecosistema de *sentence
mining*: asbplayer, Lute, VocabSieve, GameSentenceMiner, awesome-immersion).
Marcado a medida que se implementa.

## ✅ Hecho

- [x] **LICENSE MIT** + aviso de uso personal/educativo · CI (GitHub Actions:
      ruff + pytest) · `ruff` · `CONTRIBUTING.md` · README con badges (§5)
- [x] **Repo remoto** privado en GitHub
- [x] **Asistente de primer arranque** — checklist de preparación + descarga
      guiada de modelos con progreso (§6)
- [x] **Francés (fr→es)** — OPUS-MT `gaudi/opus-mt-fr-es-ctranslate2` (CTranslate2),
      spaCy `fr_core_news_sm`, bidix Apertium fra-spa, glosas eswiktionary (§2)
- [x] **Modo compartir** — servidor bajo demanda en la red local / tailnet
      (Tailscale) + **PWA** instalable (manifest + service worker + iconos) (§1)
- [x] **Optimización** (§4):
  - [x] Índices SQLite (`cards.session_id`, `cards.status`,
        `word_status(language,status)`) + PRAGMA (`synchronous=NORMAL`,
        `temp_store=MEMORY`)
  - [x] Caché con TTL de la resolución de streams (yt-dlp) — recorta la latencia
        de la ráfaga abrir+cambiar-calidad+minar
  - [x] Precarga en background (lifespan) del motor de traducción + bidix ya
        descargados, para que el primer popup no espere
  - [x] Imports perezosos auditados (whisper/ctranslate2/spaCy ya diferidos)
  - [~] *distil-whisper descartado*: es solo-inglés; para ca/fr el modelo `small`
        ya es la opción rápida

## ✅ Hecho (features de estudio)

- [x] **Ajuste de sincronía de subtítulos** (offset ±0.1 s, teclas `[` `]`) —
      desplaza visualización, navegación y el audio/imagen de la tarjeta
- [x] **Reproducción condensada** (tecla `K`) — salta los huecos sin diálogo
- [x] **Recorte de silencio del audio** de tarjeta — ffmpeg `silenceremove`
      (VAD por umbral, sin dependencias nuevas), opt-in en ⚙️
- [x] **Voz neural (TTS)** con **Piper** (ONNX, sin torch) para la pronunciación
      del popup 🗣, en catalán y francés; degrada a espeak. Elegí Piper sobre
      Matcha por ser torch-free, rápido (~0.1 s) y cubrir ambos idiomas.
- [x] **Overlay de ayuda de atajos** (tecla `?`) — modal con el keymap actual
      (remapeable) + teclas fijas, se cierra con Esc/clic fuera.
- [x] **Estilos de subtítulo por estado** — ya existían: los tokens se subrayan/
      colorean por estado (nueva=rojo, aprendiendo=ámbar, seguir=violeta,
      ignorada=atenuada) en el overlay y el navegador.

## 🟢 Nice-to-have

- [x] **Tablas de conjugación** — botón 📖 en el popup de un verbo (catalán) abre
      un modal con la conjugación completa, derivada *offline* del diccionario de
      formas (tags LanguageTool); prefiere la variante central sobre valenciana/balear.
- [x] **Importar diccionarios propios** (StarDict/Yomitan) con `pyglossary` — se
      vuelcan a sqlite y sus definiciones salen en el popup (📕). Import/lista/
      quitar en ⚙️ → Diccionarios propios (por ruta local, app de escritorio).
- [x] **UI multi-idioma** (es/ca/en) — sistema i18n ligero (`i18n.js`: `t()` +
      `data-i18n`/`-ph`/`-title`) y selector en ⚙️. Traducida la interfaz
      persistente: cabecera, portada, primeros pasos, reproductor, panel de
      tarjeta, estados, y todo el panel de ajustes (secciones, etiquetas,
      descripciones) + títulos de modales. *Pendiente incremental*: cadenas
      dinámicas (toasts, insignias de las tarjetas de sesión, checklist de
      onboarding, contenido de stats, nombres de atajos).
- [ ] Modo lectura (texto/EPUB) estilo Lute/VocabSieve — *no seleccionado*
- [ ] Forvo (audio de hablantes reales) como fuente de pronunciación
- [ ] `py-fsrs` — *evaluado*: Anki ya hace el SRS; aportaría poco sin registro
      de repasos propio. Diferido.
- [ ] `sentry-sdk` opt-in (off por defecto) para reporte de errores entre amigos


## ✅ Reanudar + búsqueda (v0.9.12)

- [x] **Reanudar donde lo dejaste** — cada sesión guarda su posición (columna
      `resume_pos`, guardado throttled + en pausa/salir/pagehide); al reabrir
      salta ahí (si >5 s y no al final) con aviso, y las tarjetas muestran una
      barra de progreso violeta.
- [x] **Búsqueda en subtítulos** de toda la biblioteca — buscador en la portada,
      acento-insensible (`cami`→`camí`), agrupado por video con tiempo y término
      resaltado; un clic abre la sesión y salta a esa línea. i18n es/ca/en.


## ✅ Streaming HLS multiplataforma (v0.9.13)

- [x] **Soporte HLS (.m3u8)** — antes la app rechazaba todo lo que no fuera un
      mp4 progresivo (solo YouTube 360p / 3cat 576p). Ahora, si no hay
      progresivo, cae al manifiesto HLS: reproducible en cualquier plataforma
      (Safari/WKWebView nativo; Chrome/Firefox/Android con **hls.js** vendido en
      `/vendor`, cargado solo si hace falta y bajo la CSP de la PWA). Enlaces
      directos `.m3u8` funcionan pegándolos en «Ver online». El corte de audio
      de las tarjetas (ffmpeg) también lee HLS.
- [x] Mejor mensaje de error cuando yt-dlp no soporta un sitio.
- Nota: sitios que cargan el stream con un reproductor propio ofuscado (muchos
  agregadores) siguen sin funcionar — no hay stream que extraer y no se
  construyen scrapers a medida para ellos.

## Notas

- **Empaquetado**: el modelo local-completo (CTranslate2 + Whisper + ~3 GB) es
  difícil de empaquetar bonito multiplataforma; el **modo compartir/Tailscale**
  evita ese infierno sirviendo desde tu Mac. BeeWare Briefcase queda como
  alternativa futura si se quiere instalador nativo (macOS necesita cuenta Apple
  Developer de pago para firmar/notarizar).
- **Legal**: descargar/streamear para uso personal es zona gris; la herramienta
  se comparte con aviso de "solo uso personal/educativo". Licencias de modelos
  (AINA Apache-2.0, Softcatalà MIT, Apertium GPL, Matcha MPL-2.0) compatibles.

## 🔍 Revisión Fable (jul 2026) — aplicada en v0.9.11

Los 18 hallazgos de la revisión de código profunda, corregidos:

- **C1** Gate de invitados: con el modo compartir, la red solo estudia — importar
  rutas del disco, settings, descargas, transcribir y parar el compartir dan 403
  fuera de localhost. Verificado en vivo desde la LAN.
- **C2** XSS por título de sesión / diccionario: `esc()` en todas las
  interpolaciones de `innerHTML` (títulos, acepciones, glosas, ejemplos, calidades).
- **I1/I2** Concurrencia SQLite: lock global de escritura en `db.py`,
  relectura del transcript dentro del lock en `_segment_es`, `_flush` de un solo
  vuelo (dos hilos ya no marcan duplicada una tarjeta recién enviada).
- **I3** Auto-pausa sin rebote (al reanudar cruza a la frase siguiente) y la
  barra de seek ya no devuelve al segmento anterior.
- **I4** Service worker: `ignoreSearch` (los assets llevan `?v=`) — el arranque
  offline ya no muere tras actualizar.
- **I5** Timeouts de ffmpeg/ffprobe (una URL caducada colgaba la biblioteca).
- **I6** Capa de datos multi-idioma de verdad: las sesiones y tarjetas graban su
  idioma, la biblioteca filtra por el activo y el sync de Anki ya no cruza idiomas.
- **I7** `segment_index` validado (un índice negativo minaba el último segmento).
- **M1-M9** pollJob no se cuelga si el server reinició; el traductor reintenta
  tras fallo transitorio (TTL 60 s); GC de MEDIA_DIR al arrancar; poda de cachés;
  tipos validados en settings; nombre de subida saneado; anti DNS-rebinding
  (Host 421); help-line dinámica según keymap; sync con Anki cada 10 min + focus;
  badge de streaming ya no dice «En vivo».

Pendiente menor: roles ARIA en los badges del header (a11y).
