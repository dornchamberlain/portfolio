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
        html.P("Dorn Chamberlain | CS 499 Database Enhancement"),
        html.P("Demonstration with synthetic records" if mode == "demo" else ("SQLite animal records" if mode == "sqlite" else "MongoDB animal records")),
        html.P("Preference score: breed 50 points, age 0–156 weeks 30 points, sex 20 points. Missing values earn zero. These demonstration weights do not establish training or rescue readiness."),
        html.Label("Rescue category", htmlFor="filter-type"),
        dcc.RadioItems(id="filter-type", options=[
            {"label": "Reset (Show All)", "value": "RESET"},
            {"label": "Water Rescue", "value": "WATER"},
            {"label": "Mountain or Wilderness Rescue", "value": "MOUNTAIN"},
            {"label": "Disaster or Individual Tracking", "value": "DISASTER"}], value="RESET"),
        *([html.Label("Animal type", htmlFor="db-type"),
           dcc.Dropdown(id="db-type", options=["Dog", "Cat"], placeholder="All types"),
           html.Label("Exact breed", htmlFor="db-breed"),
           dcc.Input(id="db-breed", type="text", debounce=True, placeholder="Any breed", maxLength=200),
           html.Label("Sort order", htmlFor="db-sort"),
           dcc.Dropdown(id="db-sort", clearable=False, value="rank", options=[
               {"label": "Preference rank or record ID", "value": "rank"},
               {"label": "Name", "value": "name"},
               {"label": "Breed", "value": "breed"},
               {"label": "Age", "value": "age_upon_outcome_in_weeks"}]),
           html.P("The chart and map show the current page. Rankings cover all matching dogs.")]
          if mode == "sqlite" else []),
        html.P(id="status", role="status"),
        dash_table.DataTable(id="animals", columns=[{"name": f.replace("_", " ").title(), "id": f} for f in ("rank", "score", *FIELDS, "score_explanation")],
            data=[], page_current=0, page_size=10, page_action="custom" if mode == "sqlite" else "native",
            sort_action="none" if mode == "sqlite" else "native", sort_mode="multi",
            filter_action="none" if mode == "sqlite" else "native", row_selectable="single", selected_row_ids=[],
            style_table={"overflowX": "auto"}, style_cell={"textAlign": "left", "padding": "8px"}),
        dcc.Graph(id="breeds"), html.H2("Selected animal location"), html.Div(id="map")
    ], style={"maxWidth": "1200px", "margin": "auto", "padding": "24px", "fontFamily": "Arial, sans-serif"})
