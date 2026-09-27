# Check and normalize incoming records before passing them to the table and map.
import math
from collections.abc import Mapping

FIELDS = ("animal_id", "name", "animal_type", "breed", "sex_upon_outcome",
          "age_upon_outcome_in_weeks", "location_lat", "location_long")

class DataValidationError(ValueError):
    # This separates a record-format problem from a failed database request.
    pass

# Treat unusable numbers as missing. Watch for True, which Python converts to 1.
def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if math.isfinite(result) else None

# One animal can have multiple records, so animal_id is not a unique row identifier.
def normalize_records(records):
    result, ids = [], set()
    for raw in records:
        if not isinstance(raw, Mapping):
            raise DataValidationError("Each animal record must be an object.")
        key = raw.get("_id", raw.get("id"))
        if key is None or isinstance(key, (bool, dict, list)) or not str(key).strip():
            raise DataValidationError("Each record requires a stable id or MongoDB _id.")
        key = str(key)
        # Duplicate record IDs would make it unclear which animal the user selected.
        if key in ids:
            raise DataValidationError("Record IDs must be unique; animal IDs may repeat.")
        ids.add(key)
        record = {"id": key}
        for field in FIELDS:
            value = raw.get(field)
            if field in {"age_upon_outcome_in_weeks", "location_lat", "location_long"}:
                value = number(value)
                # A negative age stays unknown rather than being changed to a guessed age.
                if field == "age_upon_outcome_in_weeks" and value is not None and value < 0:
                    value = None
            else:
                value = value.strip() if isinstance(value, str) else None
                value = value or None
            record[field] = value
        result.append(record)
    return result
