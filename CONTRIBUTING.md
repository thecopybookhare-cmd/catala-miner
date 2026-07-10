# Contribuir a CatalàMiner

¡Gracias por tu interés! Este es un proyecto personal de código abierto (MIT).

## Puesta a punto

```bash
git clone <repo>
cd catala-miner
./install.sh          # crea el venv, instala deps y modelos (macOS + Homebrew)
```

Para desarrollo sin los modelos pesados basta con:

```bash
uv venv --python 3.12 .venv
uv pip install -p .venv/bin/python -e . --group dev
```

## Antes de un PR

```bash
.venv/bin/ruff check app/ tests/     # lint (debe pasar; el CI lo exige)
.venv/bin/python -m pytest tests/    # tests (74, deben pasar)
node --check static/app.js           # sanidad del JS del frontend
```

- **Estilo:** sigue el estilo del código que rodea tu cambio (comentarios en
  español/catalán donde ya los hay, líneas ~80-100 col). No corras
  `ruff format` sobre todo el repo — el formato es a mano a propósito.
- **Tests:** todo cambio de backend lleva su test (patrón en `tests/`).
- **Commits:** mensaje claro en español; una unidad de trabajo por commit.

## Arquitectura

Ver `README.md` (sección Arquitectura) y los diseños en `docs/specs/`.
FastAPI + SQLite + JS vanilla; sin build step en el frontend.
