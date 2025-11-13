import os
import django
import pandas as pd

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()

from show.models import RouteMonthlyStat

# 导入未导入的数据

def safe_float(val):
    return float(val) if pd.notna(val) else None

def safe_int(val):
    return int(val) if pd.notna(val) else None

def import_bulk(csv_path, batch_size=1000):
    df = pd.read_csv(csv_path)

    df.drop_duplicates(subset=['YearMonth', 'Origin', 'Destination'], inplace=True)
    df = df[pd.notna(df['Origin']) & pd.notna(df['Destination']) & pd.notna(df['YearMonth'])]

    # 查询已有主键组合用于跳过重复导入
    existing_keys = set(RouteMonthlyStat.objects.values_list(
        'origin_code', 'destination_code', 'year', 'month'
    ))

    to_create = []
    failed_rows = []
    success_count = 0

    total = len(df)
    print(f"📦 正在批量导入，共 {total} 条记录...")

    for i, row in df.iterrows():
        try:
            year_month = pd.to_datetime(row['YearMonth'])
            year = year_month.year
            month = year_month.month
            key = (row['Origin'], row['Destination'], year, month)

            if key in existing_keys:
                continue

            obj = RouteMonthlyStat(
                origin_code=row['Origin'].strip(),
                destination_code=row['Destination'].strip(),
                year=year,
                month=month,
                passenger_volume=safe_float(row.get('Con Total Est. Pax')),
                Route_Total_Seats=safe_float(row.get('Route_Total_Seats')),
                Route_Total_Flights=safe_int(row.get('Route_Total_Flights')),
            )
            to_create.append(obj)
            success_count += 1

            # 到达批次大小就入库
            if len(to_create) >= batch_size:
                RouteMonthlyStat.objects.bulk_create(to_create)
                to_create.clear()
                print(f"🚀 批次入库成功，总导入：{success_count} 条")

        except Exception as e:
            failed_rows.append(row)
            print(f"❌ 第{i+1}条导入失败：{row.get('Origin')} → {row.get('Destination')} - {e}")

    # 剩余未提交的入库
    if to_create:
        RouteMonthlyStat.objects.bulk_create(to_create)
        print(f"✅ 最后批次导入成功，共导入 {success_count} 条")

    # 失败数据保存
    if failed_rows:
        pd.DataFrame(failed_rows).to_csv("failed_bulk_rows.csv", index=False)
        print("⚠️ 部分数据导入失败，已保存到 failed_bulk_rows.csv")

    print(f"🎉 批量导入完成，总成功：{success_count} 条，失败：{len(failed_rows)} 条")

if __name__ == "__main__":
    import_bulk("./final_data_0729.csv", batch_size=1000)
