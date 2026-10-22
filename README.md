# SecretBox

SecretBox is a cafe menu and price tracker. React shows drink sizes and prices, compares cafe menus, and supports text-file imports and manual menu edits.

## One service

A single Python / FastAPI process serves the built React website, authentication, menus, price comparisons, chat messages, and menu imports. Everything uses port 8000. Java and a running Vite server are no longer required.

## Run locally on Windows

Use Python 3.10+ and Node.js compatible with the project's Vite version. Node.js is used only to build the website; it is not a separate running service.

With your Python virtual environment activated, run from the repository folder:

```powershell
python -m pip install -r requirements.txt
python start.py
```

On the first start, the launcher installs frontend dependencies with `npm ci` if needed and builds the website. Later starts reuse the build unless frontend files have changed. To force a rebuild, run `python start.py --build`.

Open `http://127.0.0.1:8000/secretbox/` and create an account or sign in. API docs are at `http://127.0.0.1:8000/docs`. Press `Ctrl+C` to stop the service.

The launcher generates a temporary `SECRET_KEY` when none is set. Set a persistent `SECRET_KEY` in the environment to keep sessions valid across restarts.

Host and port can be configured with `--host` / `--port` or the `HOST` / `PORT` environment variables. For example:

```powershell
python start.py --host 0.0.0.0 --port 8000
```

## Menu imports and manual edits

Both controls save directly through the Python API. No additional process is needed. Supported formats:

```text
Americano 250 ml — 890 ₸
Latte — 1190 ₸
```

```text
Americano | 250 ml | 890
Latte | 0.35 l | 1190
Tea | | 590
```

Sizes may use `ml`, `мл`, `l`, or `л`. Blank sizes remain unlisted. Imports must be UTF-8, at most 2 MB, and contain 1–1000 valid drinks. Invalid imports do not replace the menu.

Automatic monitoring of cafe websites is not configured. The chat stores user messages; an AI model is not connected.

## API overview

- `POST /register`, `POST /login`
- `GET /coffee-shops`
- `GET /menu/{shop_name}`, `PUT /menu/{shop_name}` (JSON)
- `PUT /api/menus/{shop_name}` (UTF-8 plain text import)
- `GET /analytics/compare`
- `GET /chat`, `POST /chat`
- `GET /health`

Cafe, chat, analytics, and menu-update endpoints require a bearer token. Data defaults to `objects/` and `users.db`; `SECRETBOX_DATA_DIR` and `SECRETBOX_DB_FILE` can override these paths.

## Development and deployment

For optional frontend hot reload, run `npm.cmd run dev` in `secretbox-ui` alongside the API. Vite proxies API requests to port 8000. This is only a development option; normal use needs just `python start.py`.

For a single-service deployment, build the frontend during deployment and run `python start.py --host 0.0.0.0`. Include `secretbox-ui/dist` in the deployment artifact. Node.js is unnecessary at runtime when the build is current. Persist the database and menu files across deployments.

The existing GitHub Pages workflow remains an alternative static deployment. It sets `VITE_API_URL` to the separately hosted Python API; redeploy that API to include the new import endpoint. The normal local single-service build uses its own origin.

The old `price-updater/` Java source is retained as legacy code and is not used by the application.
