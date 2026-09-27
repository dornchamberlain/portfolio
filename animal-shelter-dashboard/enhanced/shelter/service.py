# Load and check animal records before scoring and ranking them.
from dataclasses import dataclass
from .filters import validate_profile
from .ranking import rank_records
from .records import normalize_records, DataValidationError
from .repository import AnimalRepository, RepositoryError

@dataclass
# Return rows with a status message so empty results and errors can be explained.
class DashboardResult:
    rows: list[dict]
    message: str

# Let tests supply sample records instead of connecting to a real database.
class DashboardService:
    def __init__(self, repository: AnimalRepository):
        self.repository = repository

    # Validate the rescue choice before reading and preparing records.
    def load(self, profile):
        try:
            validate_profile(profile)
            rows = rank_records(normalize_records(self.repository.read_all()), profile)
            message = (f"{len(rows)} matching records." if profile == "RESET" else
                       f"{len(rows)} dogs ranked by preference score. Scores do not establish rescue readiness.")
            return DashboardResult(rows, message if rows else "No matching animal records.")
        except (ValueError, DataValidationError, RepositoryError) as exc:
            # These messages explain the problem without including database connection details.
            return DashboardResult([], str(exc))
