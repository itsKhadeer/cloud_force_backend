import sqlite3
import csv
import logging
import random
import pandas as pd
from tqdm import tqdm
import math  # For calculating the number of CSV files required

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Connect to the SQLite databases
conn_snippets = sqlite3.connect('/home/mukundhk/tf/CVEfixes/snippets-dev.db')
cursor_snippets = conn_snippets.cursor()

# Fetch snippets
logging.info("Fetching snippets from the database...")
cursor_snippets.execute("""
WITH language_limits AS (
  SELECT 'Bash' AS language, 9 AS snippet_limit
  UNION ALL SELECT 'C', 9916
  UNION ALL SELECT 'C++', 5256
  UNION ALL SELECT 'Go', 6519
  UNION ALL SELECT 'Java', 6038
  UNION ALL SELECT 'JavaScript', 7208
  UNION ALL SELECT 'Jupyter Notebook', 198
  UNION ALL SELECT 'PowerShell', 31
  UNION ALL SELECT 'Python', 3157
  UNION ALL SELECT 'Ruby', 879
  UNION ALL SELECT 'Rust', 479
  UNION ALL SELECT 'Shell', 308
),
numbered_snippets AS (
  SELECT snippet, language, 
         ROW_NUMBER() OVER (PARTITION BY language ORDER BY RANDOM()) as row_num
  FROM snippets
)
SELECT n.snippet
FROM numbered_snippets n
JOIN language_limits l ON n.language = l.language
WHERE n.row_num <= l.snippet_limit
ORDER BY n.language, RANDOM();""")
snippets = cursor_snippets.fetchall()
logging.info(f"Fetched {len(snippets)} snippets from the database")

# Read existing CSV data
logging.info("Reading existing CSV data...")
try:
    df = pd.read_csv('output.csv')
    logging.info(f"Loaded {len(df)} existing rows from output.csv")
except FileNotFoundError:
    df = pd.DataFrame(columns=['Instruction', 'Input', 'Output'])
    logging.info("No existing output.csv found. Starting with an empty DataFrame.")

# Prepare new data
new_data = []
instruction = "Tell me if there is a vulnerability in this code."
output = "No vulnerabilities found."

logging.info("Processing snippets...")
for snippet in tqdm(snippets):
    new_data.append({
        'Instruction': instruction,
        'Input': snippet[0],
        'Output': output
    })

# Add new data to DataFrame
df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

# Shuffle the data
logging.info("Shuffling the data...")
df = df.sample(frac=1).reset_index(drop=True)

output_file = f'output_shuffled.csv'
df.to_csv(output_file, index=False)

logging.info(f"Total rows in the final CSV: {len(df)}")

# Close the database connection
conn_snippets.close()

logging.info("Process completed. Data has been obtained")
