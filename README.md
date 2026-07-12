# 🐈 CatalàMiner

![CI](https://img.shields.io/badge/CI-passing-brightgreen) ![license](https://img.shields.io/badge/license-MIT-blue) ![version](https://img.shields.io/badge/version-0.9.16-8b7cf8) ![python](https://img.shields.io/badge/python-3.12-3776ab)

Minero local de flashcards estilo **Migaku** para aprender catalán desde español.
Transcribe video/audio en catalán (Whisper large-v3 afinado para catalán), muestra los
subtítulos palabra a palabra, y de un clic crea tarjetas de Anki con:

- 🔊 audio del segmento (recortado con ffmpeg)
- 🖼️ fotograma del video
- 📝 frase en catalán + traducción neural al español (Softcatalà, offline)
- 📖 palabra objetivo con lema, POS, acepciones del diccionario Apertium y frecuencia

Todo corre **100% local** — sin cuentas, sin APIs de pago.

🇫🇷 **También francés → español.** Cámbialo en ⚙️ *Ajustes → Idioma*. Al elegir francés
la app usa el traductor OPUS-MT fr→es, spaCy `fr_core_news_sm`, el bidix Apertium fra-spa
y las glosas del Wikcionario en español; se descargan solos la primera vez (o desde el
asistente de primer arranque).

📡 **Compartir con amigos.** En ⚙️ *Ajustes → Compartir* enciendes un servidor bajo demanda
en tu red local o [Tailscale](https://tailscale.com), con enlace + código QR para que un
amigo (o tu móvil) la use en el navegador. Es una **PWA instalable** (icono en pantalla,
arranque offline del shell). Nada se expone hasta que lo activas; el acceso es completo, así
que compártela solo con gente de confianza en tu red privada.

## Instalación

Cada persona instala **su propia copia** — no hace falta que nadie la hospede. No
necesitas instalar Python ni ffmpeg a mano: el instalador trae `uv` (que aporta
Python) y `ffmpeg` lo aporta `static-ffmpeg` solo si falta.

### Un solo comando (clona + instala)

**macOS / Linux** (en una terminal):
```bash
curl -LsSf https://raw.githubusercontent.com/thecopybookhare-cmd/catala-miner/main/bootstrap.sh | bash
```
**Windows** (en PowerShell):
```powershell
irm https://raw.githubusercontent.com/thecopybookhare-cmd/catala-miner/main/bootstrap.ps1 | iex
```
Clona el repo en `~/CatalaMiner` y lo instala todo. *(Requiere que el repo sea
**público**; mientras sea privado, usa los pasos manuales de abajo.)*

### Manual (si ya tienes la carpeta del proyecto)

**macOS / Linux**
```bash
./install.sh        # instala todo y, en Mac, crea CatalàMiner.app
./run.sh            # o abre CatalàMiner.app (Mac)
```

**Windows** (PowerShell, en la carpeta del proyecto)
```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
.\run.bat
```

El instalador crea el venv (Python 3.12), descarga el traductor de Softcatalà, el
diccionario y el modelo de spaCy. El modelo Whisper catalán (~3 GB) se baja solo la
primera vez que transcribes. Datos de la app en la carpeta estándar de tu SO
(`Application Support` en Mac, `AppData\Roaming` en Windows, `~/.local/share` en Linux).

**Para las tarjetas necesitas Anki:**
1. Instala [Anki](https://apps.ankiweb.net)
2. En Anki: Herramientas → Complementos → Obtener complementos → código `2055492159` (AnkiConnect)
3. Reinicia Anki y déjalo abierto mientras minas

Si Anki está cerrado las tarjetas quedan en cola y se envían solas al abrirlo.

## Uso

```bash
./run.sh          # modo navegador: abre http://localhost:8977
```

**Ventana de escritorio:** en macOS, `./make-app.sh` crea `~/Applications/CatalàMiner.app`
(ventana nativa WKWebView, icono en el Dock). En Windows/Linux, `python -m app.desktop`
abre una ventana propia si hay motor webview (WebView2 / GTK); si no, cae al navegador
automáticamente. El modo `./run.sh` / `.\run.bat` siempre funciona.

**Compartir sin que cada uno instale:** si prefieres que un amigo la use sin instalar
nada, activa ⚙️ → *Compartir* y comparte el enlace (misma red o Tailscale) — pero para
que **cada uno tenga su copia independiente**, que instale con los pasos de arriba.

1. Abre un archivo local (mp4/mkv/mp3…), o pega una URL de **YouTube / 3cat / enlace
   directo** y pulsa **«🔗 Ver online»**: se reproduce en streaming al instante (yt-dlp
   resuelve el mejor formato progresivo; 3cat hasta 576p, YouTube 360p) y las tarjetas
   cortan audio+imagen desde la URL, sin descargar. Selector de calidad + auto-bajada si
   se atasca. Para HD offline, **⬇️ Importar** descarga (con barra de progreso real).
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

**📋 Panel «Palabras» (G → pestaña Palabras):** todos los lemas del video por bandas de
frecuencia (Rank 1–100, 101–300…). Clic = diccionario; clic derecho = conocida ↔ nueva.
**«Establecer nivel de vocabulario»** marca de un golpe las N palabras más frecuentes del
catalán como conocidas (sin pisar lo que ya marcaste). Los subtítulos de YouTube usan los
oficiales o los **automáticos** (etiqueta «Subs auto YouTube») antes de recurrir a Whisper.
El popup añade **glosas del Wikcionario** (offline, ~4 MB, descarga única). La DB se
respalda a diario en `backups/` (7 copias). Arquitectura preparada para más idiomas.

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

Multi-idioma: los perfiles viven en [`app/languages.py`](app/languages.py). El francés añade
[gaudi/opus-mt-fr-es-ctranslate2](https://huggingface.co/gaudi/opus-mt-fr-es-ctranslate2),
`fr_core_news_sm` y el bidix [apertium/apertium-fr-es](https://github.com/apertium/apertium-fr-es).

Datos en `~/Library/Application Support/CatalaMiner/`.

## Desarrollo

```bash
uv pip install -p .venv/bin/python -e . --group dev
.venv/bin/ruff check app/ tests/     # lint
.venv/bin/python -m pytest tests/    # 113 tests
```

Ver [CONTRIBUTING.md](CONTRIBUTING.md). El CI (GitHub Actions) corre lint + tests en cada push.

## Licencia y uso

Código bajo licencia [MIT](LICENSE) © 2026 Tomás Plaza.

⚠️ **Solo para uso personal y educativo.** La herramienta reproduce contenido de
YouTube/3cat para estudio de idiomas; respeta los derechos de autor y los términos
de cada plataforma. No redistribuyas el contenido descargado.
