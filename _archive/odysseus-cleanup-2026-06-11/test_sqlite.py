import sqlite3
conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE foo (a)')
conn.execute('BEGIN IMMEDIATE')
conn.execute('UPDATE foo SET a=1')
print("No error!")
