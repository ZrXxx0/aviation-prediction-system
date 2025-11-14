"""
修复迁移依赖问题的脚本
在数据库中手动插入accounts.0001_initial的迁移记录
"""
import os
import django
from django.db import connection
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()

def fix_migration():
    cursor = connection.cursor()
    
    # 检查accounts.0001_initial是否已经记录
    cursor.execute(
        "SELECT * FROM django_migrations WHERE app = 'accounts' AND name = '0001_initial'"
    )
    exists = cursor.fetchone()
    
    if exists:
        print("✅ accounts.0001_initial 迁移记录已存在")
        return
    
    # 插入迁移记录
    now = timezone.now()
    cursor.execute(
        """
        INSERT INTO django_migrations (app, name, applied)
        VALUES (%s, %s, %s)
        """,
        ['accounts', '0001_initial', now]
    )
    
    connection.commit()
    print("✅ 已成功插入 accounts.0001_initial 迁移记录")
    print("   现在可以运行: python manage.py migrate")

if __name__ == '__main__':
    try:
        fix_migration()
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

