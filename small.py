import sqlite3

# Connect to your database
conn = sqlite3.connect("habits.db")
cursor = conn.cursor()

# Add streak column with default value 0
cursor.execute("ALTER TABLE habits ADD COLUMN streak INTEGER DEFAULT 0")

conn.commit()
conn.close()
print("✅ streak column added successfully")
