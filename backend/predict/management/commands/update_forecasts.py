import os
import pandas as pd
import numpy as np
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, F

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
        parser.add_argument('--lr_ratio', type=float, default=None, help="覆盖配置：趋势预测占比")

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
        if options['lr_ratio']:
            TRAIN_CONFIG['max_lr_ratio'] = options['lr_ratio']

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
        self.process_and_ingest_aggregated(results_dir, top_routes_list)

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

    def process_and_ingest_aggregated(self, results_dir, top_routes_hint):
        """
        核心逻辑：
        1. 扫描结果目录，识别所有的航线。
        2. 按无向对 (A, B) 归组。
        3. 对每一组，读取 A->B 和 B->A 的预测文件，相加。
        4. 对每一组，读取数据库的历史数据，相加。
        5. 拼接并入库。
        """

        # 1. 构建无向航线映射表
        # pair_map 结构: { ('PEK', 'SZX'): [('PEK', 'SZX'), ('SZX', 'PEK')] }
        pair_map = {}

        # 遍历结果目录下的所有文件夹，找出真正生成了预测的航线
        all_folders = [f for f in os.listdir(results_dir) if os.path.isdir(os.path.join(results_dir, f))]

        for folder in all_folders:
            if folder == 'OTHER_OTHER':
                continue

            try:
                origin, dest = folder.split('_')
                # 按字母顺序排序，确保唯一Key
                sorted_key = tuple(sorted([origin, dest]))

                if sorted_key not in pair_map:
                    pair_map[sorted_key] = []

                pair_map[sorted_key].append((origin, dest))
            except ValueError:
                continue

        self.stdout.write(f"识别到 {len(pair_map)} 个无向航线对 (Top N) 准备聚合入库")

        # 2. 处理 Top N 聚合入库
        count = 0
        for (sorted_origin, sorted_dest), direction_list in pair_map.items():
            self.ingest_aggregated_pair(
                results_dir,
                target_origin=sorted_origin,
                target_dest=sorted_dest,
                direction_list=direction_list
            )
            count += 1
            if count % 50 == 0:
                self.stdout.write(f"已处理 {count} / {len(pair_map)} 个聚合航线")

        # 3. 处理 Other 航线
        other_pred_path = os.path.join(results_dir, 'OTHER_OTHER', 'future_predictions.csv')
        other_hist_path = os.path.join(results_dir, 'OTHER_OTHER', 'history_ask.csv')

        if os.path.exists(other_pred_path):
            self.stdout.write("正在处理 Other-Other 聚合航线...")
            # Other 不需要方向聚合，直接调用单条处理逻辑的变体，或者复用聚合逻辑(directions=[])
            self.ingest_aggregated_pair(
                results_dir,
                target_origin='OTHER',
                target_dest='OTHER',
                direction_list=[],  # 特殊标记
                is_other=True
            )

    def ingest_aggregated_pair(self, results_dir, target_origin, target_dest, direction_list, is_other=False):
        """
        聚合单个航线对并入库
        :param target_origin: 存入数据库的 Origin (通常是字母序小的)
        :param target_dest: 存入数据库的 Dest
        :param direction_list: 包含实际存在的方向 [('PEK', 'SZX'), ('SZX', 'PEK')]
        """
        try:
            # --- A. 聚合预测数据 (Future) ---
            combined_pred_df = pd.DataFrame()

            if is_other:
                # Other 特殊处理
                pred_path = os.path.join(results_dir, 'OTHER_OTHER', 'future_predictions.csv')
                if os.path.exists(pred_path):
                    df = pd.read_csv(pred_path)
                    df['YearMonth'] = pd.to_datetime(df['YearMonth'])
                    df = df.set_index('YearMonth')
                    combined_pred_df = df[['Predicted_Seats', 'Predicted_ASK']].fillna(0)
                    # 重命名以统一
                    combined_pred_df.rename(columns={'Predicted_Seats': 'Seats', 'Predicted_ASK': 'ASK'}, inplace=True)
            else:
                # 常规航线：遍历方向并相加
                for org, dst in direction_list:
                    csv_path = os.path.join(results_dir, f"{org}_{dst}", "future_predictions.csv")
                    if os.path.exists(csv_path):
                        df = pd.read_csv(csv_path)
                        df['YearMonth'] = pd.to_datetime(df['YearMonth'])
                        df = df.set_index('YearMonth')

                        # 确保列存在
                        if 'Predicted_ASK' not in df.columns:
                            df['Predicted_ASK'] = df['Predicted_Seats'] * df['Distance']

                        cols_to_sum = df[['Predicted_Seats', 'Predicted_ASK']].rename(
                            columns={'Predicted_Seats': 'Seats', 'Predicted_ASK': 'ASK'}
                        ).fillna(0)

                        if combined_pred_df.empty:
                            combined_pred_df = cols_to_sum
                        else:
                            # 关键：按索引(日期)对齐相加
                            combined_pred_df = combined_pred_df.add(cols_to_sum, fill_value=0)

            if combined_pred_df.empty:
                return

            # 预测数据的起始时间
            pred_start_date = combined_pred_df.index.min()

            # --- B. 更新月度预测表 (ForecastMonthly) ---
            # 存入数据库
            monthly_objects = []
            for date_idx, row in combined_pred_df.iterrows():
                monthly_objects.append(ForecastMonthly(
                    origin=target_origin,
                    destination=target_dest,
                    forecast_date=date_idx,
                    seats=row['Seats'],
                    ask=row['ASK']
                ))

            with transaction.atomic():
                # 清除旧数据 (按聚合后的 Key)
                ForecastMonthly.objects.filter(
                    origin=target_origin, destination=target_dest, forecast_date__gte=pred_start_date
                ).delete()
                ForecastMonthly.objects.bulk_create(monthly_objects)

            # --- C. 聚合历史数据 (History) ---
            # 为了计算季度/年度，我们需要把历史数据也聚合起来

            current_year = pred_start_date.year
            history_start_date = datetime(current_year, 1, 1).date()

            combined_history_df = pd.DataFrame()

            if is_other:
                # Other 历史来自 csv
                hist_path = os.path.join(results_dir, 'OTHER_OTHER', 'history_ask.csv')
                if os.path.exists(hist_path):
                    h_df = pd.read_csv(hist_path)
                    h_df['YearMonth'] = pd.to_datetime(h_df['YearMonth'])
                    h_df = h_df[
                        (h_df['YearMonth'] >= pd.Timestamp(history_start_date)) & (h_df['YearMonth'] < pred_start_date)]
                    h_df = h_df.set_index('YearMonth')
                    # Other 历史通常只有 ASK，Seats 设为 0
                    if 'ASK' not in h_df.columns and 'Predicted_ASK' in h_df.columns:
                        h_df.rename(columns={'Predicted_ASK': 'ASK'}, inplace=True)
                    h_df['Seats'] = 0
                    combined_history_df = h_df[['Seats', 'ASK']]
            else:
                # 常规航线：从 DB 聚合两个方向的历史
                # 构建 OR 查询条件
                # 实际上直接分别查两次相加在逻辑上最简单清晰

                for org, dst in direction_list:
                    qs = FlightMarketRecord.objects.filter(
                        origin=org,
                        destination=dst,
                        year_month__gte=history_start_date,
                        year_month__lt=pred_start_date
                    ).values('year_month', 'route_total_seats', 'distance_km')

                    df_hist = pd.DataFrame(list(qs))
                    if not df_hist.empty:
                        df_hist['YearMonth'] = pd.to_datetime(df_hist['year_month'])
                        df_hist = df_hist.set_index('YearMonth')
                        df_hist['Seats'] = pd.to_numeric(df_hist['route_total_seats']).fillna(0).astype(int)
                        df_hist['ASK'] = (df_hist['Seats'] * pd.to_numeric(df_hist['distance_km']).fillna(0)).astype(
                            int)

                        cols = df_hist[['Seats', 'ASK']]

                        if combined_history_df.empty:
                            combined_history_df = cols
                        else:
                            combined_history_df = combined_history_df.add(cols, fill_value=0)

            # --- D. 拼接并生成季度/年度数据 ---

            # 统一列名
            combined_pred_df = combined_pred_df[['Seats', 'ASK']]

            # 拼接 历史 + 预测
            full_timeline = pd.concat([combined_history_df, combined_pred_df], axis=0)

            if full_timeline.empty:
                return

            full_timeline = full_timeline.sort_index()

            # 1. 季度聚合 (ForecastQuarterly)
            quarterly_df = full_timeline.resample('QS').sum()
            # 过滤掉旧数据
            q_start_limit = pd.Timestamp(pred_start_date).to_period('Q').start_time
            quarterly_df = quarterly_df[quarterly_df.index >= q_start_limit]

            # 剔除末尾不完整季度
            last_date = full_timeline.index.max()
            if last_date.month not in [3, 6, 9, 12]:
                quarterly_df = quarterly_df.iloc[:-1]

            self.save_aggregated(ForecastQuarterly, quarterly_df, target_origin, target_dest)

            # 2. 年度聚合 (ForecastYearly)
            yearly_df = full_timeline.resample('YS').sum()
            y_start_limit = pd.Timestamp(pred_start_date).to_period('Y').start_time
            yearly_df = yearly_df[yearly_df.index >= y_start_limit]

            if last_date.month != 12:
                yearly_df = yearly_df.iloc[:-1]

            self.save_aggregated(ForecastYearly, yearly_df, target_origin, target_dest)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"处理聚合航线 {target_origin}-{target_dest} 失败: {e}"))
            import traceback
            traceback.print_exc()


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