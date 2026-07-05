# CatalàMiner v0.6.0 — Minería fluida, diccionario robusto, métricas y app de escritorio

**Fecha:** 2026-07-05
**Estado:** APROBADO por el usuario (decisiones: duplicados = crear igualmente; escritorio = pywebview + .app)
**Objetivo:** Eliminar la fricción del flujo de minado (hover + tarjetas en segundo plano), arreglar la lematización/diccionario (caso «Ets»), corregir el salto al inicio con A/D, añadir panel de métricas y convertir la app en aplicación de escritorio macOS.

---

## 1. Resumen de problemas y adiciones

| # | Problema / petición | Causa raíz encontrada |
|---|---|---|
| 1 | Crear tarjeta exige confirmar en un panel | Flujo preview → panel → enviar diseñado para edición manual |
| 2 | «Ets» sale como `et · NOUN` con acepción «ETS» y sin traducción | (a) spaCy `sm` lematiza mal formas con mayúscula inicial; (b) la búsqueda superficial tapa la del lema (acrónimo ETS del bidix); (c) el traductor neural trata «Ets» como nombre propio |
| 3 | A/D a veces salta al inicio del video | En huecos entre subtítulos `CUR = -1` y el código hace `CUR < 0 ? 0 : CUR±1` → segmento 0 |
| 4 | Popup al hover (no clic) + pausa durante el hover | Hoy el popup solo abre con clic; hover solo alimenta atajos de teclado |
| 5 | Popup visualmente como el de Migaku (captura del usuario) | — |
| 6 | Tarjetas multi-palabra (crítica a Migaku) | Ya soportado por selección de arrastre; conservar y verificar con el nuevo popup |
| 7 | Panel de métricas transparente (crítica a Migaku: «caja negra») | No existe vista de estadísticas |
| 8 | Funcionar como software, no «abrir localhost» | Solo existe run.sh + navegador |

Verificado en vivo (2026-07-05): `lookup("Ets")` → lema `et` NOUN, senses `[ETS n]`, word_es `Ets`; `lookup("ets")` → lema `ser` AUX, word_es `eres` pero senses siguen siendo `[ETS n]` por la prioridad superficial. El bidix sí contiene `ser → ser/estar`, `gos → perro`, etc.

## 2. Diccionario y lematización robusta

### 2.1 Nueva pieza: diccionario de formas de Softcatalà (LanguageTool)

- Fuente: `https://raw.githubusercontent.com/Softcatala/catalan-dict-tools/master/resultats/lt/diccionari.txt` (37 MB, 1 288 806 líneas, formato `forma lema ETIQUETA` — verificado: `ets ser VSIP2S00`).
- Descarga única a `MODELS_DIR` (mismo patrón que el bidix) y **volcado a SQLite** (`forms.sqlite`: tabla `forms(form, lemma, pos)` con índice por `form`) para consulta O(1) sin cargar ~300 MB en RAM. Construcción one-shot ≈ segundos, lazy en el primer uso; `install.sh` puede pre-descargarla.
- Nuevo módulo `app/forms.py`: `lookup(form) -> list[(lemma, pos_letra)]` probando forma exacta y luego minúscula; mapeo de etiqueta LT → POS legible (V→VERB, N→NOUN, NP→PROPN, A→ADJ, R→ADV, D→DET, P→PRON, C→CONJ, S→ADP, I→INTJ, M/Z→NUM); `is_proper(form)` = existe solo capitalizada (etiqueta NP).

### 2.2 Corrección de lemas en `nlp.tokenize()`

Para cada token palabra:
1. `cands = forms.lookup(token)` (exacta, luego minúscula). Sin candidatos → se queda el lema de spaCy (comportamiento actual).
2. Si el lema de spaCy ∈ candidatos → se mantiene (spaCy ya desambiguó por contexto).
3. Si no, gana el candidato cuyo POS casa con el de spaCy (VERB≈AUX); sin coincidencia → primer candidato.

Ejemplo: «Ets» → spaCy dice `et` ∉ {ser} → corrige a `ser` VERB. `analyze_selection()` hereda la corrección al usar `tokenize()`.

### 2.3 Re-tokenización de sesiones existentes

- Columna nueva `sessions.tok_version INTEGER DEFAULT 0` (migración `ALTER TABLE` tolerante en `db.connect`).
- Constante `nlp.TOK_VERSION = 1`. Al abrir una sesión (`GET /api/sessions/{sid}`), si `tok_version < TOK_VERSION` y hay transcripción: re-tokenizar cada segmento a partir de `text` (conservando `start`, `end`, `logprob`, `text_es`) y guardar con la versión nueva. Coste único por sesión (~1-3 s).
- Estados marcados sobre lemas antiguos erróneos quedan huérfanos (sin migración automática; el usuario re-marca al vuelo). Documentado, aceptado.

### 2.4 Prioridad de búsqueda de acepciones

En `/api/lookup` y preview de tarjeta:
- **Palabra única:** `bidix(lema corregido)` → `bidix(lema spaCy)` → `bidix(forma superficial)`. («ets» pasa a mostrar *ser/estar*, no «ETS».)
- **Multi-palabra (EXPR):** forma superficial primero (el bidix tiene entradas multi-palabra), luego unión de lemas.

### 2.5 Traducción de palabra y de frase con mayúscula inicial

- `word_es`: si la forma exacta no está en el dicc. de formas pero su minúscula sí (⇒ no es nombre propio), traducir la minúscula → «ets» → «eres» (conserva conjugación). Si el resultado == entrada (sin traducir), reintentar con el lema.
- `sentence_es` (nueva `translate.sentence()` usada por lookup, preview y subtítulo dual): si la primera palabra va capitalizada, no es nombre propio según el dicc. de formas, y la traducción la deja idéntica → reintentar con la frase decapitalizada y recapitalizar el resultado. («Ets molt intel·ligent» → «Eres muy inteligente».)

### 2.6 Desambiguación de acepción por contexto (WSD ligero)

Ya traducimos la frase completa: si el texto ES de alguna acepción del bidix aparece (por lema/palabra, case-insensitive) en `sentence_es`, esa acepción se marca `active` en la respuesta, se preselecciona visualmente en el popup y es la `paraula_es` por defecto de la tarjeta automática. Fallbacks: coincidencia con `word_es` → primera acepción.

## 3. Minado en segundo plano

- Nuevo endpoint `POST /api/cards/mine` = preview (audio + fotograma + clip GIF + traducciones) **+ creación + flush a Anki** en una llamada. Body: `{session_id, segment_index, selection, paraula_es?}` (esta última cuando el usuario clicó una acepción). Respuesta: `{sent_now, pending, word_status, lema, paraula}`.
- Frontend: `Q`, botón «➕ Crear tarjeta» y clic en acepción → llamada fire-and-forget **sin pausar el video y sin panel**. Toasts: «⛏️ Creando tarjeta…» → «✅ “ets” → Anki» / «🕓 “ets” en cola (Anki cerrado)».
- **Duplicados: crear igualmente** (decisión del usuario). Anki rechaza solo los idénticos (ya gestionado por `mark_card_duplicate`); el coloreado por estado (naranja = aprendiendo) ya avisa pasivamente de lemas minados.
- El panel de edición **se conserva** para casos manuales: `Shift+Q` o botón ✏️ del popup → flujo actual preview → panel (con ⏪+/+⏩ de padding de audio y campos editables). `Enter` en el panel sigue enviando.

## 4. Navegación A/D correcta

- `d`/`→`/⏭: ir al primer segmento con `start > currentTime + ε`. Si no hay, no moverse.
- `a`/`←`/⏮: si `CUR >= 0` → segmento `CUR-1` (comportamiento actual); si `CUR = -1` (hueco) → último segmento que terminó antes de `currentTime` (clamp a 0). **Nunca** saltar al segmento 0 salvo que corresponda.
- Aplica igual a los botones de la barra. La auto-pausa no cambia.

## 5. Popup estilo Migaku: hover + rediseño

### 5.1 Comportamiento hover

- `mouseenter` sobre token (overlay y navegador lateral): tras ~180 ms se abre el popup **y se pausa el video** (recordando si estaba reproduciéndose).
- `mouseleave`: gracia de ~250 ms; si el puntero entra al popup, sigue abierto (para clicar acepciones/estados/botones); al salir de ambos se cierra y **se reanuda** solo si la pausa la causó el hover y el usuario no tocó play/pausa entretanto.
- Clic en token = **fijar** el popup (no se autocierra ni reanuda); selección por arrastre de varias palabras = popup fijado de la expresión (tarjetas multi-palabra intactas). `Esc`/✕/clic fuera cierran.
- Caché de lookups en cliente (clave `segIndex:selection`) — repetir hover es instantáneo. `/api/lookup` acepta `session_id`/`segment_index` opcionales para reutilizar/rellenar la caché `text_es` del segmento en vez de retraducir la frase en cada hover.

### 5.2 Rediseño visual (referencia: captura Migaku del usuario)

- **Cabecera:** palabra grande + **IPA** `/əts/` gris al lado (ver 5.3) + ✕.
- **Chip de nivel:** zipf → 5 niveles con estrella («Frecuente ★3»), sustituye el texto plano `common (zipf 5.2)`.
- **Fila de iconos:** 🔊 repetir (S) · ➕ crear tarjeta (Q) · ✏️ editar y crear (Shift+Q) — botones circulares estilo Migaku con tooltip.
- **Bloque de contexto:** `sentence_es` en primer plano + frase CA original en cursiva atenuada debajo (orden Migaku: traducción arriba).
- **Acepciones:** chips clicables (crean tarjeta con esa acepción); la acepción `active` del WSD resaltada.
- **Pie:** `lema → word_es` + pastillas de estado (Nueva/Aprendiendo/Conocida/Ignorar) compactas tipo «DESCONOCIDA» de Migaku, la actual destacada.
- Mantener CSS vanilla (night-studio), sin librerías.

### 5.3 Pronunciación IPA (opcional, degradación elegante)

- `espeak-ng` (brew) vía subprocess: `espeak-ng -q --ipa -v ca <palabra>`, caché en memoria + endpoint incluido en la respuesta de `/api/lookup` (campo `ipa`, `""` si espeak-ng no está instalado → el frontend oculta el hueco). Añadir a `install.sh` (`brew install espeak-ng`, tolerante a fallo).

## 6. Panel de métricas 📊 (anti «caja negra»)

- Botón «📊 Estadísticas» en la cabecera → vista overlay/página.
- **Endpoint `GET /api/stats`** que agrega:
  - **Local (SQLite):** total de tarjetas minadas; minadas por mes (para gráfico de barras); distribución de estados de palabra (donut); nº de sesiones y % comprensión medio.
  - **Anki (AnkiConnect, si está abierto):** sobre el mazo configurado — retención real = `1 − Σlapses/Σreps` (de `cardsInfo`), tarjetas a repasar hoy / próximos 7 días / próximos 30 (consultas `findCards` con `prop:due`). Si Anki está cerrado: sección local visible + aviso «abre Anki para ver retención y pronóstico».
- Gráficos **SVG generados en JS vanilla** (barras mensuales, donut de estados, barras de pronóstico). Sin dependencias.
- Fórmulas visibles en tooltips (transparencia: el usuario sabe qué significa cada número).

## 7. App de escritorio macOS (pywebview + .app)

- Dependencia nueva: `pywebview` (usa WKWebView vía pyobjc). Nuevo `app/desktop.py`: arranca uvicorn en un hilo, abre `webview.create_window("CatalàMiner", "http://127.0.0.1:8977", …)`; al cerrar la ventana muere el servidor.
- Script `make-app.sh`: genera `~/Applications/CatalàMiner.app` (bundle mínimo `Contents/MacOS/launcher` shell → `exec .venv/bin/python -m app.desktop`, `Info.plist`, icono `.icns` simple). Doble clic = app con icono en Dock, sin navegador ni terminal.
- `run.sh` (navegador) se mantiene como alternativa/fallback.
- **Ajuste requerido:** WKWebView no soporta `window.prompt()` → sustituir el diálogo del puerto de AnkiConnect por un mini-diálogo HTML propio (input + aceptar/cancelar). El fullscreen ya tiene fallback `fake-fs`.
- Riesgo conocido: reproducción de video en WKWebView limitada a códecs Safari (h264/hevc); los mkv ya se remuxan a mp4 al importar, mismo comportamiento que Safari.

## 8. Orden de implementación propuesto

1. Fix A/D (bug puntual, sin dependencias). 
2. Diccionario/lematización (forms.py, tokenize, lookup, traducciones, re-tokenización, WSD).
3. Minado en segundo plano (`/api/cards/mine` + atajos).
4. Popup hover + rediseño Migaku + IPA.
5. Panel de métricas.
6. App de escritorio (pywebview + make-app.sh + diálogo propio).

Cada fase con tests (pytest para backend: forms, prioridad de acepciones, decapitalización, mine endpoint, stats) y verificación manual en el navegador con las herramientas de preview.

## 9. Criterios de aceptación

- Hover sobre «Ets» en «Ets molt intel·ligent, tu.» muestra: lema `ser` VERB, acepciones *ser/estar*, `word_es` «eres», frase «Eres muy inteligente, tú.», IPA si espeak-ng está instalado — sin tocar el ratón más que el hover, con el video pausado, y al salir el video continúa.
- `Q` con el ratón sobre una palabra crea la tarjeta sin panel y sin pausar; el toast confirma envío o cola; `Shift+Q` abre el panel de edición.
- A/D nunca saltan al segmento 0 desde mitad del video (probado en huecos entre subtítulos).
- Seleccionar «poc a poc» arrastrando crea tarjeta de la expresión completa.
- «📊 Estadísticas» muestra minadas/mes, estados, retención y carga futura con Anki abierto; sin Anki muestra la parte local.
- Doble clic en `CatalàMiner.app` abre la ventana nativa con la app funcional (video, minado, Anki) sin navegador.
