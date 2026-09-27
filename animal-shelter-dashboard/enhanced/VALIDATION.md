# Milestone Three validation

September 27, 2026. Python 3.12 on Windows. All 42 unittest tests passed: 30 inherited tests (with the callback contract updated) and 12 new ranking tests. See test-results.txt for the captured run.

New coverage includes hand-calculated 100/80/50 scores, all three profiles, age boundaries, malformed and missing ages, explicit missing-data explanations, zero-score candidates, all 24 permutations of tied records, duplicate animal IDs, non-dog exclusion, Reset behavior, the best candidate after 20 lower-scoring records, invalid profiles/weights/bounds, configurable weights, and no mutation of inputs.

Dash HTTP integration tests exercise layout and dependency endpoints, category loading with score output, clearing page/selection/sort state, and chart/map callbacks. These are server-side integration tests, not a visual browser review. Live MongoDB access and map tile availability were not tested. The original application was not executed. No performance speedup or empirical rescue suitability is claimed.

Dash emits a DataTable deprecation warning for a future major version. The pinned version passes the tested interactions. Full-list ranking trades memory and sorting time for transparent complete results.
