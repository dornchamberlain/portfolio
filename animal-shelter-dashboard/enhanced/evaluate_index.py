# Compare the same query before and after adding the planned composite index.
import json
from pathlib import Path
import statistics
import tempfile
import time
from shelter.sql_repository import SQLiteRepository


def evaluate():
    with tempfile.TemporaryDirectory() as folder:
        repo = SQLiteRepository(Path(folder) / "index-test.sqlite3")
        try:
            repo.initialize()
            rows = [{"id": f"sample-{i:06d}", "animal_type": "Dog" if i % 4 else "Cat",
                     "breed": f"Breed {i % 97:02d}"} for i in range(20000)]
            repo.create_many(rows)
            result = {"records": len(rows), "repetitions": 20, "synthetic": True}
            query = "SELECT id, breed FROM animal_records WHERE animal_type = ? AND breed = ? ORDER BY id LIMIT 10 OFFSET 10"
            with repo.transaction() as connection:
                connection.exec_driver_sql("DROP INDEX ix_type_breed_id")
                for label in ["before", "after"]:
                    if label == "after":
                        connection.exec_driver_sql("CREATE INDEX ix_type_breed_id ON animal_records (animal_type, breed, id)")
                    connection.exec_driver_sql("ANALYZE")
                    plan = [r[3] for r in connection.exec_driver_sql("EXPLAIN QUERY PLAN " + query, ("Dog", "Breed 11"))]
                    elapsed = []
                    for _ in range(result["repetitions"]):
                        start = time.perf_counter()
                        matches = connection.exec_driver_sql(query, ("Dog", "Breed 11")).all()
                        elapsed.append((time.perf_counter() - start) * 1000)
                    result[label] = {"plan": plan, "median_ms": round(statistics.median(elapsed), 4),
                                     "ids": [r[0] for r in matches]}
            assert result["before"]["ids"] == result["after"]["ids"]
            return result
        finally:
            repo.close()


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
