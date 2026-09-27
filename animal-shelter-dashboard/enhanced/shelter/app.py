# Build the Dash application without loading animal records during import.
from dash import Dash
from .config import Settings
from .layout import build_layout, ASSETS
from .repository import create_repository
from .service import DashboardService
from .callbacks import register_callbacks

# A supplied repository lets tests run without creating a database connection.
def create_app(settings=None, repository=None):
    settings = Settings.from_env() if settings is None else settings
    repository = create_repository(settings) if repository is None else repository
    try:
        app = Dash(__name__, assets_folder=str(ASSETS), title="Animal Shelter Dashboard")
        app.layout = build_layout(app, settings.mode)
        register_callbacks(app, DashboardService(repository))
        app.shelter_repository = repository
        return app
    except Exception:
        repository.close()
        raise
