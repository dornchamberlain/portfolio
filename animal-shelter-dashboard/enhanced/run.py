# Dashboard entry point. Importing this file does not start the server.
import logging
from shelter.config import Settings, ConfigurationError
from shelter.repository import RepositoryError
from shelter.app import create_app

# Load settings before startup and release the data source at shutdown.
def main():
    logging.basicConfig(level=logging.INFO)
    try:
        settings = Settings.from_env()
        app = create_app(settings)
    except (ConfigurationError, RepositoryError) as exc:
        raise SystemExit(str(exc)) from None
    try:
        app.run(host="127.0.0.1", port=settings.port, debug=False)
    # Cleanup still runs if the server exits because of an error.
    finally:
        app.shelter_repository.close()

if __name__ == "__main__":
    main()
