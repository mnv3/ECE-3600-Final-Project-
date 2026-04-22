# ECE-3600-Final-Project-

Data Center Visualizer

visualize_datacenters.py is a small Python script that reads a Data_Centers_Database as a csv file and produces two charts:
-a geographic map of every facility in terms of latitude and longitude
-a scatter plot of power capacity versus physical footprint.

## Usage/Commands 

```
python visualize_datacenters.py <data_file> [output_prefix]
```

- `<data_file>` — a CSV file. The script auto-detects the delimiter.
- `[output_prefix]` — optional. Defaults to `datacenters`.

Example:

```
python visualize_datacenters.py Data_Centers_Database.csv
```

This writes two files into the current directory:

- `datacenters_map.png`
- `datacenters_power_density.png`

## Expected input columns

The script looks for these columns in the header row (case-sensitive). Missing
optional columns are tolerated; missing `lat` will stop execution with a clear
error listing the columns that were actually found.

| Column                | Required | Notes                                             |
|-----------------------|----------|---------------------------------------------------|
| `lat`                 | yes      | Decimal degrees                                   |
| `long`                | yes      | Decimal degrees                                   |
| `status`              | no       | e.g. Operating, Proposed, Cancelled               |
| `facility_size_sqft`  | no       | Numeric; commas are stripped                      |
| `mw`                  | no       | Accepts single values, ranges (`150-300`), and `>3,000` — ranges use the midpoint |
| `state`               | no       | Used only if you later re-enable the state panel  |
| `community_pushback`  | no       | `Yes` counts as pushback                          |

## What the outputs show

**`datacenters_map.png`** — Every facility plotted at its lat/long across the
continental US. The marker color encodes project status. The marker area is scaled proportionally to the
square root of `facility_size_sqft`, so a 10 million sqft campus reads as a bigger dot than a 100,000 sqft site without dominating the view entirely. Rows without coordinates or with coordinates outside the continental US bounding box are dropped.

**`datacenters_power_density.png`** — Log-log scatterplot of MW capacity against facility size, colored by status. A dashed reference line at roughly 250 W/sqft (1 MW per 4,000 sqft) marks the typical power density of a modern AI-oriented datacenter. Points well above the line are unusually power-dense, points well below are traditional lower-density colocation facilities.
