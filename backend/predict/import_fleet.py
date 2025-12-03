import os
import django
from django.db import connection, transaction

# 1. 告诉 Django 用哪个 settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AirlinePredictSystem.settings")
django.setup()

# 这里只保留数据，不再建表

# 2. 这里写入每种机型的参数值
FLEET_ROWS = [
    # fleet_type,        avg_seats, avg_speed, avg_uti
    ("大型涡扇支线客机", 76,   586, 8.8),
    ("小型窄体客机",     117,  586, 8.5),
    ("中型窄体客机",    115,  604, 8.7),
    ("大型窄体客机",     180,  598, 8.3),
    ("小型宽体客机",     280,  605, 4.4),
    ("中型宽体客机",     334,  683, 2.5),
    ("大型宽体客机",     412,  589, 2.6),
]


def main():
    with transaction.atomic():
        with connection.cursor() as cursor:
            # 不再建表，假设 predict_fleetparam 已经存在

            # 1. 清空原有数据（如果不想清空可以注释掉）
            cursor.execute("DELETE FROM predict_fleetparam")

            # 2. 插入数据
            insert_sql = """
                INSERT INTO predict_fleetparam (fleet_type, avg_seats, avg_speed, avg_uti)
                VALUES (%s, %s, %s, %s)
            """
            cursor.executemany(insert_sql, FLEET_ROWS)

    print("表 predict_fleetparam 已更新，插入行数：", len(FLEET_ROWS))


if __name__ == "__main__":
    main()
