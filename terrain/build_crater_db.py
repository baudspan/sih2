import pandas as pd
import sqlite3

# Step A: Load raw CSV
df = pd.read_csv("data/raw/lunar_crater_database_robbins_2018.csv")
print(df.columns.tolist())
print(df.shape)

# Step B: Filter to South Pole region (adjust column names after checking print output above)
south_pole = df[df["LAT_CIRC_IMG"] <= -80]

# Step C: Keep top 100 by diameter
top_100 = south_pole.sort_values("DIAM_CIRC_IMG", ascending=False).head(100)

# Step D: Write to SQLite
conn = sqlite3.connect("data/crater_db.sqlite")
top_100.to_sql("craters", conn, if_exists="replace", index=False)
conn.close()

print("Done. Rows written:", len(top_100))