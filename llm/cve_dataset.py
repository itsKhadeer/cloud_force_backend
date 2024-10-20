import sqlite3
import csv
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

conn = sqlite3.connect('CVEfixes/CVEfixes.db')
cursor = conn.cursor()
 
# Create indexes
indexes = [
    "CREATE INDEX IF NOT EXISTS idx_file_change_hash ON file_change(hash)",
    "CREATE INDEX IF NOT EXISTS idx_commits_hash ON commits(hash)",
    "CREATE INDEX IF NOT EXISTS idx_fixes_hash ON fixes(hash)",
    "CREATE INDEX IF NOT EXISTS idx_fixes_cve_id ON fixes(cve_id)",
    "CREATE INDEX IF NOT EXISTS idx_cve_id ON cve(cve_id)",
    "CREATE INDEX IF NOT EXISTS idx_cwe_classification_cve_id ON cwe_classification(cve_id)",
    "CREATE INDEX IF NOT EXISTS idx_cwe_classification_cwe_id ON cwe_classification(cwe_id)",
    "CREATE INDEX IF NOT EXISTS idx_cwe_cwe_id ON cwe(cwe_id)"
]

logging.info("Creating indexes...")
for index in indexes:
    cursor.execute(index)
conn.commit()
logging.info("Indexes created successfully")

query = """
SELECT 
    fc.code_before,
    fc.code_after,
    cve.cve_id,
    cve.description AS cve_description,
    cve.severity,
    cwe.cwe_id,
    cwe.cwe_name,
    cwe.description AS cwe_description,
    cwe.extended_description,
    cwe.url
FROM 
    file_change fc
JOIN 
    commits c ON fc.hash = c.hash
JOIN 
    fixes f ON c.hash = f.hash
JOIN 
    cve ON f.cve_id = cve.cve_id
LEFT JOIN 
    cwe_classification cc ON cve.cve_id = cc.cve_id
LEFT JOIN 
    cwe ON cc.cwe_id = cwe.cwe_id
"""

logging.info("Executing SQL query...")
start_time = time.time()
cursor.execute(query)

with open('output.csv', 'w', newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(['Instruction', 'Input', 'Output'])
    
    logging.info("Started writing to CSV file")
    i = 0
    batch_size = 1000
    while True:
        results = cursor.fetchmany(batch_size)
        if not results:
            break
        
        for row in results:
            code_before, code_after, cve_id, cve_description, severity, cwe_id, cwe_name, cwe_description, extended_description, url = row
            
            instruction = "Tell me if there is a vulnerability in this code."
            input_text = code_before
            
            if cve_id == '0' or cve_id is None:
                output = "No vulnerabilities or safe code."
            else:
                output = f"Vulnerability is there. CVE ID: {cve_id}, Description: {cve_description}, Severity: {severity}, "
                output += f"CWE ID: {cwe_id}, CWE Name: {cwe_name}, CWE Description: {cwe_description}, "
                output += f"Extended Description: {extended_description}, URL: {url}. "
                output += f"Code after fix: {code_after}"
            
            csv_writer.writerow([instruction, input_text, output])
            
            i += 1
            if i % 1000 == 0:
                logging.info(f"Processed {i} rows")
                csvfile.flush()  # Ensure data is written to disk

    logging.info(f"Finished writing all {i} rows to CSV")

end_time = time.time()
logging.info(f"Total execution time: {end_time - start_time:.2f} seconds")

conn.close()
logging.info("Data has been exported to output.csv")