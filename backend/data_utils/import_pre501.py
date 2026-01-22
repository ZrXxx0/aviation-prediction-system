# import csv
# import csv
# import os
# import sys
# from datetime import datetime
# import django
#
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(current_dir)
# sys.path.append(project_root)
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
#
# django.setup()
#
# from django.utils.timezone import now
#
# from predict.models import ForecastMonthly, ForecastQuarterly, ForecastYearly
#
#
# def import_forecast_data(csv_file_path, model_class, batch_updated_at=None):
#     """
#     导入CSV数据到指定的模型
#
#     Args:
#         csv_file_path: CSV文件路径
#         model_class: Django模型类（ForecastMonthly/ForecastQuarterly/ForecastYearly）
#         batch_updated_at: 批次更新时间，如果为None则使用当前时间
#     """
#     if batch_updated_at is None:
#         batch_updated_at = now()
#
#     # 统计信息
#     imported_count = 0
#     updated_count = 0
#     error_count = 0
#
#     try:
#         with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
#             # 尝试不同的分隔符
#             dialect = csv.Sniffer().sniff(csv_file.read(1024))
#             csv_file.seek(0)
#
#             reader = csv.DictReader(csv_file, dialect=dialect)
#
#             # 检查CSV列名并进行标准化
#             field_mapping = {}
#             for field in reader.fieldnames:
#                 field_lower = field.lower().strip()
#                 if 'yearmonth' in field_lower:
#                     field_mapping[field] = 'forecast_date'
#                 elif 'origin' in field_lower:
#                     field_mapping[field] = 'origin'
#                 elif 'destination' in field_lower:
#                     field_mapping[field] = 'destination'
#                 elif 'predicted_seats' in field_lower or 'seats' in field_lower:
#                     field_mapping[field] = 'seats'
#                 elif 'predicted_ask' in field_lower or 'ask' in field_lower:
#                     field_mapping[field] = 'ask'
#                 elif 'distance' in field_lower:
#                     # 跳过Distance字段，模型中不存在
#                     field_mapping[field] = None
#
#             for row_num, row in enumerate(reader, start=1):
#                 try:
#                     # 提取并转换数据
#                     data = {}
#                     for csv_field, model_field in field_mapping.items():
#                         if model_field is None:
#                             continue  # 跳过不需要的字段
#
#                         value = row[csv_field].strip()
#
#                         if model_field == 'forecast_date':
#                             # 处理日期格式
#                             try:
#                                 # 尝试解析日期
#                                 date_value = datetime.strptime(value, '%Y-%m-%d').date()
#                             except ValueError:
#                                 try:
#                                     # 如果日期格式不同，尝试其他格式
#                                     date_value = datetime.strptime(value, '%Y/%m/%d').date()
#                                 except ValueError:
#                                     print(f"行 {row_num}: 无法解析日期: {value}")
#                                     error_count += 1
#                                     continue
#                             data[model_field] = date_value
#                         elif model_field in ['seats', 'ask']:
#                             # 转换为浮点数
#                             try:
#                                 data[model_field] = float(value)
#                             except ValueError:
#                                 print(f"行 {row_num}: 无法转换数值: {value}")
#                                 error_count += 1
#                                 continue
#                         else:
#                             data[model_field] = value
#
#                     # 添加更新时间
#                     data['updated_at'] = batch_updated_at
#
#                     # 使用update_or_create避免重复，基于唯一约束
#                     obj, created = model_class.objects.update_or_create(
#                         origin=data['origin'],
#                         destination=data['destination'],
#                         forecast_date=data['forecast_date'],
#                         defaults=data
#                     )
#
#                     if created:
#                         imported_count += 1
#                     else:
#                         updated_count += 1
#
#                 except Exception as e:
#                     print(f"行 {row_num} 处理失败: {str(e)}")
#                     error_count += 1
#                     continue
#
#     except FileNotFoundError:
#         print(f"文件不存在: {csv_file_path}")
#         return False
#
#     print(f"导入完成: 新增 {imported_count} 条, 更新 {updated_count} 条, 错误 {error_count} 条")
#     return True
#
#
# def import_all_forecast_data(monthly_csv=None, quarterly_csv=None, yearly_csv=None):
#     """
#     导入所有频率的预测数据
#
#     Args:
#         monthly_csv: 月度数据CSV文件路径
#         quarterly_csv: 季度数据CSV文件路径
#         yearly_csv: 年度数据CSV文件路径
#     """
#     # 使用统一的批次更新时间
#     batch_updated_at = now()
#
#     print(f"开始导入数据，批次时间: {batch_updated_at}")
#     print("=" * 50)
#
#     # 导入月度数据
#     if monthly_csv and os.path.exists(monthly_csv):
#         print(f"导入月度数据: {monthly_csv}")
#         success = import_forecast_data(monthly_csv, ForecastMonthly, batch_updated_at)
#         if success:
#             print("月度数据导入成功!")
#         print("-" * 30)
#
#     # 导入季度数据
#     if quarterly_csv and os.path.exists(quarterly_csv):
#         print(f"导入季度数据: {quarterly_csv}")
#         success = import_forecast_data(quarterly_csv, ForecastQuarterly, batch_updated_at)
#         if success:
#             print("季度数据导入成功!")
#         print("-" * 30)
#
#     # 导入年度数据
#     if yearly_csv and os.path.exists(yearly_csv):
#         print(f"导入年度数据: {yearly_csv}")
#         success = import_forecast_data(yearly_csv, ForecastYearly, batch_updated_at)
#         if success:
#             print("年度数据导入成功!")
#         print("-" * 30)
#
#     print("=" * 50)
#     print("所有数据导入完成!")
#
#
# if __name__ == "__main__":
#     import_all_forecast_data(
#         monthly_csv="D:/Desktop/科研工作/科研工作ing/航空市场需求分析/AirlineSystem/backend/Predict_Datas/agg_data_0122/agg_monthly.csv",
#         quarterly_csv="D:/Desktop/科研工作/科研工作ing/航空市场需求分析/AirlineSystem/backend/Predict_Datas/agg_data_0122/agg_quarterly.csv",
#         yearly_csv="D:/Desktop/科研工作/科研工作ing/航空市场需求分析/AirlineSystem/backend/Predict_Datas/agg_data_0122/agg_yearly.csv"
#     )


import os
import sys
import pandas as pd
import django
from django.utils.timezone import now
from django.db import transaction

# --- Django 环境初始化 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()

from predict.models import ForecastMonthly, ForecastQuarterly, ForecastYearly


def import_forecast_data_with_summary(csv_file_path, model_class, batch_updated_at=None):
    if not os.path.exists(csv_file_path):
        print(f"文件不存在: {csv_file_path}")
        return False

    if batch_updated_at is None:
        batch_updated_at = now()

    print(f"正在处理: {os.path.basename(csv_file_path)}")

    try:
        # 1. Pandas 高速读取与格式化
        df = pd.read_csv(csv_file_path)

        column_map = {}
        for col in df.columns:
            c_low = col.lower().strip()
            if 'yearmonth' in c_low or 'date' in c_low:
                column_map[col] = 'forecast_date'
            elif 'origin' in c_low:
                column_map[col] = 'origin'
            elif 'destination' in c_low:
                column_map[col] = 'destination'
            elif 'seats' in c_low:
                column_map[col] = 'seats'
            elif 'ask' in c_low:
                column_map[col] = 'ask'

        df.rename(columns=column_map, inplace=True)

        # 数据转换
        df['forecast_date'] = pd.to_datetime(df['forecast_date']).dt.date
        df['seats'] = pd.to_numeric(df['seats'], errors='coerce').fillna(0)
        df['ask'] = pd.to_numeric(df['ask'], errors='coerce').fillna(0)
        df = df.dropna(subset=['forecast_date', 'origin', 'destination'])

        # 2. 计算 ALL-ALL 汇总
        print(f"生成汇总数据 (ALL-ALL)...")
        summary_df = df.groupby('forecast_date').agg({
            'seats': 'sum',
            'ask': 'sum'
        }).reset_index()
        summary_df['origin'] = 'ALL'
        summary_df['destination'] = 'ALL'

        # 3. 转换为 Django 对象
        # 合并原始数据和汇总数据
        final_records = df.to_dict('records') + summary_df.to_dict('records')
        objs = [model_class(**{**row, 'updated_at': batch_updated_at}) for row in final_records]

        # 4. 事务写入
        with transaction.atomic():
            print(f"清空旧数据并写入 {len(objs)} 条新记录...")
            model_class.objects.all().delete()

            batch_size = 5000
            for i in range(0, len(objs), batch_size):
                model_class.objects.bulk_create(objs[i: i + batch_size])

        print(f"[{os.path.basename(csv_file_path)}] 导入成功！")
        return True

    except Exception as e:
        print(f"导入过程中出错: {str(e)}")
        return False


def run_import():
    # 关闭 DEBUG 以节省内存
    from django.conf import settings
    settings.DEBUG = False

    batch_time = now()
    base_path = "D:/Desktop/科研工作/科研工作ing/航空市场需求分析/AirlineSystem/backend/Predict_Datas/agg_data_0122/"

    config = [
        ("agg_monthly.csv", ForecastMonthly),
        ("agg_quarterly.csv", ForecastQuarterly),
        ("agg_yearly.csv", ForecastYearly),
    ]

    for file_name, model in config:
        full_path = os.path.join(base_path, file_name)
        import_forecast_data_with_summary(full_path, model, batch_time)


if __name__ == "__main__":
    run_import()