import os
import django
import pandas as pd
from django.db import transaction

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()

from show.models import RouteMonthlyStat

def safe_float(val):
    try:
        return float(val) if pd.notna(val) else None
    except:
        return None

def safe_int(val):
    try:
        return int(val) if pd.notna(val) else None
    except:
        return None

def import_csv_in_chunks(csv_path, chunk_size=5000):
    failed_rows = []
    total_created = 0

    for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
        objs_to_create = []

        for _, row in chunk.iterrows():
            try:
                year_month = pd.to_datetime(row['YearMonth'])
                year = year_month.year
                month = year_month.month
            except Exception as e:
                print(f"❌ 时间解析失败：{row.get('YearMonth')} -- {e}")
                failed_rows.append(row)
                continue

            obj = RouteMonthlyStat(
                origin_code=str(row.get('Origin', '')).strip(),
                destination_code=str(row.get('Destination', '')).strip(),
                year=year,
                month=month,
                passenger_volume=safe_float(row.get('Con Total Est. Pax')),
                Route_Total_Seats=safe_float(row.get('Route_Total_Seats')),
                Route_Total_Flights=safe_int(row.get('Route_Total_Flights')),
            )
            objs_to_create.append(obj)

        try:
            with transaction.atomic():
                RouteMonthlyStat.objects.bulk_create(objs_to_create, batch_size=1000, ignore_conflicts=True)
                total_created += len(objs_to_create)
                print(f"✅ 成功导入 {len(objs_to_create)} 条")
        except Exception as e:
            print(f"❌ 批量导入失败：{e}")
            failed_rows.extend(chunk.to_dict(orient='records'))

    if failed_rows:
        pd.DataFrame(failed_rows).to_csv("failed_imports.csv", index=False)
        print("⚠️ 有部分数据导入失败，已保存到 failed_imports.csv")

    print(f"✅ 总共导入成功记录数：{total_created}")

if __name__ == "__main__":
    import_csv_in_chunks("D:/desk/Airlinepredict/aviation-prediction/final_data_0622.csv")
