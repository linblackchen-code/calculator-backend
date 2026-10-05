"""Exercise real HTTP handlers and a temporary SQLite database."""

import csv
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "history.db"
        self.client = TestClient(create_app(self.path))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.cleanup()

    def calculate(self, expression):
        return self.client.post("/api/calculate", json={"expression": expression})

    def test_calculate_and_query(self):
        response = self.calculate("(1+2)*3")
        self.assertEqual(response.status_code, 201)
        record = response.json()
        self.assertEqual(record["result"], "9")
        self.assertIn("created_at", record)
        history = self.client.get("/api/history").json()
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["id"], record["id"])

    def test_persistence_across_application_restart(self):
        record = self.calculate("0.1+0.2").json()
        with TestClient(create_app(self.path)) as second_client:
            history = second_client.get("/api/history").json()
            self.assertEqual(history["items"][0]["result"], "0.3")
            self.assertEqual(history["items"][0]["id"], record["id"])

    def test_deletion_really_removes_database_record(self):
        first = self.calculate("1+2").json()
        second = self.calculate("5*8").json()
        response = self.client.delete(f"/api/history/{first['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.delete(f"/api/history/{first['id']}").status_code, 404)
        with TestClient(create_app(self.path)) as second_client:
            history = second_client.get("/api/history").json()
            self.assertEqual(history["total"], 1)
            self.assertEqual(history["items"][0]["id"], second["id"])

    def test_errors_do_not_create_history(self):
        for expression in ["1/0", "1+", "__import__('os')"]:
            response = self.calculate(expression)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json()["success"])
        self.assertEqual(self.client.get("/api/history").json()["total"], 0)

    def test_frontend_cannot_submit_precomputed_result(self):
        response = self.client.post("/api/calculate", json={"expression": "1+2", "result": 99})
        self.assertEqual(response.status_code, 422)
        for payload in [{}, {"expression": 123}, {"expression": ""}]:
            self.assertEqual(self.client.post("/api/calculate", json=payload).status_code, 422)

    def test_pagination_and_literal_search(self):
        for number in range(12):
            self.calculate(f"{number}+1")
        first = self.client.get("/api/history?limit=10").json()
        second = self.client.get("/api/history?limit=10&page=2").json()
        self.assertEqual(first["total"], 12)
        self.assertEqual(len(first["items"]), 10)
        self.assertEqual(len(second["items"]), 2)
        self.assertEqual(self.client.get("/api/history", params={"search": "11+1"}).json()["total"], 1)
        self.assertEqual(self.client.get("/api/history", params={"search": "%"}).json()["total"], 0)
        for query in ["page=0", "limit=101", "page=no"]:
            self.assertEqual(self.client.get(f"/api/history?{query}").status_code, 422)

    def test_cors_and_health(self):
        response = self.client.options("/api/calculate", headers={
            "Origin": "http://localhost:8080", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:8080")
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")

    def test_favorites_persist_and_filter_with_search(self):
        first = self.calculate("1+2").json()
        self.calculate("3+4")
        response = self.client.patch(f"/api/history/{first['id']}/favorite", json={"is_favorite": True})
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["is_favorite"], True)
        with TestClient(create_app(self.path)) as restarted:
            records = restarted.get("/api/history?favorites_only=true").json()
            self.assertEqual(records["total"], 1)
            self.assertEqual(records["items"][0]["id"], first["id"])
            self.assertEqual(restarted.get("/api/history?favorites_only=true&search=7").json()["total"], 0)
        self.client.patch(f"/api/history/{first['id']}/favorite", json={"is_favorite": False})
        self.assertEqual(self.client.get("/api/history?favorites_only=true").json()["total"], 0)

    def test_favorite_validation_and_cors(self):
        record = self.calculate("1+2").json()
        for payload in [{}, {"is_favorite": "true"}, {"is_favorite": 1}]:
            self.assertEqual(self.client.patch(f"/api/history/{record['id']}/favorite", json=payload).status_code, 422)
        self.assertEqual(self.client.patch("/api/history/999/favorite", json={"is_favorite": True}).status_code, 404)
        response = self.client.options("/api/history/1/favorite", headers={
            "Origin": "http://localhost:8080", "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200)

    def test_csv_exports_all_pages_and_quoted_expressions(self):
        for number in range(12):
            self.calculate(f"1200+{number}")
        self.calculate("(1+\n2)*3")
        response = self.client.get("/api/history/export")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("attachment; filename=", response.headers["content-disposition"])
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 14)
        self.assertEqual(rows[0], ["ID", "表达式", "结果", "计算时间（UTC）", "收藏"])
        self.assertEqual(rows[1][1], "(1+\n2)*3")

    def test_csv_respects_search_and_favorite_filters(self):
        record = self.calculate("-5+8").json()
        self.calculate("8+8")
        self.client.patch(f"/api/history/{record['id']}/favorite", json={"is_favorite": True})
        response = self.client.get("/api/history/export?favorites_only=true&search=8")
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], "'-5+8")
        self.assertEqual(rows[1][-1], "是")
        response = self.client.get("/api/history/export?search=not-found")
        self.assertEqual(len(list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))), 1)

    def test_old_schema_migrates_without_losing_history(self):
        path = Path(self.directory.name) / "old.db"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE calculation_history (id INTEGER PRIMARY KEY AUTOINCREMENT, expression TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL)")
            connection.execute("INSERT INTO calculation_history VALUES (1, '9*2', '18', '2026-10-05T00:00:00+00:00')")
            connection.commit()
        for attempt in range(2):
            with TestClient(create_app(path)) as migrated:
                history = migrated.get("/api/history").json()
                self.assertEqual(history["total"], 1)
                self.assertEqual(history["items"][0]["expression"], "9*2")
                self.assertIs(history["items"][0]["is_favorite"], attempt == 1)
                self.assertEqual(migrated.patch("/api/history/1/favorite", json={"is_favorite": True}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
