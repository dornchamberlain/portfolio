# Milestone Four validation

Verified October 1, 2026 using Python 3.12, SQLAlchemy 2.0.54, and the pinned dashboard dependencies.

- 61 tests pass: 42 inherited dashboard/ranking tests and 19 SQLite tests.
- Temporary file databases exercise CRUD persistence, atomic rollback, repeated animal IDs, unique record IDs, direct database constraints, nulls, coordinate boundaries, input validation, projection, combined filters, sorting, paging, and stale-page handling.
- Injection-shaped text and apostrophes remain bound data. Invalid identifiers are rejected. Controlled errors and logs hide simulated secret query details.
- SQL ranking matches the prior Python algorithm for all profiles across multiple pages, with ties and missing data. SQL capture confirms LIMIT/OFFSET. Alternative sorting preserves preference ranks.
- Real Dash HTTP requests verify SQLite page two, rank 11, selection reset, page counts, changed-filter resets, empty results, and page-specific chart labels. CLI tests exercise import, duplicate rejection, read, update, and delete.
- Browser check: Reset reported 12 synthetic records; Water Rescue reported 11 dogs; page two retained rank 11; an unmatched breed displayed no matching records. Table, chart, and map loaded. This is not a full accessibility or cross-browser audit.
- The reproducible index experiment uses 20,000 synthetic records. Results agree before and after indexing. Query plans and timings are in index-results.json; this does not benchmark every dashboard query.
- Packaging verifies original source checksums and excludes .git, virtual environments, caches, SQLite files, and private .env configuration.

No live MongoDB, PostgreSQL, production data migration, concurrent-user load test, or hosted deployment is claimed. Dash emits an upstream DataTable deprecation warning; the pinned version passes the tests.
