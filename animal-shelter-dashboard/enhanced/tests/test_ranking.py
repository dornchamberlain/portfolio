# Use made-up animals to check scores, ranking, and invalid settings.
import itertools
import math
import unittest
from shelter.ranking import ScoringProfile, SCORING_PROFILES, rank_records, score_candidate
from shelter.records import normalize_records


# Start with one sample dog and change only what each test needs.
def dog(key="1", **changes):
    row = dict(id=key, animal_id="A", animal_type="Dog", breed="Labrador Retriever Mix",
               age_upon_outcome_in_weeks=52, sex_upon_outcome="Intact Female")
    return {**row, **changes}


class RankingTests(unittest.TestCase):
    def rank(self, rows, profile="WATER"):
        # Clean the records first, just as the dashboard service does.
        return rank_records(normalize_records(rows), profile)

    def test_hand_calculated_scores_and_order(self):
        # These examples should earn 50, 80, and 100 points before sorting.
        rows = [dog("sex-age", breed="Other"), dog("breed-age", sex_upon_outcome="Other"), dog("all")]
        result = self.rank(rows)
        self.assertEqual([(r["id"], r["score"], r["rank"]) for r in result],
                         [("all", 100, 1), ("breed-age", 80, 2), ("sex-age", 50, 3)])

    def test_all_profiles(self):
        # Give each rescue role a dog that matches all three preferences.
        for name, breed, sex in [("WATER", "Newfoundland", "Intact Female"),
                                  ("MOUNTAIN", "Siberian Husky", "Intact Male"),
                                  ("DISASTER", "Bloodhound", "Intact Male")]:
            self.assertEqual(self.rank([dog(breed=breed, sex_upon_outcome=sex)], name)[0]["score"], 100)

    def test_boundary_ages_are_preferences(self):
        # Breed and sex still earn 70 points when age earns none.
        # Both age endpoints are allowed, and numeric text can be cleaned.
        for age, expected in [(0,100),(156,100),(156.01,70),(-1,70),(None,70),
                              (True,70),(math.nan,70),(math.inf,70),("bad",70),("52",100)]:
            with self.subTest(age=age):
                self.assertEqual(self.rank([dog(age_upon_outcome_in_weeks=age)])[0]["score"],expected)

    def test_missing_explanation_and_zero_score(self):
        # Missing information should be explained, not filled in with guesses.
        result = self.rank([dog(breed=None, age_upon_outcome_in_weeks=None, sex_upon_outcome=None)])[0]
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["score_explanation"].count("missing or invalid"), 3)

    def test_ties_independent_of_input_order(self):
        # Try all 24 orders, including repeated animal IDs and a missing ID.
        rows = [dog("2", animal_id="A"), dog("1", animal_id="A"),
                dog("3", animal_id="B"), dog("4", animal_id=None)]
        for order in itertools.permutations(rows):
            self.assertEqual([r["id"] for r in self.rank(order)], ["1","2","3","4"])

    def test_non_dogs_excluded_reset_retains_all(self):
        # Rescue ranking includes dogs; Reset also includes the other records.
        rows = [dog(), dog("cat", animal_type="Cat"), dog("unknown", animal_type=None)]
        self.assertEqual(len(self.rank(rows)), 1)
        reset = self.rank(rows, "RESET")
        self.assertEqual(len(reset),3)
        self.assertNotIn("score",reset[0])

    def test_best_beyond_first_page(self):
        # Put the best match after 20 weaker matches so it starts beyond page one.
        rows = [dog(str(i), breed="Other") for i in range(20)] + [dog("best")]
        self.assertEqual(self.rank(rows)[:10][0]["id"], "best")
        self.assertEqual(len(self.rank(rows)),21)

    def test_empty_and_invalid_profile(self):
        # No records is a valid result, but an unknown rescue role is an error.
        self.assertEqual(self.rank([]),[])
        for value in [None, [], {}, "INVALID"]:
            with self.assertRaises(ValueError): self.rank([],value)

    def test_no_source_mutation(self):
        # Keep a copy to check that ranking leaves the input unchanged.
        rows = normalize_records([dog()])
        before = [dict(row) for row in rows]
        rank_records(rows,"WATER")
        self.assertEqual(rows,before)

    def test_weight_validation(self):
        # Reject weights that could make the scores invalid or misleading.
        for weights in [(50,30,-20),(50,30,True),(50,30,math.inf),(50,30,math.nan),
                        (0,0,0),(50,30),(50,30,"20"),[50,30,20]]:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                ScoringProfile(frozenset({"A"}),"B",weights=weights)

    def test_profile_validation(self):
        # Check age ranges and preference names before they reach scoring.
        for bounds in [(-1,156),(157,156),(0,math.inf),(True,156)]:
            with self.assertRaises(ValueError): ScoringProfile(frozenset({"A"}),"B",*bounds)
        for breeds,sex in [(frozenset(),"B"),(frozenset({""}),"B"),(frozenset({"A"}),"")]:
            with self.assertRaises(ValueError): ScoringProfile(breeds,sex)

    def test_configurable_weights(self):
        # Changing the profile should change points without rewriting scoring.
        profile=ScoringProfile(frozenset({"Labrador Retriever Mix"}),"Intact Female",weights=(20,40,40))
        self.assertEqual(score_candidate(dog(sex_upon_outcome="Other"),profile)["score"],60)


if __name__ == "__main__":
    unittest.main()
