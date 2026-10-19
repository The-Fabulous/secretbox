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
On first visit, choose **Create an account** to register, then sign in.

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
