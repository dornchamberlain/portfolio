# Public comparison copy: historical credentials redacted.
# Setup the Jupyter version of Dash
from jupyter_dash import JupyterDash

# Configure the necessary Python module imports for dashboard components
import dash_leaflet as dl
from dash import dcc, html
import plotly.express as px
from dash import dash_table
from dash.dependencies import Input, Output, State
import base64
JupyterDash.infer_jupyter_proxy_config()

# Configure OS routines
import os

# Configure the plotting routines
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


####  #####
# change animal_shelter and AnimalShelter to match your CRUD Python module file name and class name
from CRUD_Python_Module import AnimalShelter

###########################
# Data Manipulation / Model
###########################

username = "REDACTED_FOR_PUBLIC_PORTFOLIO"
password = "REDACTED_FOR_PUBLIC_PORTFOLIO"
# Connect to database via CRUD Module
db = AnimalShelter(username, password)

# class read method must support return of list object and accept projection json input
# sending the read method an empty document requests all documents be returned
df = pd.DataFrame.from_records(db.read({}))

# MongoDB v5+ is going to return the '_id' column and that is going to have an
# invlaid object type of 'ObjectID' - which will cause the data_table to crash - so we remove
# it in the dataframe here. The df.drop command allows us to drop the column. If we do not set
# inplace=True - it will reeturn a new dataframe that does not contain the dropped column(s)
df.drop(columns=['_id'], inplace=True)

# Confirm the database returned records
print("Number of records loaded:", len(df))

## Debug
# print(len(df.to_dict(orient='records')))
# print(df.columns)


#########################
# Dashboard Layout / View
#########################
app = JupyterDash(__name__)

# Add in Grazioso Salvare’s logo
logo_path = os.path.join(os.getcwd(), "Grazioso Salvare Logo.png")
encoded_image = base64.b64encode(open(logo_path, "rb").read()).decode()

# Useful if the image breaks again
# print("Current working directory:", os.getcwd())
# print("Logo path being used:", logo_path)

# Place the HTML image tag in the line below into the app.layout code according to your design
# Also remember to include a unique identifier such as your name or date

app.layout = html.Div([

    # Header: Logo + unique identifier (name)
    html.Div([
        html.Img(
            src="data:image/png;base64,{}".format(encoded_image),
            style={"height": "120px"}
        ),
        html.H2("CS-340 Dashboard - Dorn Chamberlain")
    ], style={"textAlign": "center"}),

    html.Hr(),

    # Interactive filtering options (radio buttons)
    html.Div([
        html.H4("Rescue Type Filter"),
        dcc.RadioItems(
            id="filter-type",
            options=[
                {"label": "Reset (Show All)", "value": "RESET"},
                {"label": "Water Rescue", "value": "WATER"},
                {"label": "Mountain or Wilderness Rescue", "value": "MOUNTAIN"},
                {"label": "Disaster or Individual Tracking", "value": "DISASTER"},
            ],
            value="RESET",
            labelStyle={"display": "inline-block", "marginRight": "20px"}
        )
    ], style={"textAlign": "center"}),

    html.Hr(),

    # Data table (interactive + user-friendly features)
    dash_table.DataTable(
        id="datatable-id",
        columns=[{"name": i, "id": i, "deletable": False, "selectable": True} for i in df.columns],
        data=df.to_dict("records"),

        # These features make the table easier for the client to use
        page_size=10,
        page_action="native",
        sort_action="native",
        sort_mode="multi",
        filter_action="native",

        # Single-row selection makes the map behavior predictable
        row_selectable="single",
        selected_rows=[0],
        column_selectable="single",

        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "5px", "whiteSpace": "normal", "height": "auto"},
        style_header={"fontWeight": "bold"}
    ),

    html.Br(),
    html.Hr(),

    # This sets up the dashboard so that your chart and your geolocation chart are side-by-side
    html.Div(
        className="row",
        style={"display": "flex"},
        children=[
            html.Div(
                id="graph-id",
                className="col s12 m6",
            ),
            html.Div(
                id="map-id",
                className="col s12 m6",
            )
        ]
    )
])

#############################################
# Interaction Between Components / Controller
#############################################

@app.callback(
    Output("datatable-id", "data"),
    [Input("filter-type", "value")]
)
def update_dashboard(filter_type):
    """
    Callback filters the data shown in the table.
    The table then drives the chart and the map since they use derived_virtual_data.
    """

    # Reset (unfiltered)
    if filter_type == "RESET":
        data = db.read({})

    # Water Rescue
    elif filter_type == "WATER":
        data = db.read({
            "animal_type": "Dog",
            "breed": {"$in": ["Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland"]},
            "sex_upon_outcome": "Intact Female",
            "age_upon_outcome_in_weeks": {"$lte": 156}
        })

    # Mountain or Wilderness Rescue
    elif filter_type == "MOUNTAIN":
        data = db.read({
            "animal_type": "Dog",
            "breed": {"$in": ["German Shepherd", "Alaskan Malamute", "Old English Sheepdog", "Siberian Husky", "Rottweiler"]},
            "sex_upon_outcome": "Intact Male",
            "age_upon_outcome_in_weeks": {"$lte": 156}
        })

    # Disaster or Individual Tracking
    elif filter_type == "DISASTER":
        data = db.read({
            "animal_type": "Dog",
            "breed": {"$in": ["Doberman Pinscher", "German Shepherd", "Golden Retriever", "Bloodhound", "Rottweiler"]},
            "sex_upon_outcome": "Intact Male",
            "age_upon_outcome_in_weeks": {"$lte": 156}
        })

    else:
        data = db.read({})

    # Convert to DataFrame and remove _id if it exists
    dff = pd.DataFrame.from_records(data)
    if "_id" in dff.columns:
        dff.drop(columns=["_id"], inplace=True)

    return dff.to_dict("records")


# Display the breeds of animal based on quantity represented in
# the data table
@app.callback(
    Output("graph-id", "children"),
    [Input("datatable-id", "derived_virtual_data")]
)
def update_graphs(viewData):
    """
    This chart updates based on what is currently visible in the table.
    I used a simple bar chart showing the top 10 breeds (by count) because it is easy to read.
    """
    if viewData is None:
        dff = df
    else:
        dff = pd.DataFrame.from_dict(viewData)

    # Simple, safe chart: top 10 breeds by count
    if "breed" not in dff.columns or len(dff) == 0:
        # If the filter returns no records, show an empty chart with a message
        fig = px.bar(title="No data available for this filter")
        return [dcc.Graph(figure=fig)]

    breed_counts = (
        dff["breed"].fillna("Unknown")
        .value_counts()
        .head(10)
        .reset_index()
    )
    breed_counts.columns = ["breed", "count"]

    fig = px.bar(breed_counts, x="breed", y="count", title="Top 10 Breeds (Current Filter)")

    return [dcc.Graph(figure=fig)]


# This callback will highlight a cell on the data table when the user selects it
@app.callback(
    Output('datatable-id', 'style_data_conditional'),
    [Input('datatable-id', 'selected_columns')]
)
def update_styles(selected_columns):
    # Student note: selected_columns can be None at startup, so I default to an empty list
    if not selected_columns:
        selected_columns = []

    return [{
        'if': {'column_id': i},
        'background_color': '#D2F3FF'
    } for i in selected_columns]

# This callback will update the geo-location chart for the selected data entry
# derived_virtual_data will be the set of data available from the datatable in the form of
# a dictionary.
# derived_virtual_selected_rows will be the selected row(s) in the table in the form of
# a list. For this application, we are only permitting single row selection so there is only
# one value in the list.
# The iloc method allows for a row, column notation to pull data from the datatable
@app.callback(
    Output("map-id", "children"),
    [Input("datatable-id", "derived_virtual_data"),
     Input("datatable-id", "derived_virtual_selected_rows")]
)
def update_map(viewData, index):
    # Make the map show immediately by defaulting to the first row
    if viewData is None:
        return

    dff = pd.DataFrame.from_dict(viewData)
    if len(dff) == 0:
        return

    # Default to first row if nothing is selected
    if not index:
        row = 0
    else:
        row = index[0]

    # Austin TX is at [30.75,-97.48]
    # Dataset includes latitude/longitude columns used here (same as the starter code)
    return [
        dl.Map(
            style={"width": "1000px", "height": "500px"},
            center=[30.75, -97.48],
            zoom=10,
            children=[
                dl.TileLayer(id="base-layer-id"),
                # Marker with tool tip and popup
                # Column 13 and 14 define the grid-coordinates for the map
                # Column 4 defines the breed for the animal
                # Column 9 defines the name of the animal
                dl.Marker(
                    position=[dff.iloc[row, 13], dff.iloc[row, 14]],
                    children=[
                        dl.Tooltip(dff.iloc[row, 4]),
                        dl.Popup([
                            html.H1("Animal Name"),
                            html.P(dff.iloc[row, 9])
                        ])
                    ]
                )
            ]
        )
    ]


# Run app and display result in jupyterlab mode, note, if you have previously run a prior app, the default port of 8050 may not be available, if so, try setting an alternate port.
app.run_server()



