# CatalàMiner v0.8.0 — Panel de vocabulario, progreso visible, subs automáticos, 2º diccionario y multi-idioma

**Fecha:** 2026-07-07
**Estado:** APROBADO por el usuario («vamos con todo»), orden 3→1→2→6→4→5.
**Objetivo:** Marcar vocabulario en masa (estilo Language Reactor), feedback de progreso en subidas/URLs, subtítulos automáticos de YouTube, biblioteca instantánea + backups, acepciones del Wikcionario offline, y arquitectura multi-idioma preparada para el francés.

---

## 3. Panel «Palabras» (Language Reactor)

- El panel lateral (G) gana pestañas: **Subtítulos | Palabras**.
- «Palabras»: lemas únicos del video agrupados por bandas de rango de corpus (Rank 1–100, 101–300, 301–1000, 1001–5000, resto — vía `wordfreq.top_n_list`, servido una vez por `GET /api/vocab/ranks`), coloreados por estado como los tokens. Dentro de cada banda, orden por frecuencia.
- Interacción: **clic izquierdo** → popup de diccionario (fijado); **clic derecho** → alterna conocida ↔ desconocida (toast).
- **«Establecer nivel de vocabulario»**: botón arriba → diálogo con slider (500–5000) «marca como conocidas las N palabras más frecuentes del catalán» → `POST /api/words/bulk-known {top_n}`; el servidor lematiza la lista top-N (dicc. de formas) y marca `known` **solo** lemas sin estado previo (no pisa learning/ignored). Devuelve `{marked}`; la UI refresca estados y chips.

## 1. Progreso visible en subida / URL

- **Subida**: XHR con `upload.onprogress` → barra «Subiendo… NN%». El endpoint guarda el archivo y devuelve `job_id`; el job hace remux (mkv) + ffprobe + alta de sesión con mensajes («convirtiendo…», «analizando…») y el frontend usa el `pollJob` existente.
- **Ver online**: `POST /api/sessions/url` pasa a job («comprobando el enlace…») con el mismo polling.
- YouTube ya tiene job con progreso (se conserva).

## 2. Subtítulos automáticos de YouTube

- `youtube.py`: `writeautomaticsub: True` además de `writesubtitles`. Prioridad: oficiales ca → automáticos ca → sin subs (Whisper manual).
- Etiqueta de origen nueva `youtube_auto` («Subs auto YouTube»).
- Los VTT automáticos de YouTube traen líneas rodantes duplicadas y etiquetas `<c>`: `subs.py` gana una pasada `clean_auto(segs)` (strip de tags + fusión de textos consecutivos idénticos/contenidos).

## 6. Rendimiento y seguridad de datos

- **Biblioteca instantánea**: `_session_meta` deja de releer transcripciones en cada carga — caché en memoria keyed por `(sid, session.updated_at, max(word_status.updated_at))`; una sola lectura de sesión por fila.
- **Backup automático**: al arrancar, `db.backup_daily()` copia `app.db` → `APP_DIR/backups/app-YYYYMMDD.db` (API `sqlite3 backup`, segura con WAL) si no existe la de hoy; conserva las 7 más recientes.

## 4. Segundo diccionario offline (Wikcionario vía kaikki.org)

- Descarga única del extracto JSONL del **Wikcionario español para el catalán** (kaikki.org; URL a validar en vivo durante la implementación — si la extracción es↛ca no existe, degradar a no-disponible sin romper nada).
- `app/wikdict.py`: parsea JSONL → sqlite `wikdict.sqlite` (word → glosas en español, por POS). `lookup(term)` como el bidix.
- Integración: las **glosas** se muestran en el popup bajo las acepciones (bloque de definición offline, sin necesitar el toggle online); las chips del bidix siguen siendo la fuente de `paraula_es`. El campo `senses` gana `src` («apertium»/«wikci») por si la UI quiere distinguir.

## 5. Arquitectura multi-idioma (preparar francés)

- `app/languages.py`: registro de perfiles — por idioma: modelos Whisper, modelo spaCy, repo del traductor, URLs de bidix/formas/wikdict, código wordfreq, voz espeak. Perfil `ca` completo; perfil `fr` **preparado pero inactivo** (traductor fr→es sin validar → no seleccionable).
- Refactor: `config/nlp/translate/forms/dictionary/ipa/wikdict` leen del perfil activo (elegido en `settings.language`, default `ca`); rutas de modelos con sufijo de idioma donde aplique.
- **DB**: `word_status` migra a PK `(lemma, language)` (rebuild + copia con `language='ca'`); todas las consultas filtran por idioma activo. `sessions.language` ya existe.
- UI: selector de idioma en ⚙️ **oculto mientras solo haya un perfil activable**.

## Criterios de aceptación

1. Pestaña «Palabras» lista los lemas por bandas de rango; clic derecho alterna conocida; el slider de nivel marca en masa sin pisar estados previos y actualiza el % del chip.
2. Subir un archivo muestra porcentaje real de subida y estados del job; «Ver online» muestra estado; nada queda «colgado» sin feedback.
3. Un video de YouTube sin subs oficiales ca pero con automáticos queda transcrito sin Whisper, etiquetado «Subs auto YouTube», sin líneas duplicadas.
4. La home carga sin releer transcripciones (segunda carga instantánea); existe `backups/app-YYYYMMDD.db` tras arrancar.
5. Con wikdict instalado, el popup muestra glosas en español bajo las acepciones; sin él, todo funciona igual.
6. Todo el código lee el idioma del perfil; los tests pasan; el selector de idioma no aparece (solo ca activo); la DB migrada conserva todos los estados.
