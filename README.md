# SecretBox

SecretBox is a cafe menu and price tracker. The React website shows each drink's listed size and price, compares matching cafe menus, and supports text-file imports and manual menu edits.

## Services

- **Python / FastAPI** serves the authenticated API, reads cafe menu files, stores accounts and chat messages, and compares current menu prices.
- **Java** runs a small menu-updater HTTP service. It accepts an uploaded or edited menu, validates drink names, sizes and prices, then forwards the structured update to the Python API.
- **React / Vite** provides the responsive website.

Sizes are displayed only when supplied in the source menu. SecretBox does not estimate missing volumes.
Menu changes are imported from staff uploads or entered manually; automatic monitoring of cafe websites is not configured because no source URLs were provided.

## Run locally on Windows

Install Python, Node.js (which includes npm), and a JDK 11 or newer if you want to import or edit menus.

### One-time setup

From the project folder, install the Python and frontend dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd secretbox-ui
npm.cmd install
cd ..
```

### Start the website and API together

From the project folder, run this in PowerShell:

```powershell
py start.py
```

Open `http://127.0.0.1:5173/secretbox/` and choose **Create an account** to register, then sign in. The API documentation is at `http://127.0.0.1:8000/docs`. Press `Ctrl+C` in the terminal to stop both services.

The launcher generates a temporary `SECRET_KEY` if one is not already set. Restarting it signs out existing sessions.

### Importing or editing menus

The Java updater is optional and is only required for the manual and upload menu-update controls. In a separate PowerShell window, run:

```powershell
cd price-updater
javac -encoding UTF-8 -d out .\src\main\java\com\secretbox\PriceUpdaterServer.java
java -cp out com.secretbox.PriceUpdaterServer
```

The updater runs at `http://127.0.0.1:8081`. The catalog, chat, and price comparison work without it.

## Menu format

Existing menu files in `objects` may use lines like:

```text
Americano 250 ml — 890 ₸
Latte — 1190 ₸
```

For manual edits, use one drink per line:

```text
Americano | 250 ml | 890
Latte | 350 ml | 1190
Tea | | 590
```

Volumes may be entered in millilitres (`ml`/`мл`) or litres (`l`/`л`); litre values are converted to millilitres. Blank sizes remain unlisted. Price-list imports use the same line formats as the manual editor.

## API overview

- `POST /register`, `POST /login`
- `GET /coffee-shops`
- `GET /menu/{shop_name}`, `PUT /menu/{shop_name}`
- `GET /analytics/compare`
- `GET /chat`, `POST /chat`
- Java updater: `PUT /api/menus/{shop_name}`, `GET /health`

Menu updates require a bearer token, just like the existing cafe and chat endpoints.

## Free website deployment with GitHub Pages

The `.github/workflows/deploy-pages.yml` workflow builds the React app and publishes it to GitHub Pages when changes are pushed to `main`. The static website is free to host. It uses the existing Python API at `https://secretbox-main.onrender.com`; that API may take a short time to wake up after inactivity.

The first workflow run enables GitHub Pages deployment. Once it completes, share `https://zhanaliber.github.io/secretbox/`. The API must also be redeployed with the GitHub Pages CORS origin for sign-in and menu data to work.
