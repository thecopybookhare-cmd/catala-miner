# CatalàMiner — Especificación de diseño

**Fecha:** 2026-07-04
**Estado:** BORRADOR (pendiente de aprobación del usuario)
**Objetivo:** Aplicación local estilo Migaku para minar flashcards de Anki desde video/audio en catalán, con traducción contextual catalán→español 100% offline.

---

## 1. Resumen

Una aplicación web local (servidor en `http://localhost:8977`, se abre en el navegador) que:

1. Carga un video/audio local o descarga uno de YouTube (yt-dlp).
2. Lo transcribe localmente con faster-whisper (o usa un `.srt` existente si lo hay).
3. Muestra reproductor de video + subtítulos sincronizados y clicables.
4. Permite seleccionar una palabra o expresión de cualquier subtítulo y crear una flashcard con: audio del segmento, fotograma del video, frase en catalán, traducción de la frase al español, palabra/expresión objetivo y su traducción en contexto.
5. Envía la tarjeta a Anki vía AnkiConnect con los media incluidos.

Todo funciona offline (salvo la descarga de YouTube, obviamente).

## 2. Stack técnico

| Pieza | Herramienta | Rol |
|---|---|---|
| Backend | Python 3.11+ / FastAPI + Uvicorn | Servidor local, orquesta todo |
| Transcripción | faster-whisper (modelo `small` por defecto, configurable) | Igual que SubSmith |
| Media | ffmpeg (CLI) | Extraer audio de tarjeta, fotogramas, conversión |
| YouTube | yt-dlp (librería Python) | Descarga de videos |
| Traducción | Apertium par `cat-spa` | Frase completa en contexto + consulta del bidix para acepciones |
| Anki | AnkiConnect (HTTP a `localhost:8765` de Anki → puerto 8765 es el de AnkiConnect; **nuestra app usará el puerto 8977** para no colisionar) | Alta de notas con media |
| Datos | SQLite (`app.db`) | Sesiones, transcripciones, tarjetas creadas |
| Frontend | HTML/CSS/JS vanilla (una sola página), servido por FastAPI | Reproductor + subtítulos + editor de tarjeta |

**Corrección de puerto:** AnkiConnect ocupa el 8765. Nuestra app servirá en **`http://localhost:8977`**.

## 3. Flujo de usuario

### 3.1 Cargar contenido
- Pantalla inicial: lista de sesiones anteriores + botón "Nuevo" (elegir archivo local o pegar URL de YouTube).
- Si hay `.srt`/`.vtt` junto al video (mismo nombre) o subtítulos en catalán en YouTube, se ofrecen como alternativa a transcribir.
- Transcripción muestra barra de progreso (WebSocket o polling).

### 3.2 Pantalla de minado (la principal)
- **Arriba:** reproductor `<video>` HTML5 (los formatos no compatibles con el navegador, p. ej. mkv, se remuxan/transcodifican a mp4 con ffmpeg al importar).
- **Abajo:** lista de segmentos de subtítulo con auto-scroll sincronizado; el segmento actual resaltado; clic en un segmento → el video salta ahí.
- Atajos: espacio (play/pausa), ←/→ (segmento anterior/siguiente), `a` (repetir segmento actual).
- Las palabras ya minadas en sesiones anteriores aparecen marcadas (amarillo, estilo Migaku).

### 3.3 Crear tarjeta
1. El usuario selecciona con el ratón una palabra o expresión dentro de un segmento.
2. Panel lateral de tarjeta se rellena automáticamente:
   - **Frase (ca):** el segmento completo.
   - **Frase (es):** traducción Apertium de la frase entera (contextual por reglas de transferencia).
   - **Palabra (ca):** la selección.
   - **Palabra (es):** traducción Apertium de la expresión seleccionada + lista de acepciones alternativas extraídas del diccionario bilingüe (bidix) de Apertium, seleccionables con un clic.
   - **Audio:** recorte del segmento con ffmpeg (±250 ms de margen; botón para ampliar a segmento anterior/siguiente si la frase quedó cortada).
   - **Imagen:** fotograma del punto medio del segmento (jpg, ~640px de ancho).
   - **Fuente:** nombre del video + timestamp.
3. Todos los campos son editables antes de enviar.
4. Botón "Añadir a Anki" (o atajo `Enter`).

### 3.4 Envío a Anki
- Al primer uso, la app crea vía AnkiConnect el note type **"CatalaMiner"** con campos: `Paraula`, `ParaulaES`, `Frase`, `FraseES`, `Audio`, `Imatge`, `Font` — y una plantilla de tarjeta limpia (palabra delante; detrás frase, traducciones, imagen y audio).
- El usuario elige el mazo destino (dropdown con los mazos existentes; se recuerda el último).
- Audio e imagen se envían con `storeMediaFile` y se referencian en la nota.
- **Si Anki está cerrado o AnkiConnect no responde:** la tarjeta se guarda en cola local (tabla `pending_cards`) y se reintenta automáticamente; indicador visible de "N tarjetas en cola".

## 4. Traducción en contexto — detalle

- **Frase:** `apertium cat-spa` sobre el segmento completo. Apertium desambigua morfológicamente y aplica reglas de transferencia — la traducción es contextual, no palabra a palabra.
- **Palabra/expresión:**
  1. Se traduce la selección aislada con Apertium (maneja bien multipalabras del bidix).
  2. Se consulta el bidix (`apertium-cat-spa.cat-spa.dix`) para listar acepciones alternativas del lema — equivalente al popup de diccionario de Migaku.
  3. El usuario puede elegir otra acepción o editar a mano.
- **Fallback futuro (fuera de alcance v1):** botón "re-traducir con LLM/API" para frases donde Apertium falle. Se deja el hook en el código pero sin implementar.

## 5. Datos

```sql
sessions(id, title, source_type,        -- local | youtube
         media_path, srt_source,        -- whisper | srt | youtube_subs
         language, model_size, duration_secs,
         transcript_json, created_at, updated_at)

cards(id, session_id, segment_index,
      paraula, paraula_es, frase, frase_es,
      audio_file, image_file, font,
      anki_note_id,                     -- NULL si aún en cola
      status,                           -- sent | pending
      created_at)
```

- Base de datos y media en `~/Library/Application Support/CatalaMiner/` (`app.db`, `media/`, `downloads/` para YouTube).
- `cards.paraula` alimenta el marcado amarillo de palabras ya minadas (v1: comparación por forma exacta, case-insensitive; lematización queda para v2 — ver §8).

## 6. Manejo de errores

| Fallo | Comportamiento |
|---|---|
| Apertium no instalado / par ausente | Aviso claro al arrancar con instrucción de instalación; la app funciona sin traducción (campos vacíos editables) |
| Traducción falla en una frase | Campo vacío + editable; nunca bloquea la tarjeta |
| Anki cerrado | Cola local con reintento; indicador en UI |
| ffmpeg falla en recorte | Error visible en el panel; la tarjeta puede enviarse sin audio |
| Transcripción de baja confianza | Segmentos con `avg_logprob` bajo marcados visualmente (gris/cursiva) |
| Video no reproducible en navegador | Remux/transcodificación automática a mp4 al importar |

## 7. Instalación y arranque

- Script `install.sh`: crea venv, `pip install` dependencias, verifica/instala ffmpeg y Apertium (brew), descarga el par cat-spa, verifica AnkiConnect.
- Script `run.sh` (y alias): levanta el servidor y abre el navegador.
- README con pasos manuales por si el script falla.

## 8. Fuera de alcance (v1)

- Netflix/streaming en vivo (Migaku lo hace con extensión de navegador — otra liga).
- Lematización avanzada para el marcado de palabras conocidas (v1: forma exacta).
- SRS propio — Anki se encarga.
- Otros pares de idiomas (la arquitectura lo permitirá, pero v1 es cat→spa fijo).
- Fallback LLM/API para traducción (hook preparado, sin implementar).

## 9. Criterios de éxito

1. De un video en catalán (local o YouTube) a una tarjeta en Anki con audio reproducible, imagen, frase y traducciones correctas, en menos de 30 segundos de interacción por tarjeta.
2. Todo offline tras la instalación.
3. La traducción de frase es contextual (verificable con frases con pronoms febles: "n'hi ha", "se'n va"...).
4. Flujo probado de punta a punta con un video real en catalán.

## 10. Verificación

- Test de humo automatizado: transcribir un clip corto, crear tarjeta vía API, verificar ficheros de media generados y nota en Anki (con AnkiConnect de prueba o mock).
- Prueba manual guiada con el usuario al final.
