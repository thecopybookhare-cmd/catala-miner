# CatalàMiner — Roadmap

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

## 🟡 Siguiente (alto valor)

- [ ] **TTS catalán natural** (Matcha / projecte-aina, ONNX offline) — sustituye
      al espeak robótico en la pronunciación de las tarjetas
- [ ] **Overlay de ayuda de atajos** (tecla `?`)

## 🟢 Nice-to-have

- [ ] Modo lectura (texto/EPUB) estilo Lute/VocabSieve
- [ ] Tablas de conjugación en el popup (conjugador de Softcatalà)
- [ ] Importar diccionarios StarDict/Yomitan (`pyglossary`)
- [ ] Estilos de subtítulo por estado (color/subrayado/contorno)
- [ ] Forvo (audio de hablantes reales) como fuente de pronunciación
- [ ] UI multi-idioma (interfaz en catalán/inglés, hoy solo español)
- [ ] `py-fsrs` — *evaluado*: Anki ya hace el SRS; aportaría poco sin registro
      de repasos propio. Diferido.
- [ ] `sentry-sdk` opt-in (off por defecto) para reporte de errores entre amigos

## Notas

- **Empaquetado**: el modelo local-completo (CTranslate2 + Whisper + ~3 GB) es
  difícil de empaquetar bonito multiplataforma; el **modo compartir/Tailscale**
  evita ese infierno sirviendo desde tu Mac. BeeWare Briefcase queda como
  alternativa futura si se quiere instalador nativo (macOS necesita cuenta Apple
  Developer de pago para firmar/notarizar).
- **Legal**: descargar/streamear para uso personal es zona gris; la herramienta
  se comparte con aviso de "solo uso personal/educativo". Licencias de modelos
  (AINA Apache-2.0, Softcatalà MIT, Apertium GPL, Matcha MPL-2.0) compatibles.
