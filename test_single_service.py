"""Integration checks: python -m unittest test_single_service -v."""

import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import json as json_module
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_request(method, url, *, data=None, json=None, headers=None, timeout=5):
    headers = dict(headers or {})
    if json is not None:
        data = json_module.dumps(json).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read().decode("utf-8")
        return SimpleNamespace(status_code=response.status, text=body,
                               url=response.url, headers=response.headers, json=lambda: json_module.loads(body))


class SingleServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        menus = root / "objects"
        menus.mkdir()
        cls.menus = menus
        for shop, price in (("test", 590), ("comparison", 790)):
            (menus / f"{shop}_menu.json").write_text(json_module.dumps({
                "currency": "KZT", "items": [{"name": "Tea", "size_ml": None, "price": price}],
            }), encoding="utf-8")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.url = f"http://127.0.0.1:{port}"
        env = dict(os.environ, SECRETBOX_DB_FILE=str(root / "users.db"),
                   SECRETBOX_DATA_DIR=str(menus), SECRET_KEY="test-only-key-with-at-least-32-bytes")
        cls.log = (root / "server.log").open("w+", encoding="utf-8")
        cls.addClassCleanup(cls.log.close)
        cls.server = subprocess.Popen(
            [sys.executable, "start.py", "--port", str(port)],
            cwd=Path(__file__).resolve().parent, env=env,
            stdout=cls.log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        cls.addClassCleanup(cls.stop_server)
        for _ in range(100):
            try:
                if http_request("GET", cls.url + "/health", timeout=1).status_code == 200:
                    break
            except URLError:
                pass
            if cls.server.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError(cls.log.read())
            time.sleep(0.1)
        else:
            cls.log.seek(0)
            raise RuntimeError("Server did not start:\n" + cls.log.read())
        credentials = {"username": "tester", "password": "test-password"}
        assert http_request("POST", cls.url + "/register", json=credentials, timeout=5).status_code == 200
        response = http_request("POST", cls.url + "/login", json=credentials, timeout=5)
        assert response.status_code == 200, response.text
        cls.headers = {"Authorization": "Bearer " + response.json()["token"]}

    @classmethod
    def stop_server(cls):
        if cls.server.poll() is not None:
            return
        if os.name == "nt":
            cls.server.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            cls.server.terminate()
        cls.server.wait(timeout=10)

    def upload(self, content, headers=None):
        return http_request("PUT", self.url + "/api/menus/test", data=content,
                            headers=self.headers if headers is None else headers, timeout=5)

    def test_website_and_assets(self):
        response = http_request("GET", self.url + "/", timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.url.endswith("/secretbox/"))
        assets = re.findall(r'(?:src|href)="(/secretbox/assets/[^\"]+)"', response.text)
        self.assertTrue(assets)
        for asset in assets:
            self.assertEqual(http_request("GET", self.url + asset, timeout=5).status_code, 200)
        self.assertEqual(http_request("GET", self.url + "/secretbox/users.db", timeout=5).status_code, 404)
        self.assertEqual(http_request("GET", self.url + "/docs", timeout=5).status_code, 200)

    def test_import_formats(self):
        content = "\ufeffLatte | 0,35 л | 1 190 ₸\nTea | | 590\nAmericano 250 ml — 890 ₸\n"
        response = self.upload(content.encode("utf-8"))
        self.assertEqual(response.status_code, 200, response.text)
        response = http_request("GET", self.url + "/menu/test", headers=self.headers, timeout=5)
        items = response.json()["items"]
        self.assertEqual([item["size_ml"] for item in items], [350, None, 250])
        self.assertEqual([item["price"] for item in items], [1190, 590, 890])

    def test_invalid_import_preserves_menu(self):
        self.assertEqual(self.upload(b"Tea | | 590").status_code, 200)
        for content in (b"", b"Tea | 9999 ml | 100", b"Tea | | 0", b"Tea | | 1000001",
                        b"Tea | | abc", b"bad line", b"\xff", b"Tea | | 590\n" * 1001):
            self.assertEqual(self.upload(content).status_code, 400)
        self.assertEqual(self.upload(b"x" * 2_000_001).status_code, 413)
        response = http_request("GET", self.url + "/menu/test", headers=self.headers, timeout=5)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["price"], 590)

    def test_import_requires_authentication(self):
        self.assertEqual(self.upload(b"Tea | | 590", headers={}).status_code, 401)
        self.assertEqual(self.upload(b"Tea | | 590", headers={"Authorization": "Bearer invalid"}).status_code, 401)

    def test_existing_api(self):
        response = http_request("POST", self.url + "/chat", json={"text": "Hello"}, headers=self.headers, timeout=5)
        self.assertEqual(response.status_code, 200)
        messages = http_request("GET", self.url + "/chat", headers=self.headers, timeout=5).json()["messages"]
        self.assertEqual(messages[-1]["text"], "Hello")
        for path in ("/coffee-shops", "/analytics/compare"):
            self.assertEqual(http_request("GET", self.url + path, headers=self.headers, timeout=5).status_code, 200)

    def test_json_menu_update_and_comparison(self):
        response = http_request("PUT", self.url + "/menu/test", headers=self.headers,
                                json={"items": [{"name": "Tea", "price": 590}]})
        self.assertEqual(response.status_code, 200, response.text)
        menu = http_request("GET", self.url + "/menu/test", headers=self.headers).json()
        self.assertTrue(menu["updated_at"])
        self.assertEqual(menu["items"][0]["price"], 590)
        rows = http_request("GET", self.url + "/analytics/compare", headers=self.headers).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Разброс"], 200)
        self.assertEqual(rows[0]["test"], "590 ₸")
        self.assertEqual(rows[0]["comparison"], "790 ₸")

    def test_json_file_import_and_storage(self):
        document = {"currency": "KZT", "items": [
            {"name": "Латте — special | edition", "size_ml": 350, "price": 1190},
            {"name": "Чай", "size_ml": None, "price": 590},
        ]}
        response = self.upload(json_module.dumps(document, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(response.status_code, 200, response.text)
        path = self.menus / "test_menu.json"
        self.assertEqual(json_module.loads(path.read_text(encoding="utf-8")), document)
        items = http_request("GET", self.url + "/menu/test", headers=self.headers).json()["items"]
        self.assertEqual(items[0]["name"], document["items"][0]["name"])
        previous = path.read_bytes()
        for bad in (b'{"items":[]}', b'{"items":[', b'[]', b'{"items":[{"name":" ","price":100}]}',
                    b'{"currency":"USD","items":[{"name":"Tea","price":100}]}'):
            self.assertEqual(self.upload(bad).status_code, 400)
            self.assertEqual(path.read_bytes(), previous)
        self.assertFalse(list(self.menus.glob("*.txt")))

    def test_authentication_errors(self):
        response = http_request("POST", self.url + "/login",
                                json={"username": "tester", "password": "incorrect"})
        self.assertEqual(response.status_code, 400)
        response = http_request("POST", self.url + "/register",
                                json={"username": "tester", "password": "test-password"})
        self.assertEqual(response.status_code, 400)
        for path in ("/coffee-shops", "/menu/test", "/analytics/compare", "/chat"):
            self.assertEqual(http_request("GET", self.url + path).status_code, 401)

    def test_pages_origin_can_sign_in(self):
        response = http_request("OPTIONS", self.url + "/login", headers={
            "Origin": "https://the-fabulous.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://the-fabulous.github.io")
        rejected = http_request("OPTIONS", self.url + "/login", headers={
            "Origin": "https://unrelated.example",
            "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(rejected.status_code, 400)

    def test_guest_cannot_change_menus_or_read_chat(self):
        self.assertEqual(http_request("PUT", self.url + "/menu/test",
                                     json={"items": [{"name": "Tea", "price": 1}]}).status_code, 401)
        self.assertEqual(http_request("GET", self.url + "/chat").status_code, 401)
        self.assertEqual(http_request("POST", self.url + "/chat", json={"text": "Guest"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
