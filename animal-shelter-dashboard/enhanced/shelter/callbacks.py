# Connect the page controls to the data-loading and display functions.
from dash import Input, Output
from .presentation import chart, map_content

# The service handles record processing; callbacks pass results to the page.
def register_callbacks(app, service):
    @app.callback(Output("animals", "data"), Output("status", "children"),
                  Output("animals", "selected_row_ids"), Output("animals", "page_current"),
                  Output("animals", "sort_by"), Input("filter-type", "value"))
    # Ask the service for rows and a status message for the selected category.
    def load(profile):
        result = service.load(profile)
        # Start each category on page one and clear the previous selection.
        # Clear table sorting too, so the new ranking appears in its intended order.
        return result.rows, result.message, [], 0, []

    @app.callback(Output("breeds", "figure"), Output("map", "children"),
                  Input("animals", "derived_virtual_data"), Input("animals", "selected_row_ids"))
    # Use the filtered table rows to keep the chart and map in sync.
    def visualize(rows, selected_ids):
        return chart(rows), map_content(rows, selected_ids)
