import sqlite3
import pandas as pd

con = sqlite3.connect('data/phase_diagrams.db')

q = """
SELECT experiment_id, 
       experiment_name, 
       surfactant_name, 
       polymer_name, 
       water_hardness_gpg, 
       COUNT(*) as n_records, 
       COUNT(DISTINCT timepoint_minutes) as n_timepoints
FROM measurements 
WHERE lower(surfactant_name) LIKE '%rham%'
GROUP BY experiment_id, experiment_name, surfactant_name, polymer_name, water_hardness_gpg
ORDER BY polymer_name, water_hardness_gpg
"""

df = pd.read_sql_query(q, con)
con.close()

print("\n=== RHAMNOLIPID EXPERIMENTS ===\n")
print(df.to_string(index=False))
print(f"\nTotal: {len(df)} experiment/polymer/hardness combinations")
