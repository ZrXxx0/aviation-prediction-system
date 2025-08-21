import json
import os
import django
import sys

# ========= Django 初始化 =========
PROJECT_ROOT = r"D:\desk\project\backend"  # 项目根目录（manage.py 所在）
sys.path.append(PROJECT_ROOT)

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AirlinePredictSystem.settings")  # 改成你的 settings 模块
django.setup()

from show.models import AirportInfo

# JSON 文件路径
JSON_PATH = "./iata_city_airport_mapping.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    airport_data = json.load(f)

count_new, count_updated = 0, 0
for code, info in airport_data.items():
    obj, created = AirportInfo.objects.update_or_create(
        code=code,
        defaults={
            "city": info.get("city", ""),
            "airport": info.get("airport", ""),
            "province": info.get("province", ""),
        }
    )
    if created:
        count_new += 1
    else:
        count_updated += 1

print(f"✅ 导入完成，新建 {count_new} 条，更新 {count_updated} 条")
