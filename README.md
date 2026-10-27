# SecretBox

SecretBox is a cafe menu and price tracker. The React website shows each drink's listed size and price, compares matching cafe menus, and supports text-file imports and manual menu edits.

## Services

- **Python / FastAPI** serves the authenticated API, reads cafe menu files, stores accounts and chat messages, and compares current menu prices.
- **Java** runs a small menu-updater HTTP service. It accepts an uploaded or edited menu, validates drink names, sizes and prices, then forwards the structured update to the Python API.
- **React / Vite** provides the responsive website.

Sizes are displayed only when supplied in the source menu. SecretBox does not estimate missing volumes.
Menu changes are imported from staff uploads or entered manually; automatic monitoring of cafe websites is not configured because no source URLs were provided.

## Run locally on Windows

Open separate PowerShell windows. In each window, start from the project folder:

```powershell
cd "D:\==Codes==\==StartUp==\SecretBox\commited secret box"
```

### 1. Start the Python API

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:SECRET_KEY = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Its SQLite database is created as `users.db` on first start.
The command above creates a private random `SECRET_KEY` for this PowerShell window. Set it again each time you restart the API.

### 2. Start the Java updater (only needed for menu updates)

Install a JDK 11 or newer, open a second PowerShell window, then run:

```powershell
cd "D:\==Codes==\==StartUp==\SecretBox\commited secret box\price-updater"
javac -encoding UTF-8 -d out src\main\java\com\secretbox\PriceUpdaterServer.java
java -cp out com.secretbox.PriceUpdaterServer
```

The updater runs at `http://127.0.0.1:8081`. Set `PYTHON_API_URL` if the Python API is not at its default address.
The cafe catalog, chat, and price comparison work without this Java service. The manual and upload menu-update controls need it running.

### 3. Start the website

In another PowerShell window:

```powershell
cd "D:\==Codes==\==StartUp==\SecretBox\commited secret box\secretbox-ui"
npm.cmd install
npm.cmd run dev
```

Open the local URL printed by Vite. Optional frontend settings can be supplied through `VITE_API_URL` and `VITE_UPDATER_URL` before starting Vite.
Choose **Continue as guest** to browse the bundled cafe menus and compare prices without an account. The guest catalog is read-only; create an account and sign in to edit menus or use team chat. Guest menus are bundled from `objects` when the UI is built.

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

## Update a SecretBox menu from screenshots

The `driver` script can recognize a cafe menu from one or more screenshots and prepare a `.txt` draft in the format accepted by SecretBox. It does not publish changes or overwrite files in `objects`.

Install the driver dependencies and set `OPENAI_API_KEY` in `driver\.env`:

```powershell
py -m pip install -r driver\requirements.txt
notepad driver\.env
```

Set `OPENAI_API_KEY=...` in the `.env` file. `.env` files are ignored by Git.

Pass one screenshot directly or put multiple screenshots for one cafe in a folder, then choose one mode:

```powershell
py driver\driver.py path\to\menu.png --secretbox-shop Ayu --menu-mode replace
py driver\driver.py path\to\screenshots --secretbox-shop Ayu --menu-mode merge
```

`replace` creates a draft from the complete menu shown in the screenshots. `merge` updates matching drink names and sizes in the current menu and appends new ones; it cannot infer removals from a partial screenshot. Drafts are saved under `driver\output\secretbox-drafts\` by default. Review the generated file before uploading it in the signed-in site's **Update this menu → Upload .txt** control. Uploading a draft replaces the cafe menu with its contents, so use `replace` only when the screenshots show the complete menu. The site's Java updater and Python API must be running to upload it.

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
