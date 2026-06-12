import sqlite3
conn = sqlite3.connect('test.db')
conn.execute('CREATE TABLE IF NOT EXISTS foo (a)')
conn.execute('BEGIN IMMEDIATE')
conn.execute('UPDATE foo SET a=1')
conn.commit()
conn.close()

conn = sqlite3.connect('test.db')
print("Active transaction?", conn.in_transaction)
