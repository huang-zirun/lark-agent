import sqlite3

conn = sqlite3.connect('data/devflow.db')
cursor = conn.cursor()

cursor.execute("""
    UPDATE checkpoint_record
    SET status = 'APPROVED',
        decision_by = 'tester',
        decision_at = CURRENT_TIMESTAMP,
        reason = '设计方案合理，同意继续'
    WHERE id = 'b0494f36b34842bdaeb93851dd9053f6'
""")

conn.commit()
print(f"Updated {cursor.rowcount} row(s)")

# 验证更新
cursor.execute("SELECT status, decision_by, decision_at FROM checkpoint_record WHERE id = 'b0494f36b34842bdaeb93851dd9053f6'")
row = cursor.fetchone()
print(f"Status: {row[0]}")
print(f"Decision By: {row[1]}")
print(f"Decision At: {row[2]}")

conn.close()
