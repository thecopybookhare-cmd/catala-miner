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
./run.sh          # modo navegador: abre http://localhost:8977
```

**App de escritorio (macOS):** `./make-app.sh` crea `~/Applications/CatalàMiner.app`
— doble clic la abre en una ventana nativa (WKWebView) con icono en el Dock, sin
navegador ni terminal. `./install.sh` ya la genera al final. El modo `./run.sh` sigue
disponible como alternativa. `espeak-ng` (se instala con `install.sh`) habilita la
pronunciación IPA en el popup.

1. Abre un archivo local (mp4/mkv/mp3…), pega una URL de YouTube (⬇️ descarga)
   o un **enlace directo .mp4/.m3u8 con «🔗 Ver online»** (streaming sin descargar;
   las tarjetas cortan audio e imagen desde la propia URL). HLS (.m3u8) reproduce
   nativo en la app de escritorio/Safari; en Chrome usa mp4 directo.
2. Pulsa **🎙️ Transcriure** (el modelo catalán ≈3 GB se descarga la primera vez;
   usa `small` si quieres probar rápido). Si el video trae `.srt`/subtítulos de
   YouTube en catalán, puedes usarlos directamente.
3. Clica cualquier palabra del subtítulo (o selecciona una expresión arrastrando).
4. Revisa/edita la tarjeta en el panel y pulsa **⏎**.

**Atajos (mapa Migaku):** `A`/`←` frase anterior · `D`/`→` siguiente · `S`/`↓` repetir ·
`Q` crear tarjeta en segundo plano (palabra bajo el cursor o popup abierto) · `⇧Q` abrir el
editor de tarjeta · `1-4` estado de palabra
(1 nueva · 2 aprendiendo · 3 conocida · 4 ignorar) · `W` ocultar subtítulos ·
`Shift+W` ocultar línea ES · `E` dual · `G` navegador de subtítulos · `C` copiar frase ·
`P` auto-pausa · `F` pantalla completa · `espacio` play/pausa · `⏎` enviar tarjeta · `Esc` cerrar.

**⚙️ Configuración:** mazo de Anki, tamaño de subtítulos en vivo, dual/auto-pausa/velocidad
por defecto, IPA, funciones online (Viccionari, off por defecto), **atajos remapeables** y
export/import de palabras conocidas. **⭐ i+1:** el chip cuenta las frases con exactamente
una palabra nueva (las óptimas para minar); `R` salta entre ellas.

**Estados de palabra (colores Migaku):** rojo = desconocida · naranja = aprendiendo
(se marca sola al crear tarjeta) · sin marca = conocida · gris = ignorada · morado = seguimiento.
Los estados se sincronizan con Anki: intervalo ≥ 21 días → conocida. El chip 📊 de la
cabecera muestra el % del contenido que ya conoces.

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
