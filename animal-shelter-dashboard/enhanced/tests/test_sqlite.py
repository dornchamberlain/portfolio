# Use real temporary databases to test storage behavior, not mocked SQL calls.
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from sqlalchemy import insert, event
from sqlalchemy.exc import OperationalError
from shelter.sql_repository import SQLiteRepository, animals
from shelter.repository import RepositoryError, create_repository
from shelter.config import Settings
from shelter.ranking import rank_records
from shelter.records import normalize_records
from shelter.app import create_app
from test_dashboard import animal


class SQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.repo = SQLiteRepository(self.path)
        self.repo.initialize()

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_crud_and_persistence(self):
        self.assertEqual(self.repo.create(animal("first")), "first")
        self.repo.close()
        self.repo = SQLiteRepository(self.path)
        self.assertEqual(self.repo.read_page().rows[0]["name"], "Test animal")
        self.assertTrue(self.repo.update("first", {"name": "Changed"}))
        self.assertEqual(self.repo.read_page().rows[0]["name"], "Changed")
        self.assertFalse(self.repo.update("missing", {"name": "Changed"}))
        self.assertTrue(self.repo.delete("first"))
        self.assertFalse(self.repo.delete("first"))
        self.assertEqual(self.repo.read_page().total, 0)

    def test_batch_constraint_failure_rolls_back_every_insert(self):
        self.repo.create(animal("existing"))
        with self.assertRaises(RepositoryError):
            self.repo.create_many([animal("new"), animal("existing")])
        self.assertEqual([r["id"] for r in self.repo.read_page().rows], ["existing"])
        # A rejected transaction must not poison the next valid operation.
        self.repo.create(animal("after"))
        self.assertEqual(self.repo.read_page().total, 2)

    def test_invalid_batch_is_not_partially_written(self):
        with self.assertRaises(ValueError):
            self.repo.create_many([animal("good"), animal("bad", location_lat=91)])
        self.assertEqual(self.repo.read_page().total, 0)

    def test_repeat_animal_ids_but_unique_record_ids(self):
        self.repo.create_many([animal("a"), animal("b")])
        with self.assertRaises(RepositoryError):
            self.repo.create(animal("a"))
        self.assertEqual(self.repo.read_page().total, 2)

    def test_direct_database_constraints(self):
        # Bypassing the repository still must not allow corrupt stored values.
        for values in [{"id": None}, {"id": ""}, {"id": "x", "age_upon_outcome_in_weeks": -1},
                       {"id": "x", "age_upon_outcome_in_weeks": "bad"},
                       {"id": "x", "location_lat": 91}, {"id": "x", "location_long": -181},
                       {"id": "x", "name": " "}, {"id": "x", "name": "x" * 201}]:
            with self.subTest(values=values), self.assertRaises(RepositoryError):
                with self.repo.transaction() as connection:
                    # Driver SQL deliberately bypasses SQLAlchemy's numeric conversions.
                    keys = list(values)
                    connection.exec_driver_sql(
                        "INSERT INTO animal_records (" + ",".join(keys) + ") VALUES (" + ",".join("?" for _ in keys) + ")",
                        tuple(values.values()))

    def test_validation_of_writes_and_identity(self):
        for changes in [{"age_upon_outcome_in_weeks": True}, {"location_lat": float("inf")},
                        {"name": []}, {"id": " "}, {"private": "value"}, {"name": "x" * 201}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.repo.create({**animal(), **changes})
        self.repo.create(animal())
        for changes in [{}, {"id": "new"}, {"location_long": 181}]:
            with self.assertRaises(ValueError):
                self.repo.update("1", changes)
        self.assertEqual(self.repo.read_page().rows[0]["id"], "1")

    def test_nulls_boundaries_and_projection(self):
        self.repo.create({"id": "unknown"})
        self.repo.create(animal("edge", age_upon_outcome_in_weeks=0, location_lat=-90, location_long=180))
        page = self.repo.read_page(fields=["id", "name"])
        self.assertEqual(set(page.rows[0]), {"id", "name"})
        self.assertIsNone(page.rows[1]["name"])

    def test_filter_combinations_and_sort(self):
        self.repo.create_many([animal("b", name="Zed", age_upon_outcome_in_weeks=10),
                               animal("a", name="Amy", age_upon_outcome_in_weeks=20),
                               animal("c", animal_type="Cat"), animal("d", age_upon_outcome_in_weeks=None)])
        result = self.repo.read_page(filters={"animal_type": "Dog", "min_age": 10, "max_age": 20}, sort="name", descending=True)
        self.assertEqual([r["id"] for r in result.rows], ["b", "a"])
        self.assertEqual(self.repo.read_page(filters={"animal_type": "Cat", "breed": "Labrador Retriever Mix"}).total, 1)

    def test_pagination_ties_and_clamping(self):
        self.repo.create_many([animal(str(i).zfill(2), name="Same") for i in range(23)])
        pages = [self.repo.read_page(page=i, sort="name") for i in range(3)]
        self.assertEqual([len(p.rows) for p in pages], [10, 10, 3])
        self.assertEqual(len({r["id"] for p in pages for r in p.rows}), 23)
        self.assertEqual(self.repo.read_page(page=99).page, 2)

    def test_invalid_query_options(self):
        cases = [{"page": -1}, {"page": True}, {"page_size": 0}, {"page_size": 101},
                 {"sort": "id; DROP TABLE animal_records"}, {"fields": ["password"]},
                 {"fields": "id"}, {"filters": {"unknown": "x"}}, {"filters": []},
                 {"filters": {"min_age": True}}, {"filters": {"min_age": 3, "max_age": 2}},
                 {"descending": "yes"}, {"profile": "INVALID"}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.repo.read_page(**kwargs)

    def test_injection_text_remains_data(self):
        value = "x'; DROP TABLE animal_records; --"
        self.repo.create(animal("quoted", breed=value, name="O'Brien"))
        self.repo.create(animal("ordinary"))
        result = self.repo.read_page(filters={"breed": value})
        self.assertEqual([r["id"] for r in result.rows], ["quoted"])
        self.assertEqual(self.repo.read_page().total, 2)

    def test_sql_ranking_equals_previous_algorithm_across_pages(self):
        sample = json.loads((Path(__file__).resolve().parents[1] / "data/demo_animals.json").read_text())
        sample += [animal("tie-a", animal_id=None), animal("tie-b", animal_id=None),
                   animal("unknown", breed=None, sex_upon_outcome=None, age_upon_outcome_in_weeks=None)]
        self.repo.create_many(sample)
        for profile in ["WATER", "MOUNTAIN", "DISASTER"]:
            expected = rank_records(normalize_records(sample), profile)
            actual = []
            for page in range((len(expected) + 3) // 4):
                actual.extend(self.repo.read_page(profile=profile, page=page, page_size=4).rows)
            self.assertEqual(actual, expected)

    def test_page_query_uses_limit_and_offset(self):
        self.repo.create_many([animal(str(i)) for i in range(25)])
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.repo.engine, "before_cursor_execute", capture)
        result = self.repo.read_page(profile="WATER", page=1)
        self.assertEqual(len(result.rows), 10)
        self.assertTrue(any("LIMIT" in s and "OFFSET" in s for s in statements))

    def test_error_message_and_logs_hide_database_details(self):
        error = OperationalError("secret query", {}, Exception("secret path"))
        with patch.object(self.repo.engine, "begin", side_effect=error):
            with self.assertLogs("shelter.sql_repository", level="WARNING") as logs:
                with self.assertRaises(RepositoryError) as result:
                    self.repo.read_page()
        self.assertNotIn("secret", str(result.exception) + str(logs.output))

    def test_missing_schema_is_not_a_successful_empty_read(self):
        repo = SQLiteRepository(Path(self.temp.name) / "empty.sqlite3")
        try:
            with self.assertRaises(RepositoryError):
                repo.read_page()
        finally:
            repo.close()

    def test_configuration_and_factory(self):
        settings = Settings.from_env({"SHELTER_MODE": "sqlite", "SHELTER_SQLITE_FILE": str(self.path)})
        repo = create_repository(settings)
        try:
            self.assertEqual(repo.read_page().total, 0)
        finally:
            repo.close()

    def test_cli_import_read_update_and_delete(self):
        script = Path(__file__).resolve().parents[1] / "manage_db.py"
        source = Path(self.temp.name) / "records.json"
        source.write_text(json.dumps([animal("cli")]))
        def command(*args):
            return subprocess.run([sys.executable, str(script), "--database", str(self.path), *args],
                                  capture_output=True, text=True)
        self.assertEqual(command("import", str(source)).returncode, 0)
        self.assertEqual(json.loads(command("read").stdout)["total"], 1)
        # Repeating an import is rejected, without changing the first import.
        self.assertNotEqual(command("import", str(source)).returncode, 0)
        source.write_text(json.dumps({"name": "Updated by CLI"}))
        self.assertEqual(command("update", "cli", str(source)).stdout.strip(), "Updated.")
        self.assertEqual(self.repo.read_page().rows[0]["name"], "Updated by CLI")
        self.assertEqual(command("delete", "cli").stdout.strip(), "Deleted.")
        self.assertEqual(self.repo.read_page().total, 0)

    def test_sort_keeps_preference_rank_and_selection_identity(self):
        self.repo.create_many([animal("low", name="Amy", breed="Other"), animal("high", name="Zed")])
        page = self.repo.read_page(profile="WATER", sort="name", page_size=1)
        self.assertEqual(page.rows[0]["id"], "low")
        self.assertEqual(page.rows[0]["rank"], 2)

    def test_real_sqlite_dashboard_callbacks(self):
        self.repo.create_many([animal(str(i).zfill(2)) for i in range(23)])
        settings = Settings.from_env({"SHELTER_MODE": "sqlite", "SHELTER_SQLITE_FILE": str(self.path)})
        app = create_app(settings, self.repo)
        client = app.server.test_client()
        self.assertEqual(client.get("/_dash-layout").status_code, 200)
        key = next(k for k in app.callback_map if "animals.data" in k)
        def request(page, changed, breed=None):
            return client.post("/_dash-update-component", json={"output": key,
                "outputs": [{"id": i, "property": p} for i, p in [("animals", "data"), ("status", "children"),
                    ("animals", "page_count"), ("animals", "page_current"), ("animals", "selected_row_ids")]],
                "inputs": [{"id": i, "property": p, "value": v} for i, p, v in [
                    ("filter-type", "value", "WATER"), ("animals", "page_current", page),
                    ("db-type", "value", None), ("db-breed", "value", breed), ("db-sort", "value", "rank")]],
                "state": [], "changedPropIds": [changed]})
        response = request(1, "animals.page_current")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["response"]["animals"]
        self.assertEqual(payload["data"][0]["rank"], 11)
        self.assertEqual(payload["page_count"], 3)
        self.assertEqual(payload["selected_row_ids"], [])
        self.assertEqual(request(2, "db-sort.value").get_json()["response"]["animals"]["page_current"], 0)
        empty = request(0, "db-breed.value", "No match").get_json()["response"]
        self.assertEqual(empty["animals"]["data"], [])
        self.assertIn("No matching", empty["status"]["children"])
        visual_key = next(k for k in app.callback_map if "breeds.figure" in k)
        response = client.post("/_dash-update-component", json={
            "output": visual_key, "outputs": [{"id": "breeds", "property": "figure"}, {"id": "map", "property": "children"}],
            "inputs": [{"id": "animals", "property": "data", "value": payload["data"]},
                       {"id": "animals", "property": "selected_row_ids", "value": []}],
            "state": [], "changedPropIds": ["animals.data"]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("current page", response.get_json()["response"]["breeds"]["figure"]["layout"]["title"]["text"])


if __name__ == "__main__":
    unittest.main()
