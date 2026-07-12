import sqlite3

conn = sqlite3.connect(r"instance\freight_crm.db")
cursor = conn.cursor()

try:
    cursor.execute("""
        ALTER TABLE support_tickets
        ADD COLUMN admin_reply TEXT
    """)
    conn.commit()
    print("✅ admin_reply column added successfully.")
except Exception as e:
    print("⚠️", e)

conn.close()