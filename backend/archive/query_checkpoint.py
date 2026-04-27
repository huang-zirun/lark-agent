import sqlite3

conn = sqlite3.connect('data/devflow.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 获取 checkpoint 信息
cursor.execute("""
    SELECT id, run_id, stage_key, checkpoint_type, status, decision_by, decision_at, reason
    FROM checkpoint_record
    WHERE id = 'b0494f36b34842bdaeb93851dd9053f6'
""")
row = cursor.fetchone()
if row:
    print(f"Checkpoint: {row['id']}")
    print(f"Run ID: {row['run_id']}")
    print(f"Stage Key: {row['stage_key']}")
    print(f"Type: {row['checkpoint_type']}")
    print(f"Status: {row['status']}")
    print(f"Decision By: {row['decision_by']}")
    print(f"Decision At: {row['decision_at']}")
    print(f"Reason: {row['reason']}")
else:
    print("Checkpoint not found")

conn.close()
