import os
import pandas as pd
import numpy as np
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

# 仅引入预测结果表，不引入模型元信息表
from predict.models import (
    FlightMarketRecord,
    ForecastMonthly,
    ForecastQuarterly,
    ForecastYearly
)

# 引入算法模块
from predict.predictive_algorithm.train_models_split_topn import process_all_routes, CONFIG as TRAIN_CONFIG, base_dir
from predict.predictive_algorithm.field_mapping import get_field_mapping, get_special_fields


class Command(BaseCommand):
    help = '自动更新航线排名，生成预测，并聚合季度/年度数据入库（仅更新预测结果，不记录模型信息）'

    current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/...
    base_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'Predict_Datas')  # backend/Predict_Datas

    def add_arguments(self, parser):
        parser.add_argument('--top_n', type=int, default=500, help='筛选前N条航线')
        parser.add_argument('--skip_train', action='store_true', help='跳过训练阶段，直接使用现有的csv进行入库')

        parser.add_argument('--time_granularity', type=str, default=None,
                            help="覆盖配置: 时间粒度 (monthly/quarterly/yearly)")
        parser.add_argument('--include_other', action='store_true', help="覆盖配置: 是否包含剩余航线聚合")
        parser.add_argument('--no_include_other', action='store_false', dest='include_other',
                            help="覆盖配置: 不包含剩余航线")
        parser.set_defaults(include_other=None)  # 默认值为None，表示不覆盖

        parser.add_argument('--model_type', type=str, default=None, help="覆盖配置: 模型类型 (lgb/xgb)")
        parser.add_argument('--future_periods', type=int, default=None, help="覆盖配置: 预测时长")
        parser.add_argument('--max_workers', type=int, default=None, help="覆盖配置: 并行进程数")

    def handle(self, *args, **options):
        # 0. 获取命令行参数
        top_n = options['top_n']
        skip_train = options['skip_train']

        self.stdout.write(self.style.SUCCESS(f"=== 开始全流程更新任务 (Top {top_n}) ==="))

        # === 核心修复：动态更新 TRAIN_CONFIG ===
        # 必须显式修改导入的字典，才能让 process_all_routes 生效
        TRAIN_CONFIG['top_n'] = top_n
        TRAIN_CONFIG['filter_mode'] = 'top_n'  # 强制确保模式匹配

        # 处理其他可选参数的覆盖
        if options['time_granularity']:
            TRAIN_CONFIG['time_granularity'] = options['time_granularity']
        if options['include_other'] is not None:
            TRAIN_CONFIG['include_other'] = options['include_other']
        if options['model_type']:
            TRAIN_CONFIG['model_type'] = options['model_type']
        if options['future_periods']:
            TRAIN_CONFIG['future_periods'] = options['future_periods']
        if options['max_workers']:
            TRAIN_CONFIG['max_workers'] = options['max_workers']

        self.stdout.write(f"当前运行配置: {TRAIN_CONFIG}")

        # 1. 准备数据 (修复原脚本 domestic_data 未定义的问题)
        self.stdout.write("1. 正在从数据库加载全量数据...")
        domestic_data = self.load_and_clean_data()

        if domestic_data is None or domestic_data.empty:
            self.stdout.write(self.style.ERROR("数据库中无数据，任务终止"))
            return

        # 2. 计算排名
        self.stdout.write("2. 计算最新的航线排名...")
        ranking_df, top_routes_list = self.generate_ranking_from_df(domestic_data, top_n)

        # 保存排名文件 (train_models_split_topn.py 依赖此文件进行筛选)

        ranking_path = os.path.join(base_dir,'route_ranking.csv')
        ranking_df.to_csv(ranking_path, index=False)
        self.stdout.write(f"排名已保存至: {ranking_path}")

        # 3. 执行预测

        if not skip_train:
            self.stdout.write("3. 开始执行预测模型 (此过程耗时较长)...")
            # 传入已经修改过的 TRAIN_CONFIG
            process_all_routes(domestic_data, TRAIN_CONFIG)
        else:
            self.stdout.write("跳过训练，直接处理现有结果...")

        # 4. 结果入库
        # 根据配置定位结果文件夹: ./results_split_1201/{granularity}_{model_type}
        granularity = TRAIN_CONFIG.get('time_granularity', 'monthly')
        model_type = TRAIN_CONFIG.get('model_type', 'lgb')
        algo_output_base = base_dir
        results_dir = os.path.join(algo_output_base, f"{granularity}_{model_type}")

        if not os.path.exists(results_dir):
            self.stdout.write(self.style.WARNING(f"找不到预测结果目录: {results_dir}，请检查训练脚本是否执行成功"))
            return

        self.stdout.write(f"4. 开始从 {results_dir} 聚合数据并写入数据库...")
        self.process_and_ingest(results_dir, top_routes_list)

        self.stdout.write(self.style.SUCCESS("=== 全流程更新完成 ==="))

    def load_and_clean_data(self):
        """
        加载全量 FlightMarketRecord 并映射字段名
        (已融合更稳健的数据类型转换逻辑)
        """
        try:
            self.stdout.write("正在读取数据库全量数据...")
            # 使用 values() 稍微提高一点性能
            qs = FlightMarketRecord.objects.all().values()
            df = pd.DataFrame(list(qs))

            if df.empty:
                return None

            # 获取字段映射
            try:
                field_to_csv_mapping = get_field_mapping()
            except ImportError as e:
                self.stdout.write(self.style.ERROR(f"数据映射失败: {e}"))
                return None

            # 重命名列
            df = df.rename(columns=field_to_csv_mapping)

            # --- 核心修改：借鉴 load_data_from_database 的通用转换逻辑 ---

            # 定义不需要转换的非数值列 (白名单)
            # 注意：International Flight 如果是布尔值，to_numeric 可能会把它变成 0/1，这通常是可以接受的
            # 如果你有特定的 Region 列或者其他字符串列，也加到这里
            exclude_cols = [
                'YearMonth', 'Origin', 'Destination', 'Equipment',
                'International Flight', 'Region', 'dt', 'year'
            ]

            converted_count = 0
            for col in df.columns:
                if col not in exclude_cols:
                    # 1. 强制转为数值，无法解析的变 NaN (errors='coerce')
                    # 2. 将 NaN 填充为 0 (fillna(0))，防止模型报错
                    # 3. 如果原本是 Decimal 类型，这里也会被转为 float
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    converted_count += 1

            self.stdout.write(f"已加载 {len(df)} 条记录，并清洗了 {converted_count} 个数值列")
            return df

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"加载数据失败: {e}"))
            import traceback
            traceback.print_exc()
            return None

    def generate_ranking_from_df(self, df, top_n):
        """
        基于 DataFrame 生成排名
        """
        df['dt'] = pd.to_datetime(df['YearMonth'])
        df['year'] = df['dt'].dt.year

        # 简化逻辑：取每条航线最大年份的前一年作为基准
        route_max_dates = df.groupby(['Origin', 'Destination'])['dt'].max().reset_index()
        route_max_dates['target_year'] = route_max_dates['dt'].dt.year - 1

        merged = pd.merge(df, route_max_dates, on=['Origin', 'Destination'])
        target_data = merged[merged['year'] == merged['target_year']]

        # 聚合
        stats = target_data.groupby(['Origin', 'Destination']).agg({
            'Route_Total_Seats': 'sum',
            'Distance (KM)': 'mean'
        }).reset_index()

        stats['Calculated_Value'] = stats['Route_Total_Seats'] * stats['Distance (KM)']
        stats = stats.sort_values(by='Calculated_Value', ascending=False)

        top_routes = stats.head(top_n)[['Origin', 'Destination']].values.tolist()
        return stats, top_routes

    def process_and_ingest(self, base_dir, top_routes):
        """
        遍历文件夹，读取预测csv，入库
        """
        # Other 航线路径
        other_pred_path = os.path.join(base_dir, 'OTHER_OTHER', 'future_predictions.csv')
        other_hist_path = os.path.join(base_dir, 'OTHER_OTHER', 'history_ask.csv')

        # 1. 处理 Top N 航线
        for origin, dest in top_routes:
            folder_name = f"{origin}_{dest}"
            pred_file = os.path.join(base_dir, folder_name, 'future_predictions.csv')

            if os.path.exists(pred_file):
                self.ingest_single_route(origin, dest, pred_file)
            else:
                # 仅警告，不中断
                pass

        # 2. 处理 Other 航线 (如果配置中开启了 include_other)
        if os.path.exists(other_pred_path):
            self.stdout.write("正在处理 Other-Other 聚合航线...")
            self.ingest_single_route(
                'OTHER', 'OTHER',
                other_pred_path,
                is_other=True,
                history_csv_path=other_hist_path
            )

    def ingest_single_route(self, origin, dest, csv_path, is_other=False, history_csv_path=None):
        """
        核心入库逻辑：
        1. 读取 future_predictions.csv -> 存入 ForecastMonthly
        2. 读取历史数据 (DB 或 csv) -> 拼接 -> Resample -> 存入 ForecastQuarterly/Yearly
        """
        try:
            # --- A. 读取预测数据 ---
            pred_df = pd.read_csv(csv_path)
            pred_df['YearMonth'] = pd.to_datetime(pred_df['YearMonth'])

            # 预测起始时间
            start_date = pred_df['YearMonth'].min()

            # --- B. 更新月度预测表 (ForecastMonthly) ---
            # 直接覆盖该航线 >= start_date 的数据
            monthly_objects = []
            for _, row in pred_df.iterrows():
                # 兼容：有些文件可能有 Predicted_ASK，有些可能需要算
                seats = row.get('Predicted_Seats', 0)
                dist = row.get('Distance', 0)
                ask = row.get('Predicted_ASK', seats * dist)

                monthly_objects.append(ForecastMonthly(
                    origin=origin,
                    destination=dest,
                    forecast_date=row['YearMonth'],
                    seats=seats,
                    ask=ask
                ))

            with transaction.atomic():
                ForecastMonthly.objects.filter(
                    origin=origin, destination=dest, forecast_date__gte=start_date
                ).delete()
                ForecastMonthly.objects.bulk_create(monthly_objects)

            # --- C. 准备聚合数据 (拼接 历史 + 预测) ---
            # 目的是为了计算出完整的季度/年度数值，因为单纯的预测数据可能从季度中间开始

            current_year = start_date.year
            history_start_date = datetime(current_year, 1, 1).date()  # 从当年年初开始补齐

            if not is_other:
                # 常规航线：从 DB 读取历史真实值
                history_qs = FlightMarketRecord.objects.filter(
                    origin=origin,
                    destination=dest,
                    year_month__gte=history_start_date,
                    year_month__lt=start_date
                ).values('year_month', 'route_total_seats', 'distance_km')

                history_df = pd.DataFrame(list(history_qs))
                if not history_df.empty:
                    history_df = history_df.rename(columns={
                        'year_month': 'YearMonth',
                        'route_total_seats': 'Seats',
                        'distance_km': 'Distance'
                    })
                    history_df['YearMonth'] = pd.to_datetime(history_df['YearMonth'])
                    history_df['ASK'] = history_df['Seats'] * pd.to_numeric(history_df['Distance'])
                else:
                    history_df = pd.DataFrame(columns=['YearMonth', 'Seats', 'ASK'])
            else:
                # Other 航线：尝试读取 CSV 历史 (因为 DB 里可能没有聚合好的 Other 记录)
                if history_csv_path and os.path.exists(history_csv_path):
                    try:
                        history_df = pd.read_csv(history_csv_path)
                        history_df['YearMonth'] = pd.to_datetime(history_df['YearMonth'])
                        history_df['Seats'] = 0  # Other 只有 ASK
                        # 确保列名
                        if 'ASK' not in history_df.columns and 'Predicted_ASK' in history_df.columns:
                            history_df = history_df.rename(columns={'Predicted_ASK': 'ASK'})

                        # 截取当年年初到预测开始前的数据
                        history_df = history_df[
                            (history_df['YearMonth'] >= pd.Timestamp(history_start_date)) &
                            (history_df['YearMonth'] < start_date)
                            ]
                    except Exception:
                        history_df = pd.DataFrame(columns=['YearMonth', 'Seats', 'ASK'])
                else:
                    history_df = pd.DataFrame(columns=['YearMonth', 'Seats', 'ASK'])

            # 统一预测数据的列名以便拼接
            pred_clean = pred_df[['YearMonth', 'Predicted_Seats', 'Predicted_ASK']].rename(
                columns={'Predicted_Seats': 'Seats', 'Predicted_ASK': 'ASK'}
            )

            # 拼接
            full_timeline = pd.concat([history_df[['YearMonth', 'Seats', 'ASK']], pred_clean], axis=0)

            if full_timeline.empty:
                return

            full_timeline = full_timeline.sort_values('YearMonth').set_index('YearMonth')

            # --- D. 季度聚合入库 (ForecastQuarterly) ---
            quarterly_df = full_timeline.resample('QS').sum()

            # 过滤掉早于预测开始那个季度的旧数据 (只存未来的/包含预测部分的)
            q_start_limit = pd.Timestamp(start_date).to_period('Q').start_time
            quarterly_df = quarterly_df[quarterly_df.index >= q_start_limit]

            # 剔除末尾不完整季度
            last_date = full_timeline.index.max()
            if last_date.month not in [3, 6, 9, 12]:
                quarterly_df = quarterly_df.iloc[:-1]

            self.save_aggregated(ForecastQuarterly, quarterly_df, origin, dest)

            # --- E. 年度聚合入库 (ForecastYearly) ---
            yearly_df = full_timeline.resample('YS').sum()

            y_start_limit = pd.Timestamp(start_date).to_period('Y').start_time
            yearly_df = yearly_df[yearly_df.index >= y_start_limit]

            # 剔除末尾不完整年份
            if last_date.month != 12:
                yearly_df = yearly_df.iloc[:-1]

            self.save_aggregated(ForecastYearly, yearly_df, origin, dest)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"处理航线 {origin}-{dest} 入库失败: {e}"))

    def save_aggregated(self, ModelClass, df, origin, dest):
        """
        通用保存函数：用于季度和年度数据
        """
        if df.empty:
            return

        objects = []
        for date_idx, row in df.iterrows():
            objects.append(ModelClass(
                origin=origin,
                destination=dest,
                forecast_date=date_idx,
                seats=row['Seats'],
                ask=row['ASK']
            ))

        start_date = df.index.min()

        # 事务写入
        with transaction.atomic():
            ModelClass.objects.filter(
                origin=origin, destination=dest, forecast_date__gte=start_date
            ).delete()
            ModelClass.objects.bulk_create(objects)