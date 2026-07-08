# CatalàMiner v0.8.0 — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Spec: `docs/specs/2026-07-07-v080-vocabulario-progreso-design.md`. Convenciones: pytest + `client(tmp_path)`, `node --check` tras editar JS, commit por tarea, verificación en app de escritorio/preview al final.

### Task 0
- [ ] Rama `feature/v080-vocab-progreso`.

### Task 1: Panel «Palabras» + nivel de vocabulario
- [ ] `app/vocab.py`: `ranks(n=5000)` → dict lema→rank desde `wordfreq.top_n_list("ca", n)` lematizando con `forms` (primer candidato); cache en memoria. `bulk_known(con, top_n)` → marca `known` lemas top_n sin estado previo, devuelve nº.
- [ ] `GET /api/vocab/ranks` → `{ranks:{lema:rank}}` (top 5000). `POST /api/words/bulk-known {top_n}` → `{marked}`.
- [ ] Tests: ranks lematiza y cachea (mock top_n_list + forms.lookup); bulk-known no pisa learning/ignored.
- [ ] Frontend: tabs en `#side-panel` («Subtítulos | Palabras»); vista Palabras agrupada por bandas Rank 1–100/101–300/301–1000/1001–5000/resto usando ranks + zipf para orden interno; clic → `openPopup(segIndex_de_1a_aparicion, lema, el, true)`; contextmenu → toggle known/unknown; botón «Establecer nivel de vocabulario» → mini-diálogo slider + POST + refresh (`syncdespués: STATUS = respuesta o re-GET sesión; renderSegs/updateComp`).
- [ ] CSS bandas + chips de palabra. Commit.

### Task 2: Progreso subida/URL
- [ ] Backend: `POST /api/sessions/upload` guarda archivo y devuelve `{job_id}`; job: `ensure_browser_playable` («convirtiendo…») + `duration` («analizando…») + `create_session` → result `{session_id, has_sidecar_subs}`. `POST /api/sessions/url` → job («comprobando el enlace…») con la validación actual.
- [ ] Tests: upload devuelve job y el job crea la sesión (mock media); url job idem.
- [ ] Frontend: `uploadWithProgress(url, fd, onpct)` con XHR (`upload.onprogress`) + `$("job-progress")` «Subiendo… NN%»; luego `pollJob`. `url-btn` → pollJob. Commit.

### Task 3: Subs automáticos de YouTube
- [ ] `youtube.py`: `writeautomaticsub: True`; detectar origen: `"ca" in (info.get("subtitles") or {})` → `youtube_subs`, si no y hay vtt → `youtube_auto`; devolver `subs_kind`.
- [ ] `subs.py`: `clean_auto(segs)` — strip `<[^>]+>`, descartar vacíos, fusionar consecutivos con texto idéntico o contenido en el siguiente (rolling captions).
- [ ] `main.youtube_import`: usar `clean_auto` cuando `subs_kind == "youtube_auto"`; guardar srt_source correspondiente. `SRC_LABEL` + «Subs auto YouTube» en app.js.
- [ ] Tests: clean_auto fusiona duplicados y limpia tags. Commit.

### Task 4: Biblioteca instantánea + backup
- [ ] `main._session_meta`: una sola `db.get_session`; caché módulo-level `_META_CACHE[(sid, updated_at, ws_version)]` donde `ws_version = SELECT MAX(updated_at) FROM word_status` (una query por request de listado).
- [ ] `db.backup_daily(con, app_dir)`: `con.backup()` a `backups/app-YYYYMMDD.db` si falta; poda >7. Llamada en arranque de `main`.
- [ ] Tests: backup crea archivo y poda; meta cache invalida al cambiar estado. Commit.

### Task 5: Wikcionario offline (kaikki)
- [ ] Validar URL en vivo (`curl -I`): extracción de es.wiktionary para catalán en kaikki.org. Si no existe → construir el módulo igualmente con `available() == False` y saltar descarga.
- [ ] `app/wikdict.py` (patrón forms.py): descarga JSONL → sqlite `wikdict-<lang>.sqlite` (word, pos, gloss); `lookup(term)` → [(gloss, pos)]; lazy, degradación a [].
- [ ] `main.lookup`/`_build_preview`: campo nuevo `glosses` (máx 4, del lema); popup: bloque `#wp-gloss` bajo las acepciones (estilo `#wp-def`).
- [ ] Tests: build+lookup con JSONL de muestra; endpoint incluye glosses (mock). Commit.

### Task 6: Multi-idioma preparado
- [ ] `app/languages.py`: `PROFILES` (ca completo; fr con `translate_repo=None` → inactivo), `active()` lee settings, `get(key)` helpers.
- [ ] Refactor a perfil: `config.WHISPER_MODELS/TRANSLATE_REPO/BIDIX_URL/FORMS_URL` → funciones/perfil; `nlp._spacy` (nombre modelo), `zipf(lang)`, `ipa` (voz), `translate.model_dir` (sufijo idioma), `forms/dictionary/wikdict` (rutas y URLs por idioma). Mantener compat: con solo `ca` todo idéntico.
- [ ] DB: migrar `word_status` → PK `(lemma, language)` (rebuild + copia `language='ca'`); `word_statuses(con, lang)`, `set_word_status(..., lang)` — call sites pasan idioma activo.
- [ ] ⚙️: sección Idioma **oculta** si solo hay 1 perfil activable (`GET /api/settings` gana `languages: [...]`).
- [ ] Tests: migración conserva estados; perfil fr inactivo no seleccionable. Commit.

### Task 7: Versión y cierre
- [ ] `?v=0.8.0`, pyproject 0.8.0, README (Palabras, nivel, subs auto, backups).
- [ ] Suite + `node --check` + criterios de aceptación; merge `--no-ff` a main. **No** relanzar servidor web (el usuario usa la .app); avisar de reiniciar la .app.
