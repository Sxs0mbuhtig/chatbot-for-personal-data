# purge_bad_rows.py
import sqlite3

conn = sqlite3.connect("chuon_nath_fts.db")
cursor = conn.cursor()

# លុបចោលរាល់ Data ដែល definition មានតែសញ្ញាខណ្ឌ '។' ឬ Empty String
cursor.execute("""
    DELETE FROM dictionary 
    WHERE TRIM(REPLACE(REPLACE(definition, '។', ''), ' ', '')) = '';
""")

conn.commit()
print(f"Purged invalid rows. Total rows deleted: {cursor.rowcount}")
conn.close()
