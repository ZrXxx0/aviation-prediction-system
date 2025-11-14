"""
临时脚本：检查数据库中是否已存在user和role表
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# 检查表是否存在
cursor.execute("SHOW TABLES LIKE 'user'")
user_exists = cursor.fetchone() is not None

cursor.execute("SHOW TABLES LIKE 'role'")
role_exists = cursor.fetchone() is not None

print(f"user表存在: {user_exists}")
print(f"role表存在: {role_exists}")

if user_exists or role_exists:
    print("\n⚠️  检测到表已存在，需要使用 --fake 选项")
else:
    print("\n✅ 表不存在，可以正常迁移")

