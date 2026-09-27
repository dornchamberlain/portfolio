#Score preference matches without claiming an animal is ready for rescue work.
from dataclasses import dataclass
import math
from .filters import PROFILES, validate_profile
from .records import number


# Keep each rescue role's preferences and weights together.
# Freezing the profile helps prevent accidental changes after it is created.
@dataclass(frozen=True)
class ScoringProfile:
    breeds: frozenset[str]
    sex: str
    min_age: float = 0
    max_age: float = 156
    weights: tuple = (50, 30, 20)

    def __post_init__(self):
        # Require a fixed collection of breeds and usable preference names.
        if (not isinstance(self.breeds, frozenset) or not self.breeds
                or any(not isinstance(b, str) or not b.strip() for b in self.breeds)
                or not isinstance(self.sex, str) or not self.sex.strip()):
            raise ValueError("Profile preferences must contain nonempty text.")
        # Reject missing or impossible age bounds instead of guessing a range.
        values = (self.min_age, self.max_age)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("Age bounds must be finite numbers.")
        if not 0 <= self.min_age <= self.max_age:
            raise ValueError("Age bounds must be ordered and nonnegative.")
        # Breed, age, and sex each need a weight. Together they must total 100.
        # Booleans are rejected even though Python treats them as numbers.
        if (not isinstance(self.weights, tuple) or len(self.weights) != 3
                or any(isinstance(w, bool) or not isinstance(w, (int, float))
                       or not math.isfinite(w) or w < 0 for w in self.weights)
                or sum(self.weights) != 100):
            raise ValueError("Three finite nonnegative weights must sum to 100.")


# Reuse the original rescue preferences so the breed lists stay in one place.
# These weights are examples for the project, not proven rescue suitability.
SCORING_PROFILES = {key: ScoringProfile(frozenset(breeds), sex)
                    for key, (breeds, sex) in PROFILES.items()}


def score_candidate(row, profile):
    # Score one cleaned animal record and explain how it earned its points.
    # Treat an invalid age as unknown so it cannot earn age points.
    age = number(row.get("age_upon_outcome_in_weeks"))
    if age is not None and age < 0:
        age = None
    # Store each criterion's name, value, and match result together.
    criteria = (
        ("Breed", row.get("breed"), row.get("breed") in profile.breeds),
        ("Age", age, age is not None and profile.min_age <= age <= profile.max_age),
        ("Sex", row.get("sex_upon_outcome"), row.get("sex_upon_outcome") == profile.sex),
    )
    score, explanations = 0, []
    # Pair each criterion with its weight and explain the points it earns.
    # Missing information earns zero without increasing the other weights.
    for (label, value, matches), weight in zip(criteria, profile.weights):
        points = weight if matches else 0
        score += points
        reason = "missing or invalid" if value is None or value == "" else ("matched" if matches else "not preferred")
        explanations.append(f"{label}: {reason} (+{points:g})")
    # Return a new dictionary so scoring leaves the original record unchanged.
    return {**row, "score": score, "score_explanation": "; ".join(explanations)}


def rank_records(records, profile):
    # Rank cleaned dog records before the table divides them into pages.
    validate_profile(profile)
    if profile == "RESET":
        # Reset includes every animal and does not add scores or ranks.
        return [dict(row) for row in records]
    rules = SCORING_PROFILES[profile]
    # Only dogs are rescue candidates, but they can still have a zero score.
    candidates = [score_candidate(row, rules) for row in records if row.get("animal_type") == "Dog"]
    # Put higher scores first, then known animal IDs before missing ones on ties.
    # Record ID breaks the final tie because an animal can have several records.
    candidates.sort(key=lambda row: (-row["score"], row.get("animal_id") is None,
                                    row.get("animal_id") or "", row["id"]))
    # Assign positions after sorting the full list, before the table makes pages.
    return [{**row, "rank": index} for index, row in enumerate(candidates, 1)]
