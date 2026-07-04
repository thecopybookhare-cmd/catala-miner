# CatalàMiner — Especificación de diseño

**Fecha:** 2026-07-04 (rev. 2, tras investigación de ecosistema)
**Estado:** APROBADO por el usuario (rev. 1) + mejoras de investigación incorporadas
**Objetivo:** Aplicación local estilo Migaku para minar flashcards de Anki desde video/audio en catalán, con traducción contextual catalán→español 100% offline.

---

## 1. Resumen

Una aplicación web local (servidor en `http://localhost:8977`, se abre en el navegador) que:

1. Carga un video/audio local o descarga uno de YouTube (yt-dlp).
2. Lo transcribe localmente con faster-whisper usando un **Whisper large-v3 afinado específicamente para catalán** (o usa un `.srt` existente si lo hay).
3. Muestra reproductor de video + subtítulos sincronizados, **tokenizados palabra a palabra** (clicables, con color según estado y badge de frecuencia — estilo Migaku).
4. Al clicar/seleccionar una palabra o expresión crea una flashcard con: audio del segmento, fotograma del video, frase en catalán, traducción neural de la frase al español, palabra objetivo con su traducción en contexto + acepciones de diccionario.
5. Envía la tarjeta a Anki vía AnkiConnect con los media incluidos.

Todo funciona offline tras la instalación (salvo descargas de YouTube).

## 2. Stack técnico (rev. 2 — hallazgos de investigación)

| Pieza | Herramienta | Justificación |
|---|---|---|
| Backend | Python 3.12 (venv gestionado con `uv`) / FastAPI + Uvicorn | Python 3.14 del sistema aún sin wheels para todo el stack ML |
| Transcripción | faster-whisper + **`projecte-aina/faster-whisper-large-v3-ca-3catparla`** | Whisper large-v3 afinado con 710 h de catalán (BSC/Projecte AINA), ya en formato CTranslate2, Apache-2.0. Mejor que large-v3 genérico para catalán. Alternativas seleccionables: `large-v3` genérico, `small` (borrador rápido) |
| Timestamps por palabra | `word_timestamps=True` de faster-whisper | Permite recorte de audio preciso y tokens clicables sincronizados |
| Media | ffmpeg (CLI) | Recorte de audio, fotogramas, remux a mp4 |
| YouTube | yt-dlp | Descarga video + subtítulos oficiales si existen |
| Traducción de frase | **Softcatalà `translate-cat-spa`** (CTranslate2 + SentencePiece, MIT) | Traductor neuronal que usa softcatala.org en producción. Instalación 100% pip (`ctranslate2`, `sentencepiece`) — Apertium no está en Homebrew y compilarlo es doloroso |
| Diccionario de acepciones | **Bidix de `apertium/apertium-spa-cat`** parseado como XML | El diccionario bilingüe ca↔es de Apertium se descarga crudo de GitHub y se parsea con Python — sin instalar Apertium. Popup de acepciones estilo Migaku |
| Tokenización/lemas | **spaCy `ca_core_news_sm`** | Tokens clicables, lematización para marcar palabras conocidas (por lema, no forma exacta), POS para la tarjeta |
| Frecuencia léxica | **`wordfreq`** (soporta catalán) | Badge de frecuencia por palabra (como Migaku) — priorizar qué minar |
| Anki | AnkiConnect (puerto 8765 de Anki) | Alta de notas con media. **Nuestra app usa el puerto 8977** para no colisionar |
| Datos | SQLite (`app.db`) | Sesiones, transcripciones, tarjetas |
| Frontend | HTML/CSS/JS vanilla, una página, servido por FastAPI | Sin build step; referencia de UX: asbplayer (minado por teclado, colores de estado de palabra) |

**Requisitos de máquina verificados:** 16 GB RAM y 244 GB libres — sobra para large-v3 int8 en CPU (Apple Silicon). Anki **no está instalado** actualmente: la guía de instalación incluye Anki + add-on AnkiConnect (código 2055492159).

## 3. Flujo de usuario

### 3.1 Cargar contenido
- Pantalla inicial: lista de sesiones anteriores + botón "Nuevo" (elegir archivo local o pegar URL de YouTube).
- Si hay `.srt`/`.vtt` junto al video (mismo nombre) o subtítulos en catalán en YouTube, se ofrecen como alternativa a transcribir.
- Selector de modelo (por defecto: large-v3 catalán de AINA; opción small para pruebas rápidas).
- Transcripción con barra de progreso (polling del backend); primera vez descarga el modelo (~3 GB, con aviso).

### 3.2 Pantalla de minado (la principal)
- **Arriba:** reproductor `<video>` HTML5 (mkv y similares se remuxan a mp4 con ffmpeg al importar).
- **Abajo:** segmentos de subtítulo con auto-scroll sincronizado; el actual resaltado; clic en segmento → el video salta ahí.
- **Cada palabra es un token clicable** (spaCy) con estilo según estado, como Migaku/asbplayer:
  - **Amarillo:** ya minada (comparación por lema).
  - **Punto de frecuencia:** indicador visual (común / media / rara) vía wordfreq.
- Atajos: espacio (play/pausa), ←/→ (segmento anterior/siguiente), `a` (repetir segmento), `s` (crear tarjeta del segmento sin palabra objetivo).

### 3.3 Crear tarjeta
1. Clic en una palabra (o selección arrastrando para una expresión multi-palabra).
2. Panel lateral se rellena automáticamente:
   - **Frase (ca):** el segmento completo.
   - **Frase (es):** traducción neural Softcatalà de la frase entera (contextual).
   - **Paraula (ca):** la selección + lema y POS (spaCy).
   - **Paraula (es):** traducción de la expresión + **acepciones alternativas del bidix Apertium**, seleccionables con un clic (popup diccionario estilo Migaku).
   - **Frecuencia:** rango wordfreq de la palabra.
   - **Audio:** recorte ffmpeg usando timestamps por palabra (margen ±250 ms; botones para extender a segmento anterior/siguiente).
   - **Imagen:** fotograma del punto medio del segmento (jpg ~640 px).
   - **Font:** nombre del video + timestamp.
3. Todos los campos editables antes de enviar.
4. "Añadir a Anki" (`Enter`).

### 3.4 Envío a Anki
- Al primer uso, la app crea vía AnkiConnect el note type **"CatalaMiner"** con campos: `Paraula`, `ParaulaES`, `Frase`, `FraseES`, `Audio`, `Imatge`, `Font`, `Freq` — plantilla limpia (palabra delante; detrás frase, traducciones, imagen, audio).
- Dropdown de mazo destino (se recuerda el último).
- Media vía `storeMediaFile`.
- **Anki cerrado / AnkiConnect ausente:** cola local (`pending_cards`) con reintento automático e indicador "N en cola".

## 4. Traducción en contexto — detalle

- **Frase completa:** modelo neuronal Softcatalà cat→spa (CTranslate2). Es el mismo motor del traductor de softcatala.org — traducción contextual de calidad de producción.
- **Palabra/expresión:**
  1. Traducción de la selección con el mismo motor neuronal.
  2. Acepciones alternativas consultando el bidix de Apertium (spa-cat) parseado localmente — el usuario elige con un clic si la automática no convence.
  3. Campo siempre editable.
- **Fallback futuro (fuera de alcance v1):** hook para re-traducir con LLM/API.

## 5. Datos

```sql
sessions(id, title, source_type,        -- local | youtube
         media_path, srt_source,        -- whisper | srt | youtube_subs
         language, model_size, duration_secs,
         transcript_json,               -- segmentos + palabras con timestamps
         created_at, updated_at)

cards(id, session_id, segment_index,
      paraula, lema, pos, paraula_es, frase, frase_es,
      freq_rank, audio_file, image_file, font,
      anki_note_id,                     -- NULL si aún en cola
      status,                           -- sent | pending
      created_at)
```

- Datos y media en `~/Library/Application Support/CatalaMiner/` (`app.db`, `media/`, `downloads/`, `models/` cache HF).
- `cards.lema` alimenta el marcado amarillo de palabras ya minadas (por lema vía spaCy; mejora sobre rev. 1 que era forma exacta).

## 6. Manejo de errores

| Fallo | Comportamiento |
|---|---|
| Modelo de traducción no descargado | Aviso al arrancar con botón de descarga; la app funciona sin traducción (campos vacíos editables) |
| Traducción falla en una frase | Campo vacío + editable; nunca bloquea la tarjeta |
| Anki cerrado | Cola local con reintento; indicador en UI |
| ffmpeg falla en recorte | Error visible; la tarjeta puede enviarse sin audio |
| Transcripción de baja confianza | Segmentos con `avg_logprob` bajo en gris/cursiva |
| Video no reproducible en navegador | Remux/transcodificación automática a mp4 al importar |
| spaCy/wordfreq no disponibles | Degradación elegante: subtítulos sin tokenizar (selección manual), sin badges |

## 7. Instalación y arranque

- `install.sh`: instala `uv` (brew) si falta → venv Python 3.12 → `uv pip install` dependencias → verifica ffmpeg (brew si falta) → descarga modelo Softcatalà + bidix Apertium + spaCy ca → deja el modelo Whisper para descarga lazy en primer uso (~3 GB).
- `run.sh`: levanta el servidor y abre `http://localhost:8977`.
- README: pasos manuales + instalar Anki (apps.ankiweb.net) y add-on AnkiConnect (2055492159) — **Anki no está instalado hoy en esta máquina**.

## 8. Fuera de alcance (v1)

- Netflix/streaming en vivo (requiere extensión de navegador — otra liga).
- SRS propio — Anki se encarga.
- Otros pares de idiomas (la arquitectura lo permite; v1 es cat→spa fijo).
- Fallback LLM/API para traducción (hook preparado, sin implementar).
- Estados de palabra multinivel sincronizados desde Anki (asbplayer los tiene; v1 solo marca "ya minada").

## 9. Criterios de éxito

1. De un video en catalán (local o YouTube) a una tarjeta en Anki con audio reproducible, imagen, frase y traducciones correctas, en <30 s de interacción por tarjeta.
2. Todo offline tras la instalación.
3. Traducción de frase contextual y natural (verificable con pronoms febles: "n'hi ha", "se'n va"…).
4. Palabras ya minadas marcadas por lema; badges de frecuencia visibles.
5. Flujo probado de punta a punta con un video real en catalán.

## 10. Verificación

- Test de humo automatizado: transcribir un clip corto, crear tarjeta vía API, verificar media generados y (si Anki está abierto) nota creada; si no, cola pending.
- Prueba manual guiada con el usuario al final.

## Apéndice A — Referencias de la investigación

- Whisper catalán: [projecte-aina/faster-whisper-large-v3-ca-3catparla](https://huggingface.co/projecte-aina/faster-whisper-large-v3-ca-3catparla) (Apache-2.0, 710 h 3CatParla)
- Traductor neuronal: [softcatala/translate-cat-spa](https://huggingface.co/softcatala/translate-cat-spa) (MIT) + [Softcatala/nmt-models](https://github.com/Softcatala/nmt-models)
- Diccionario: [apertium/apertium-spa-cat](https://github.com/apertium/apertium-spa-cat) (GPL-2.0, bidix XML)
- UX de referencia: [asbplayer](https://github.com/killergerbah/asbplayer) (minado por teclado, colores de estado, anotación de frecuencia)
- Motor de subtítulos: [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
