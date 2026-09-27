# Read connection settings from the environment instead of embedding them in the dashboard.
from dataclasses import dataclass, field
from pathlib import Path
import os

class ConfigurationError(ValueError):
    # This gives the startup code a way to identify a problem with the settings.
    pass

@dataclass(frozen=True)
# Keep related settings together as one object.
class Settings:
    mode: str
    data_file: Path
    # The URI may contain a password, so leave it out of the settings representation.
    mongo_uri: str = field(default="", repr=False)
    database: str = "aac"
    collection: str = "animals"
    port: int = 8050

    @classmethod
    # Tests can supply a dictionary without changing the shell environment.
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        mode = env.get("SHELTER_MODE", "demo")
        if mode not in {"demo", "mongo"}:
            raise ConfigurationError("SHELTER_MODE must be demo or mongo.")
        try:
            port = int(env.get("PORT", "8050"))
        except (TypeError, ValueError):
            raise ConfigurationError("PORT must be an integer from 1 to 65535.") from None
        if not 1 <= port <= 65535:
            raise ConfigurationError("PORT must be an integer from 1 to 65535.")
        uri = env.get("MONGODB_URI", "")
        if mode == "mongo" and not uri.startswith(("mongodb://", "mongodb+srv://")):
            raise ConfigurationError("Set MONGODB_URI to a MongoDB connection URI.")
        database = env.get("MONGODB_DATABASE", "aac").strip()
        collection = env.get("MONGODB_COLLECTION", "animals").strip()
        if not database or any(c in database for c in '/\\. "$*<>:|?') or not collection or collection.startswith("$") or "\x00" in collection:
            raise ConfigurationError("Database or collection name is invalid.")
        # Resolve sample data relative to this file, not the terminal's working directory.
        default = Path(__file__).resolve().parent.parent / "data" / "demo_animals.json"
        return cls(mode, Path(env.get("SHELTER_DATA_FILE", str(default))).expanduser().resolve(), uri, database, collection, port)
