# Load one database page while keeping ranking and selection consistent.
from dash import Input, Output, ctx
from .repository import RepositoryError
from .presentation import chart, map_content


def register_sql_callbacks(app, repository):
    @app.callback(Output("animals", "data"), Output("status", "children"),
                  Output("animals", "page_count"), Output("animals", "page_current"),
                  Output("animals", "selected_row_ids"),
                  Input("filter-type", "value"), Input("animals", "page_current"),
                  Input("db-type", "value"), Input("db-breed", "value"), Input("db-sort", "value"))
    def load(profile, page, animal_type, breed, sort):
        try:
            filters = {}
            if animal_type:
                filters["animal_type"] = animal_type
            if breed:
                filters["breed"] = breed
            # A new filter or sort starts on page one instead of keeping an old offset.
            if ctx.triggered_id != "animals":
                page = 0
            result = repository.read_page(profile=profile, filters=filters, sort=sort, page=page)
            count = max(1, (result.total + result.page_size - 1) // result.page_size)
            message = f"{result.total} matching records. Page {result.page + 1} of {count}."
            if not result.rows:
                message = "No matching animal records."
            return result.rows, message, count, result.page, []
        except (ValueError, RepositoryError) as exc:
            return [], str(exc), 1, 0, []

    @app.callback(Output("breeds", "figure"), Output("map", "children"),
                  Input("animals", "data"), Input("animals", "selected_row_ids"))
    def visualize(rows, selected_ids):
        # Page-local summaries avoid loading the complete database into the browser.
        figure = chart(rows)
        figure.update_layout(title="Top 10 breeds on the current page")
        return figure, map_content(rows, selected_ids)
