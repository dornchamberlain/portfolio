# Milestone Four Database Enhancement

Dorn Chamberlain | CS 499 | October 1, 2026

The Animal Shelter Dashboard now uses SQLAlchemy 2.0 and SQLite for constrained storage, transactional CRUD, validated queries, and database pagination. It retains Milestone Three scoring. `original-sanitized` contains publicly redacted CS 340 comparison source; `enhanced` contains the application, sample records, tools, and tests. The narrative is a separate Word file.

## Start the SQLite dashboard

Extract the ZIP and open PowerShell in `enhanced`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage_db.py init
.\.venv\Scripts\python.exe manage_db.py import data/demo_animals.json
$env:SHELTER_MODE = "sqlite"
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8050. Import loads 12 synthetic records. The ZIP excludes generated databases; setup creates `enhanced/data/shelter.sqlite3`. Skip import if the sample records are already loaded. Initialization preserves existing records; repeated imports are rejected because record IDs must be unique. For later runs, set the mode and run `run.py`. Without a mode setting, the inherited JSON demo remains the default and does not exercise SQLite. `.env.example` is documentation, not an automatically loaded configuration file.

To use another file, pass `--database "D:/data/example.sqlite3"` before the management command and set `SHELTER_SQLITE_FILE` to the same path for the dashboard. Its parent folder must exist. Default paths resolve from the application folder, independent of the terminal directory. `PORT` changes the local port. SQLite needs no database credentials.

## Schema and integrity

One row in `animal_records` represents one shelter outcome record, not an animal's entire history. The required text primary key `id` is unique and preserves dashboard selection identity. Repeated `animal_id` values are allowed. Separating animals and outcomes would require history and identity information absent from these samples; the schema does not invent those relationships.

| Fields | Rules |
| --- | --- |
| id | Required unique primary key; 1-120 trimmed characters |
| animal_id, name, animal_type, breed, sex_upon_outcome | Nullable text; 1-200 characters when present |
| age_upon_outcome_in_weeks | Nullable finite number; nonnegative |
| location_lat, location_long | Nullable numbers within +/-90 and +/-180 |

Unknown optional values use SQL NULL. Writes reject invalid values instead of silently changing them to unknown. Python validation rejects wrong types, numeric booleans, non-finite numbers, oversized text, and unknown fields. SQLite constraints independently protect identity, lengths, numeric storage, and ranges. Updates cannot change the primary key. The SQLite-specific `typeof` checks need adaptation for PostgreSQL.

Each operation owns a short transaction. Batch imports are atomic: a constraint failure rolls back the full batch. Explicit BEGIN keeps count and page reads in one snapshot. Connections return to the pool after operations; shutdown disposes the engine. Controlled errors distinguish failures from empty results without displaying submitted values or database paths.

## CRUD and validated queries

The dashboard is read-only. The repository and `manage_db.py` provide local writes. Create files contain one JSON object; update files contain changed fields; imports contain lists. Example files are in `enhanced/data/crud_examples`.

```powershell
.\.venv\Scripts\python.exe manage_db.py create data/crud_examples/create.json
.\.venv\Scripts\python.exe manage_db.py read --profile WATER --page 0 --page-size 5
.\.venv\Scripts\python.exe manage_db.py update example-record data/crud_examples/update.json
.\.venv\Scripts\python.exe manage_db.py delete example-record
```

`read_page` supports selected fields; exact animal type, breed, and sex filters; minimum/maximum age; validated sorting and direction; and zero-based pages of 1-100 rows. Record ID breaks sort ties. Invalid fields and ranges are rejected. SQLAlchemy binds submitted values; column identifiers come from an allowlist. The UI exposes type/breed filters, rank/name/breed/age sorting, and ten-row pages. The repository supports the additional options without exposing raw SQL input.

## Ranking and pagination

SQLite computes the same preference scores as Milestone Three and assigns sequential ranks with a window function before LIMIT/OFFSET. Ties use known animal IDs first, then animal ID and unique record ID. Zero-score dogs remain candidates. Reset includes all types with blank ranks and scores. Filters recompute ranks within the matching set; other sort choices retain those rank numbers. Tests compare SQL and Python results for all profiles across multiple pages.

Only the current page reaches the browser. Chart and map labels identify that page-local scope. Paging clears selection; changing category, filters, or sort resets to page one. Stale pages are clamped to the last available page. Ranking still processes the matching set and can require sorting: pagination reduces transferred rows and Python result memory, not the full database ranking cost. Large offsets add work; keyset pagination remains a future option.

## Index evaluation

The composite index `ix_type_breed_id (animal_type, breed, id)` supports exact type/breed searches and stable ID sorting. `evaluate_index.py` compares one projected, paged query on 20,000 synthetic records before and after indexing. `enhanced/index-results.json` records identical result IDs, query plans, and 20-run median timings. The plan changes from a primary-key index scan to a covering composite-index search. The recorded medians were 0.2002 ms before and 0.0211 ms after. This small local experiment is not a production speed guarantee or a ranking benchmark. Indexes consume storage and add write work; this index does not cover every sort or calculated score.

## Scope and verification

SQLite provides a portable local demonstration. File access uses operating-system permissions. Authentication, authorization, encryption, concurrent-user load testing, and hosted deployment are outside this milestone. PostgreSQL requires schema adaptations and separate testing. The original MongoDB service is unavailable and has not been retested. Historical MongoDB and JSON modes remain for comparison. This is an application/schema migration with synthetic data, not a migration of unavailable production records.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe evaluate_index.py
```

All 61 tests passed. See `enhanced/VALIDATION.md` and `enhanced/test-results.txt`. Public comparison hashes are in `PUBLIC_SHA256.txt`; changes are documented in `PUBLIC_COMPARISON.md`. Comments use consistent Python `#` syntax with purpose, decision, and edge-case explanations. Untouched originals are retained separately for course submission.

## References

- SQLAlchemy transactions and parameters: https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html
- SQLite query planning: https://www.sqlite.org/queryplanner.html
- SQLite query-plan output: https://www.sqlite.org/eqp.html
