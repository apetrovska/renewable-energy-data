import os

from entsoe import EntsoePandasClient
import pandas as pd

# Initialize ENTSO-E API client with authentication key
API_KEY = os.environ.get("ENTSOE_API_KEY")
    if not API_KEY:
        raise Exception("Please set the environment variable `ENTSOE_API_KEY`")

client = EntsoePandasClient(api_key=API_KEY)

# Define query time window for testing
start = pd.Timestamp("2023-01-01", tz="UTC")
end   = pd.Timestamp("2023-02-01", tz="UTC")

# Query generation data by type for Germany and inspect structure
gen = client.query_generation("DE", start=start, end=end)
print("── Generation ──")
print(type(gen))
print(gen.head())
print(gen.columns.tolist())

# Query load data for Germany and inspect structure
load = client.query_load("DE", start=start, end=end)
print("\n── Load ──")
print(type(load))
print(load.head())
