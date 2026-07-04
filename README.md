# 🐈 CatalàMiner

Minero local de flashcards estilo **Migaku** para aprender catalán desde español.
Transcribe video/audio en catalán (Whisper large-v3 afinado para catalán), muestra los
subtítulos palabra a palabra, y de un clic crea tarjetas de Anki con:

- 🔊 audio del segmento (recortado con ffmpeg)
- 🖼️ fotograma del video
- 📝 frase en catalán + traducción neural al español (Softcatalà, offline)
- 📖 palabra objetivo con lema, POS, acepciones del diccionario Apertium y frecuencia

Todo corre **100% local** — sin cuentas, sin APIs de pago.

## Instalación

```bash
./install.sh
```

Requiere [Homebrew](https://brew.sh). El script instala `uv`, `ffmpeg`, crea el venv
(Python 3.12), descarga el traductor de Softcatalà, el diccionario y el modelo de spaCy.

**Para las tarjetas necesitas Anki:**
1. Instala [Anki](https://apps.ankiweb.net)
2. En Anki: Herramientas → Complementos → Obtener complementos → código `2055492159` (AnkiConnect)
3. Reinicia Anki y déjalo abierto mientras minas

Si Anki está cerrado las tarjetas quedan en cola y se envían solas al abrirlo.

## Uso

```bash
./run.sh          # abre http://localhost:8977
```

1. Abre un archivo local (mp4/mkv/mp3…) o pega una URL de YouTube.
2. Pulsa **🎙️ Transcriure** (el modelo catalán ≈3 GB se descarga la primera vez;
   usa `small` si quieres probar rápido). Si el video trae `.srt`/subtítulos de
   YouTube en catalán, puedes usarlos directamente.
3. Clica cualquier palabra del subtítulo (o selecciona una expresión arrastrando).
4. Revisa/edita la tarjeta en el panel y pulsa **⏎**.

**Atajos:** `espacio` play/pausa · `←/→` segmento anterior/siguiente · `a` repetir
segmento · `Esc` cerrar panel · `⏎` enviar tarjeta.

**Colores:** fondo amarillo = palabra ya minada · subrayado punteado = palabra
poco frecuente (rojo) o media (amarillo).

## Solución de problemas

| Problema | Solución |
|---|---|
| "Anki tancat" en el badge | Abre Anki con AnkiConnect instalado; la cola se envía sola |
| El video no se reproduce | Los .mkv se remuxan a mp4 automáticamente al importar |
| Traducciones vacías | Ejecuta `./install.sh` de nuevo (descarga el traductor) |
| Transcripción lenta | Elige el modelo `small` en el selector |

## Arquitectura

FastAPI + SQLite + vanilla JS. Piezas: [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
con [projecte-aina/faster-whisper-large-v3-ca-3catparla](https://huggingface.co/projecte-aina/faster-whisper-large-v3-ca-3catparla),
[softcatala/translate-cat-spa](https://huggingface.co/softcatala/translate-cat-spa) (CTranslate2),
bidix de [apertium/apertium-spa-cat](https://github.com/apertium/apertium-spa-cat),
spaCy `ca_core_news_sm`, wordfreq, yt-dlp, AnkiConnect.

Datos en `~/Library/Application Support/CatalaMiner/`.
