# Chart and map helpers, kept separate to make the callbacks easier to follow.
from collections import Counter
from dash import html
import dash_leaflet as dl
import plotly.graph_objects as go
from .records import number

# Count breeds across the filtered records. Alphabetical order breaks count ties.
def breed_counts(rows):
    counts = Counter(row.get("breed") or "Unknown" for row in (rows or []))
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]

# Sorting changes row positions, so selection follows the record ID.
def selected_record(rows, selected_ids):
    if not rows:
        return None, "No animal records to display."
    if not selected_ids:
        return rows[0], ""
    # A filtered-out selection should show a message, not a different animal.
    record = next((row for row in rows if row.get("id") == selected_ids[0]), None)
    return record, "" if record else "The selected record is no longer in these results. Select another row."

# Missing or out-of-range coordinates cannot produce a valid map marker.
def coordinates(row):
    lat, lon = number(row.get("location_lat")), number(row.get("location_long"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return [lat, lon]

# These counts cover all filtered rows, including rows on other table pages.
def chart(rows):
    counts = breed_counts(rows)
    fig = go.Figure(go.Bar(x=[item[0] for item in counts], y=[item[1] for item in counts]))
    fig.update_layout(title="Top 10 breeds across all filtered table records", xaxis_title="Breed", yaxis_title="Records")
    if not counts:
        fig.add_annotation(text="No records to summarize", showarrow=False)
    return fig

# Explain missing selections and locations rather than guessing a map position.
def map_content(rows, selected_ids):
    row, message = selected_record(rows, selected_ids)
    if row is None:
        return html.P(message)
    position = coordinates(row)
    if position is None:
        return html.P("Location unavailable for this record.")
    return dl.Map(center=position, zoom=11, style={"height": "420px", "width": "100%"}, children=[
        dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'), dl.Marker(position=position, children=[
            dl.Tooltip(row.get("breed") or "Unknown breed"),
            dl.Popup(html.P(row.get("name") or "Unnamed animal"))])])
