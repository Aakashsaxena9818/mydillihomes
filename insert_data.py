import sqlite3

# Connect to the database
conn = sqlite3.connect('property.db')
cursor = conn.cursor()

# Drop existing table if it exists
cursor.execute('DROP TABLE IF EXISTS properties')

# Create table with corrected field names
cursor.execute('''
    CREATE TABLE properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area INTEGER,
        area_name TEXT,
        bhk INTEGER,
        bathroom INTEGER,
        furnishing TEXT,
        parking INTEGER,
        status TEXT,
        "transaction" TEXT,
        type TEXT,
        per_sqft INTEGER,
        price INTEGER,
        image_filenames TEXT
    )
''')

# Commit and close
conn.commit()
conn.close()

print("Database and table created successfully!")
