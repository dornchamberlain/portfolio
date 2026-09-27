# Build the page and controls. Other files handle loading and ranking records.
from pathlib import Path
from dash import html, dcc, dash_table
from .records import FIELDS

ASSETS = Path(__file__).resolve().parent / "assets"

# The logo is optional; the dashboard can still open without the image file.
def build_layout(app, mode):
    branding = []
    if (ASSETS / "logo.png").is_file():
        branding.append(html.Img(src=app.get_asset_url("logo.png"), alt="Grazioso Salvare", style={"height": "100px"}))
    return html.Main([
        *branding,
        html.H1("Animal Shelter Dashboard"),
        html.P("Dorn Chamberlain | CS 499 Algorithms and Data Structures"),
        html.P("Demonstration with synthetic records" if mode == "demo" else "MongoDB animal records"),
        html.P("Preference score: breed 50 points, age 0–156 weeks 30 points, sex 20 points. Missing values earn zero. These demonstration weights do not establish training or rescue readiness."),
        html.Label("Rescue category", htmlFor="filter-type"),
        dcc.RadioItems(id="filter-type", options=[
            {"label": "Reset (Show All)", "value": "RESET"},
            {"label": "Water Rescue", "value": "WATER"},
            {"label": "Mountain or Wilderness Rescue", "value": "MOUNTAIN"},
            {"label": "Disaster or Individual Tracking", "value": "DISASTER"}], value="RESET"),
        html.P(id="status", role="status"),
        dash_table.DataTable(id="animals", columns=[{"name": f.replace("_", " ").title(), "id": f} for f in ("rank", "score", *FIELDS, "score_explanation")],
            data=[], page_size=10, page_action="native", sort_action="native", sort_mode="multi",
            filter_action="native", row_selectable="single", selected_row_ids=[],
            style_table={"overflowX": "auto"}, style_cell={"textAlign": "left", "padding": "8px"}),
        dcc.Graph(id="breeds"), html.H2("Selected animal location"), html.Div(id="map")
    ], style={"maxWidth": "1200px", "margin": "auto", "padding": "24px", "fontFamily": "Arial, sans-serif"})
