"""执行数据库迁移脚本"""
import sqlite3
import os

# 数据库路径
db_path = os.path.join(os.path.dirname(__file__), 'data', 'ai_stats.db')
sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'blame_stats_schema_sqlite.sql')

# 读取 SQL 脚本
with open(sql_path, 'r', encoding='utf-8') as f:
    sql_script = f.read()

# 连接数据库并执行
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.executescript(sql_script)
    conn.commit()
    print("数据库迁移成功！")

    # 验证新表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('ssh_keys', 'stats_blame_repo', 'stats_blame_file')")
    tables = cursor.fetchall()
    print(f"新创建的表: {[t[0] for t in tables]}")

except Exception as e:
    conn.rollback()
    print(f"数据库迁移失败: {e}")
finally:
    conn.close()
