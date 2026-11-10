# Portale-von-Molthar

We are building an AI model that plays our favorite card game, Portale von Molthar.


## Installation

As a user, run `pip install .` (or `uv pip install .`).

As a developer:

```bash
pip install -e ".[dev]"       # or: uv pip install -e ".[dev]"
pre-commit install
```

`pre-commit install` sets up git hooks so the same checks that will catch
issues later (ruff, mypy, pylint, bandit, flake8-errmsg, nb-clean) run
automatically on every commit.


## Play online

The multiplayer server (`src/portale_von_molthar/services` and `entrypoints/api.py`)
wraps the engine; the React frontend lives in `frontend/` and uses the
*Molthar Illuminated* design system.

```bash
uv pip install -e ".[server]"
uvicorn portale_von_molthar.entrypoints.api:app --reload   # API on :8000

cd frontend && npm install && npm run dev                  # UI on :5173, proxies /api and /ws
```

For one process that serves everything, build the frontend once; the API then serves
`frontend/dist` at `/`. Games live in memory, so restarting the server ends them.

```bash
cd frontend && npm run build && cd ..
uvicorn portale_von_molthar.entrypoints.api:app --host 0.0.0.0 --port 8000
```

**Same Wi-Fi:** find the host's IP (`ipconfig getifaddr en0` on macOS), and everyone opens
`http://<that-ip>:8000`. Allow incoming connections if the firewall asks. Guest networks
often block device-to-device traffic.

**Over the internet:** with uvicorn running, start `cloudflared tunnel --url http://localhost:8000`
(`brew install cloudflared`) and share the printed `https://….trycloudflare.com` URL.

One player creates a game, the others join with its 5-letter code or the invite link.


## Tooling

* `ruff` — formatting, import sorting, and linting.
* `pytest` + `coverage` — unit testing and coverage tracking.
* `nb-clean` — strips output/metadata from Jupyter notebooks before commit.
* `mypy` — static type checking.
* `pylint` — enabled only for meaningful variable name enforcement.
* `flake8` — enabled only for non-empty error message enforcement (flake8-errmsg).
* `pre-commit` — runs all of the above automatically before each commit.
  Run `pre-commit install` once per clone to enable it.
* `sphinx` — documentation generation (optional `docs` extra).


## Unittests

Run the full suite with:

```bash
pytest
```

Run a single test with:

```bash
pytest --tb=short <path_to_test_file>.py::<test_function_name>
```

For coverage:

```bash
coverage run -m pytest && coverage report
```

Tests live under `tests/`, mirroring the structure of `src/portale_von_molthar/`.
See `AGENTS.md` for the naming convention.


## Versioning

Version numbers are derived automatically from git tags via `hatch-vcs` — tag
a commit (e.g. `git tag v0.1.0 && git push --tags`) to cut a release version.