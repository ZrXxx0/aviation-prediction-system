import os
import django
import pandas as pd

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()

from show.models import RouteMonthlyStat

# 将csv文件导入数据库
# import_routes效率慢，建议采用import_routes2
def import_csv_to_db(csv_path):
    df = pd.read_csv(csv_path)

    # 去除列名两端空格（避免因为拼错或含空格而找不到字段）
    df.columns = df.columns.str.strip()

    for _, row in df.iterrows():
        # 处理时间
        try:
            year_month = pd.to_datetime(row['YearMonth'], errors='coerce')
            if pd.isna(year_month):
                raise ValueError("无法解析日期")
            year = year_month.year
            month = year_month.month
        except Exception as e:
            print(f"❌ 时间解析失败：{row.get('YearMonth')} -- {e}")
            continue

        try:
            passenger_volume = float(row.get('Con Total Est. Pax', 0) or 0)
            total_seats = float(row.get('Route_Total_Seats', 0) or 0)
            total_flights = int(row.get('Route_Total_Flights', 0) or 0)

            RouteMonthlyStat.objects.update_or_create(
                origin_code=row.get('Origin', '').strip(),
                destination_code=row.get('Destination', '').strip(),
                year=year,
                month=month,
                defaults={
                    'passenger_volume': passenger_volume,
                    'Route_Total_Seats': total_seats,
                    'Route_Total_Flights': total_flights,
                }
            )
            print(f"✅ 成功导入：{row['Origin']} → {row['Destination']} {year}-{month}")
        except Exception as e:
            print(f"❌ 导入失败：{row.get('Origin')} → {row.get('Destination')} {year}-{month} -- {e}")

if __name__ == "__main__":
    import_csv_to_db("D:/desk/Airlinepredict/aviation-prediction/final_data_0622.csv")
