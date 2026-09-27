# Keep the original rescue preferences here so ranking can reuse them.
# The old strict filter remains for comparison; the dashboard now uses ranking.
from .records import number

PROFILES = {
    "WATER": ({"Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland"}, "Intact Female"),
    "MOUNTAIN": ({"German Shepherd", "Alaskan Malamute", "Old English Sheepdog", "Siberian Husky", "Rottweiler"}, "Intact Male"),
    "DISASTER": ({"Doberman Pinscher", "German Shepherd", "Golden Retriever", "Bloodhound", "Rottweiler"}, "Intact Male"),
}

# An unknown rescue choice is an input error, not a request to show all records.
def validate_profile(profile):
    if not isinstance(profile, str) or profile not in {"RESET", *PROFILES}:
        raise ValueError("Select a valid rescue category or Reset.")

# A record must meet every condition in the original rescue profile.
def filter_records(records, profile):
    validate_profile(profile)
    if profile == "RESET":
        return list(records)
    breeds, sex = PROFILES[profile]
    result = []
    for row in records:
        age = number(row.get("age_upon_outcome_in_weeks"))
        # Age boundaries: zero and 156 weeks are allowed; missing and negative ages are excluded.
        if (row.get("animal_type") == "Dog" and row.get("breed") in breeds
                and row.get("sex_upon_outcome") == sex and age is not None and 0 <= age <= 156):
            result.append(row)
    return result
