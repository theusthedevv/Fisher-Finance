import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import database
import main


async def asgi_request(path, method="GET", payload=None):
    url = urlsplit(path)
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    messages = []
    received = False
    headers = [(b"host", b"testserver")]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": url.path,
        "raw_path": url.path.encode("ascii"),
        "query_string": url.query.encode("ascii"),
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "state": {},
    }

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await main.app(scope, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    if not response_body:
        parsed_body = None
    else:
        try:
            parsed_body = json.loads(response_body)
        except json.JSONDecodeError:
            parsed_body = response_body.decode("utf-8")
    return status, parsed_body


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path_patcher = patch.object(
            database, "DB_PATH", Path(self.temp_dir.name) / "api-test.db"
        )
        self.path_patcher.start()
        database.init_db()

    async def asyncTearDown(self):
        self.path_patcher.stop()
        self.temp_dir.cleanup()

    async def test_transaction_lifecycle_and_dashboard(self):
        status, created = await asgi_request(
            "/transacoes/nova",
            "POST",
            {
                "tipo": "receita",
                "descricao": "Salário",
                "valor": 3500.25,
                "categoria": "Salário",
                "data": "2026-03-05",
            },
        )
        self.assertEqual(status, 201)
        transaction_id = created["transacao"]["id"]
        self.assertEqual(created["transacao"]["valor"], 3500.25)

        status, _ = await asgi_request(
            "/transacoes/nova",
            "POST",
            {
                "tipo": "despesa",
                "descricao": "Aluguel",
                "valor": 1200,
                "categoria": "Moradia",
                "data": "2026-03-07",
            },
        )
        self.assertEqual(status, 201)

        status, result = await asgi_request("/api/dashboard?mes=2026-03")
        self.assertEqual(status, 200)
        self.assertEqual(result["saldo_centavos"], 230025)
        self.assertEqual(result["quantidade_transacoes"], 2)

        status, result = await asgi_request("/transacoes/lista?mes=2026-03")
        self.assertEqual(status, 200)
        self.assertEqual(len(result["transacoes"]), 2)

        status, _ = await asgi_request(
            f"/transacoes/{transaction_id}",
            "PUT",
            {
                "tipo": "receita",
                "descricao": "Salário atualizado",
                "valor": 3600,
                "categoria": "Salário",
                "data": "2026-03-05",
            },
        )
        self.assertEqual(status, 200)

        status, _ = await asgi_request(
            f"/transacoes/{transaction_id}", "DELETE"
        )
        self.assertEqual(status, 204)

    async def test_invalid_transaction_is_rejected(self):
        status, response = await asgi_request(
            "/transacoes/nova",
            "POST",
            {
                "tipo": "receita",
                "descricao": "Valor inválido",
                "valor": -1,
                "categoria": "Salário",
                "data": "2026-03-05",
            },
        )
        self.assertEqual(status, 422)
        self.assertEqual(response["detail"][0]["loc"][-1], "valor")
        self.assertEqual(database.buscar_transacoes(), [])

    async def test_meta_creation_and_progress(self):
        status, result = await asgi_request(
            "/api/metas",
            "POST",
            {"nome": "Reserva de emergência", "valor_alvo": 5000},
        )
        self.assertEqual(status, 201)
        goal_id = result["meta"]["id"]

        status, result = await asgi_request(
            f"/api/metas/{goal_id}/progresso",
            "PUT",
            {"valor_atual": 750},
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["meta"]["valor_atual"], 750)

    def test_web_app_and_assets_are_configured(self):
        index = main.STATIC_DIR / "index.html"
        stylesheet = main.STATIC_DIR / "styles.css"
        script = main.STATIC_DIR / "app.js"
        self.assertTrue(index.is_file())
        self.assertTrue(stylesheet.is_file())
        self.assertTrue(script.is_file())
        self.assertIn("Fisher — Controle financeiro", index.read_text(encoding="utf-8"))
        self.assertEqual(main.app.title, "Fisher — Controle financeiro")
        self.assertTrue(
            any(getattr(route, "name", None) == "static" for route in main.app.routes)
        )


if __name__ == "__main__":
    unittest.main()
