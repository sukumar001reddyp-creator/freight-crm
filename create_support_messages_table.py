import sqlite3

conn = sqlite3.connect(r"instance\freight_crm.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ticket_id)
        REFERENCES support_tickets(id)
        ON DELETE CASCADE
)
""")

conn.commit()

print("✅ support_messages table created.")

conn.close()