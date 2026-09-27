# Milestone Three Algorithms and Data Structures

Dorn Chamberlain

This enhancement extends the Milestone Two Animal Shelter Dashboard with explainable rescue preference scoring. The standalone enhanced application and tests are in `enhanced`. Historical CS 340 originals are kept in the private coursework files and are not included in this public copy because they contain old credentials and notebook output.

## Run

From `enhanced`, using Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8050. Demo mode uses the inherited 12 synthetic records. No database is required. Map tiles require network access. Run tests with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

## Algorithm and data structures

`ranking.py` looks up a frozen scoring profile in a dictionary. The preferred dog breeds are stored in a frozenset. Each dog record gets 50 points if the breed matches one of the preferred breeds, 30 points for age between 0 and 156 weeks inclusive, and 20 points for the sex preferred by the profile. These are example, configurable weights based on the original criteria, not empirically derived weights for predicting suitability as a rescue dog. All dog records are possible matches including records with 0 points. Non-dog animals and unknown animal types are excluded from rescue matching. Reset displays all normalized records without scoring.

The score function computes a new results dictionary. It assigns points and explanations for each criterion. Missing or invalid values get 0 points without penalizing the other criteria (i.e. the other criteria are not down-weighted). This avoids giving incomplete records an unrealistically high percentage score. The list of results is sorted by descending score, ascending animal ID, and then by unique record ID. Text fields (animal IDs and record IDs) are sorted lexicographically. When scores tie, records with missing animal IDs come after records with known IDs. Ties are broken by unique record ID. Rank is the sequential rank (Each record receives a separate rank, even when scores tie.). Record IDs must be present and unique. Animal IDs can be repeated.

The service will normalize the data before scoring. Numeric booleans, non-finite numbers, negative ages, and unparsable ages will become unknown. Profile building will reject invalid age bound/weight combinations; weights must be three finite, non-negative numbers that add up to 100. Breed and sex matching will continue to be exact and case-sensitive, and will adhere to the same validity constraints as the rest of the data set.

The algorithm scores the entire candidate list before the table breaks it up into pages of ten rows. Searching on a rescue category resets any prior choices of sorting, selection, and page position. The user is then free to further sort the table (the Rank column holds the original sorting of the algorithm). The chart reflects the records remaining after table filtering, and map selection is by stable record IDs.

Scoring complexity is O(nm), assuming bounded field lengths and average constant-time set lookups. Sorting complexity is O(n log n). Explanations per criterion are stored for scorers, which uses O(nm) memory (or O(n) if there are 3 fixed criteria). The strict filter is O(n), so the ranking (which adds work to give more information, but does not claim any speed improvements) is only worth the extra information. Full list ranking requires more memory per page than scoring individual pages (to avoid missing possible top-scoring pages towards the end of the list), but avoids the redundant lookup. Consider evaluating bounded top-k page ranking, or database-assisted ranking, for much larger datasets.

## Architecture and scope

The new `ranking.py` separates scoring from ranking. `service.py` selects the ranking flow, `layout.py` exposes score and explanations, and `callbacks.py` clears stale table sort state. The old `filters.py` remains as a reference and source of original breed/sex preferences; the application now calls `rank_records`, not the old strict filter. Existing normalization, repository, map, chart, and configuration responsibilities remain in their modules.

The MongoDB mode is still available via the environment variables in enhanced/.env.example. The file is for documentation purposes and is not automatically loaded. SQLite migration is not implemented in this milestone. The tests are using fake data and mock database calls. A live database or original application run is not claimed.

Original files contained historical credentials and notebook output that could be used by someone to compare against an assignment. Review and clean the originals before publishing to a public ePortfolio. Improved code uses environment variables for configuration and does not contain any copied credentials.

See `enhanced/VALIDATION.md` for verification and `enhanced/test-results.txt` for the recorded test run. The narrative is a separate Word deliverable.
