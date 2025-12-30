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

        parser.add_argument('--del_yiqing', action='store_true', help="覆盖配置: 强制开启疫情数据剔除")
        parser.add_argument('--no_del_yiqing', action='store_false', dest='del_yiqing',
                            help="覆盖配置: 强制关闭疫情数据剔除")
        parser.set_defaults(del_yiqing=None)

    def handle(self, *args, **options):
        # 0. 获取命令行参数
        top_n = options['top_n']
        skip_train = options['skip_train']

        self.stdout.write(self.style.SUCCESS(f"=== 开始全流程更新任务 (Top {top_n}) ==="))

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
        if options['del_yiqing'] is not None:
            TRAIN_CONFIG['del_yiqing'] = options['del_yiqing']

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
        基于 DataFrame 生成排名 (修正版：按双向汇总排名)
        """
        # 1. 预处理年份
        df['dt'] = pd.to_datetime(df['YearMonth'])
        df['year'] = df['dt'].dt.year

        # 简化逻辑：取每条航线最大年份的前一年作为基准
        route_max_dates = df.groupby(['Origin', 'Destination'])['dt'].max().reset_index()
        route_max_dates['target_year'] = route_max_dates['dt'].dt.year - 1

        merged = pd.merge(df, route_max_dates, on=['Origin', 'Destination'])
        target_data = merged[merged['year'] == merged['target_year']]

        # 2. 统计单向数据
        stats = target_data.groupby(['Origin', 'Destination']).agg({
            'Route_Total_Seats': 'sum',
            'Distance (KM)': 'mean'
        }).reset_index()

        # 计算单向的"价值" (ASK)
        stats['Calculated_Value'] = stats['Route_Total_Seats'] * stats['Distance (KM)']

        # ================= 修改开始 =================
        # 3. 生成无向航线对标识 (Sort Origin/Dest to make A-B same as B-A)
        # 使用 frozenset 或 tuple(sorted) 来创建统一的 Key
        stats['Route_Pair'] = stats.apply(lambda x: tuple(sorted([x['Origin'], x['Destination']])), axis=1)

        # 4. 按航线对聚合计算总价值
        pair_stats = stats.groupby('Route_Pair')['Calculated_Value'].sum().reset_index()
        pair_stats = pair_stats.rename(columns={'Calculated_Value': 'Pair_Total_Value'})

        # 5. 对航线对进行排名，取 Top N
        top_pairs_df = pair_stats.sort_values(by='Pair_Total_Value', ascending=False).head(top_n)
        top_pairs_set = set(top_pairs_df['Route_Pair'])  # 拿到入选的 Top N 个无向对

        # 6. 反向筛选：从原始 stats 中把属于这些 Pair 的单向航线都找出来
        # 这样能保证 A->B 和 B->A 同时被选中（如果原始数据里都有的话）
        final_stats = stats[stats['Route_Pair'].isin(top_pairs_set)].copy()

        # 按单向价值降序排列一下，方便查看
        final_stats = final_stats.sort_values(by='Calculated_Value', ascending=False)

        # 提取最终要训练的单向列表
        top_routes = final_stats[['Origin', 'Destination']].values.tolist()

        self.stdout.write(f"排名逻辑修正：已选取 Top {top_n} 个双向航线对，共生成 {len(top_routes)} 条单向训练任务")

        # 返回 final_stats (用于保存CSV) 和 top_routes (用于后续遍历)
        return final_stats, top_routes

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
        核心入库逻辑：单向航线入库
        Change: 现在返回 full_timeline (DataFrame) 用于 ALL-ALL 累加
        """
        try:
            # --- A. 读取预测数据 ---
            pred_df = pd.read_csv(csv_path)
            pred_df['YearMonth'] = pd.to_datetime(pred_df['YearMonth'])

            # 预测起始时间
            start_date = pred_df['YearMonth'].min()

            # 兼容：计算 ASK
            if 'Predicted_ASK' not in pred_df.columns:
                # 防止由 Predicted_Seats * Distance 计算时出现缺失
                pred_df['Predicted_ASK'] = pred_df['Predicted_Seats'] * pred_df.get('Distance', 0)

            # --- B. 更新月度预测表 (ForecastMonthly) ---
            monthly_objects = []
            for _, row in pred_df.iterrows():
                monthly_objects.append(ForecastMonthly(
                    origin=origin,
                    destination=dest,
                    forecast_date=row['YearMonth'],
                    seats=row['Predicted_Seats'],
                    ask=row['Predicted_ASK']
                ))

            with transaction.atomic():
                ForecastMonthly.objects.filter(
                    origin=origin, destination=dest, forecast_date__gte=start_date
                ).delete()
                ForecastMonthly.objects.bulk_create(monthly_objects)

            # --- C. 准备聚合数据 (拼接 历史 + 预测) ---
            current_year = start_date.year
            history_start_date = datetime(current_year, 1, 1).date()

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
                    # 确保数值类型
                    history_df['Seats'] = pd.to_numeric(history_df['Seats']).fillna(0)
                    history_df['Distance'] = pd.to_numeric(history_df['Distance']).fillna(0)
                    history_df['ASK'] = history_df['Seats'] * history_df['Distance']
                else:
                    history_df = pd.DataFrame(columns=['YearMonth', 'Seats', 'ASK'])
            else:
                # Other 航线：尝试读取 CSV 历史
                if history_csv_path and os.path.exists(history_csv_path):
                    try:
                        history_df = pd.read_csv(history_csv_path)
                        history_df['YearMonth'] = pd.to_datetime(history_df['YearMonth'])
                        history_df['Seats'] = 0  # Other 只有 ASK
                        if 'ASK' not in history_df.columns and 'Predicted_ASK' in history_df.columns:
                            history_df = history_df.rename(columns={'Predicted_ASK': 'ASK'})

                        history_df = history_df[
                            (history_df['YearMonth'] >= pd.Timestamp(history_start_date)) &
                            (history_df['YearMonth'] < start_date)
                            ]
                    except Exception:
                        history_df = pd.DataFrame(columns=['YearMonth', 'Seats', 'ASK'])
                else:
                    history_df = pd.DataFrame(columns=['YearMonth', 'Seats', 'ASK'])

            # 统一列名
            pred_clean = pred_df[['YearMonth', 'Predicted_Seats', 'Predicted_ASK']].rename(
                columns={'Predicted_Seats': 'Seats', 'Predicted_ASK': 'ASK'}
            )

            # 拼接
            full_timeline = pd.concat([history_df[['YearMonth', 'Seats', 'ASK']], pred_clean], axis=0)

            if full_timeline.empty:
                return None

            full_timeline = full_timeline.groupby('YearMonth')[['Seats', 'ASK']].sum().reset_index()
            full_timeline = full_timeline.sort_values('YearMonth').set_index('YearMonth')
            full_timeline = full_timeline[['Seats', 'ASK']].fillna(0)  # 确保只返回数值列

            # --- D. 季度聚合入库 (ForecastQuarterly) ---
            quarterly_df = full_timeline.resample('QS').sum()
            q_start_limit = pd.Timestamp(start_date).to_period('Q').start_time
            quarterly_df = quarterly_df[quarterly_df.index >= q_start_limit]

            last_date = full_timeline.index.max()
            if last_date.month not in [3, 6, 9, 12]:
                quarterly_df = quarterly_df.iloc[:-1]

            self.save_aggregated(ForecastQuarterly, quarterly_df, origin, dest)

            # --- E. 年度聚合入库 (ForecastYearly) ---
            yearly_df = full_timeline.resample('YS').sum()
            y_start_limit = pd.Timestamp(start_date).to_period('Y').start_time
            yearly_df = yearly_df[yearly_df.index >= y_start_limit]

            if last_date.month != 12:
                yearly_df = yearly_df.iloc[:-1]

            self.save_aggregated(ForecastYearly, yearly_df, origin, dest)

            # === [关键修改] 返回完整时间线供 ALL-ALL 累加 ===
            return full_timeline

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"处理航线 {origin}-{dest} 入库失败: {e}"))
            import traceback
            traceback.print_exc()
            return None

    def process_and_ingest_aggregated(self, results_dir, top_routes_list):
        """
        逻辑修改：
        1. 遍历 top_routes_list (约1000条单向)，逐个入库。
        2. 处理 OTHER。
        3. 累加所有数据生成 ALL-ALL。
        最终结果数量 = TopN(单向) + 1(Other) + 1(All)
        """

        grand_total_df = pd.DataFrame()
        processed_count = 0

        self.stdout.write(f"开始处理入库：预计处理 {len(top_routes_list)} 条单向航线 + Other + All")

        # 1. 处理 Top N 单向航线
        for origin, dest in top_routes_list:
            folder_name = f"{origin}_{dest}"
            pred_file = os.path.join(results_dir, folder_name, 'future_predictions.csv')

            if os.path.exists(pred_file):
                # 调用单条入库，并获取返回的数据
                route_df = self.ingest_single_route(origin, dest, pred_file)

                # 累加到 ALL-ALL
                if route_df is not None and not route_df.empty:
                    if grand_total_df.empty:
                        grand_total_df = route_df.copy()
                    else:
                        # fill_value=0 保证日期对齐，若某日期缺失则视为0
                        grand_total_df = grand_total_df.add(route_df, fill_value=0)

                processed_count += 1
                if processed_count % 100 == 0:
                    self.stdout.write(f"已处理 {processed_count} 条航线...")
            else:
                # 可能是由于数据过滤导致该方向被剔除，属正常现象
                pass

        # 2. 处理 Other 航线
        other_pred_path = os.path.join(results_dir, 'OTHER_OTHER', 'future_predictions.csv')
        other_hist_path = os.path.join(results_dir, 'OTHER_OTHER', 'history_ask.csv')

        if os.path.exists(other_pred_path):
            self.stdout.write("正在处理 Other-Other 航线...")
            other_df = self.ingest_single_route(
                'OTHER', 'OTHER',
                other_pred_path,
                is_other=True,
                history_csv_path=other_hist_path
            )

            # 累加 Other 到 ALL-ALL
            if other_df is not None and not other_df.empty:
                if grand_total_df.empty:
                    grand_total_df = other_df.copy()
                else:
                    grand_total_df = grand_total_df.add(other_df, fill_value=0)

        # 3. 处理并入库 ALL-ALL
        if not grand_total_df.empty:
            self.stdout.write(self.style.SUCCESS("正在生成并入库 ALL-ALL 全市场数据..."))
            self.ingest_all_all(grand_total_df)
        else:
            self.stdout.write(self.style.WARNING("未生成任何数据，无法计算 ALL-ALL"))

        self.stdout.write(self.style.SUCCESS(f"入库完成。共处理单向航线: {processed_count}, 包含Other和All。"))

    def ingest_aggregated_pair(self, results_dir, target_origin, target_dest, direction_list, is_other=False):
        """
        聚合单个航线对并入库
        :return: full_timeline (DataFrame) or None. 返回该航线完整的历史+预测数据供累加使用
        """
        try:
            # --- A. 聚合预测数据 (Future) ---
            combined_pred_df = pd.DataFrame()

            if is_other:
                pred_path = os.path.join(results_dir, 'OTHER_OTHER', 'future_predictions.csv')
                if os.path.exists(pred_path):
                    df = pd.read_csv(pred_path)
                    df['YearMonth'] = pd.to_datetime(df['YearMonth'])
                    df = df.set_index('YearMonth')
                    combined_pred_df = df[['Predicted_Seats', 'Predicted_ASK']].fillna(0)
                    combined_pred_df.rename(columns={'Predicted_Seats': 'Seats', 'Predicted_ASK': 'ASK'}, inplace=True)
            else:
                for org, dst in direction_list:
                    csv_path = os.path.join(results_dir, f"{org}_{dst}", "future_predictions.csv")
                    if os.path.exists(csv_path):
                        df = pd.read_csv(csv_path)
                        df['YearMonth'] = pd.to_datetime(df['YearMonth'])
                        df = df.set_index('YearMonth')
                        if 'Predicted_ASK' not in df.columns:
                            df['Predicted_ASK'] = df['Predicted_Seats'] * df['Distance']
                        cols_to_sum = df[['Predicted_Seats', 'Predicted_ASK']].rename(
                            columns={'Predicted_Seats': 'Seats', 'Predicted_ASK': 'ASK'}
                        ).fillna(0)

                        if combined_pred_df.empty:
                            combined_pred_df = cols_to_sum
                        else:
                            combined_pred_df = combined_pred_df.add(cols_to_sum, fill_value=0)

            if combined_pred_df.empty:
                return None

            pred_start_date = combined_pred_df.index.min()

            # --- B. 更新月度预测表 (ForecastMonthly) ---
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
                ForecastMonthly.objects.filter(
                    origin=target_origin, destination=target_dest, forecast_date__gte=pred_start_date
                ).delete()
                ForecastMonthly.objects.bulk_create(monthly_objects)

            # --- C. 聚合历史数据 (History) ---
            current_year = pred_start_date.year
            history_start_date = datetime(current_year, 1, 1).date()
            combined_history_df = pd.DataFrame()

            if is_other:
                hist_path = os.path.join(results_dir, 'OTHER_OTHER', 'history_ask.csv')
                if os.path.exists(hist_path):
                    h_df = pd.read_csv(hist_path)
                    h_df['YearMonth'] = pd.to_datetime(h_df['YearMonth'])
                    h_df = h_df[
                        (h_df['YearMonth'] >= pd.Timestamp(history_start_date)) & (h_df['YearMonth'] < pred_start_date)]
                    h_df = h_df.set_index('YearMonth')
                    if 'ASK' not in h_df.columns and 'Predicted_ASK' in h_df.columns:
                        h_df.rename(columns={'Predicted_ASK': 'ASK'}, inplace=True)
                    h_df['Seats'] = 0
                    combined_history_df = h_df[['Seats', 'ASK']]
            else:
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
            combined_pred_df = combined_pred_df[['Seats', 'ASK']]
            full_timeline = pd.concat([combined_history_df, combined_pred_df], axis=0)

            if full_timeline.empty:
                return None

            full_timeline = full_timeline.sort_index()

            # 1. 季度聚合
            quarterly_df = full_timeline.resample('QS').sum()
            q_start_limit = pd.Timestamp(pred_start_date).to_period('Q').start_time
            quarterly_df = quarterly_df[quarterly_df.index >= q_start_limit]

            last_date = full_timeline.index.max()
            if last_date.month not in [3, 6, 9, 12]:
                quarterly_df = quarterly_df.iloc[:-1]

            self.save_aggregated(ForecastQuarterly, quarterly_df, target_origin, target_dest)

            # 2. 年度聚合
            yearly_df = full_timeline.resample('YS').sum()
            y_start_limit = pd.Timestamp(pred_start_date).to_period('Y').start_time
            yearly_df = yearly_df[yearly_df.index >= y_start_limit]
            if last_date.month != 12:
                yearly_df = yearly_df.iloc[:-1]

            self.save_aggregated(ForecastYearly, yearly_df, target_origin, target_dest)

            # --- [新增] 返回 Full Timeline 供 ALL-ALL 累加 ---
            return full_timeline

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"处理聚合航线 {target_origin}-{target_dest} 失败: {e}"))
            import traceback
            traceback.print_exc()
            return None

    def ingest_all_all(self, grand_total_df):
        """
        [新增] 专门处理 ALL-ALL 的入库逻辑
        grand_total_df 包含所有的历史+预测数据
        """
        try:
            target_origin = 'ALL'
            target_dest = 'ALL'

            grand_total_df = grand_total_df.sort_index()

            # --- 1. 入库 ForecastMonthly (ALL-ALL) ---
            # 只有预测部分入库到 Monthly 表？通常逻辑是这样。
            # 我们需要推断预测开始时间。
            # 这里简单处理：假设当前时间往后都是预测，或者根据最后一条数据倒推。
            # 但更准确的是：grand_total_df 实际上包含了历史部分。
            # Monthly 表通常我们希望展示完整的趋势，或者只展示预测。
            # 既然之前的逻辑是 "ForecastMonthly 存 future_predictions"，那么我们这里也应该截取一下。
            # 我们可以取当前月或下个月作为分界线，或者更简单的：
            # 由于 grand_total_df 是 history + future 的累加，
            # 我们很难精确知道“预测”是从哪一天开始的（因为不同航线可能稍微有点差异），
            # 但通常都是统一的 current_date。
            # 建议：直接将 grand_total_df 中最近的数据视为预测（例如最近12个月后的）。
            # 或者更安全的方法：不做截断，全部存入？不，ForecastMonthly 定义通常是预测值。

            # 稍微Hack一下：我们取所有列的非零值的点。
            # 但实际上，为了保持一致性，我们可以假设只有未来的数据才写入 ForecastMonthly。
            # 获取当前日期
            now = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # 假设预测是从下个月或者当月开始 (根据你的业务逻辑，通常是当前脚本运行时间)
            # 这里我们保守一点，只存 `now` 之后的到 Monthly 表，或者存全部。
            # **参照 ingest_aggregated_pair 的逻辑，它是只存 combined_pred_df**。
            # 由于 grand_total_df 混在一起了，我们可以通过和数据库里最新的历史数据比对，
            # 或者简单点：
            # 直接把 grand_total_df 全部存进去？这样历史数据也会变成"预测"。
            # 最好是：既然我们已经走到这一步，就假设 grand_total_df 的后半段是预测。

            # 修正策略：在 ForecastMonthly 中，ALL-ALL 通常既需要看历史也需要看未来。
            # 但如果表定义严格是 Forecast，那就只存未来。
            # 让我们找一个 split point。通常是当前日期的下个月。
            split_date = pd.Timestamp(now)

            # 提取预测部分 (日期 >= split_date)
            # 如果你的预测脚本是生成的未来20年，那肯定是从当前时间开始的。
            pred_part = grand_total_df[grand_total_df.index >= split_date]

            monthly_objects = []
            for date_idx, row in pred_part.iterrows():
                monthly_objects.append(ForecastMonthly(
                    origin=target_origin,
                    destination=target_dest,
                    forecast_date=date_idx,
                    seats=row['Seats'],
                    ask=row['ASK']
                ))

            with transaction.atomic():
                ForecastMonthly.objects.filter(
                    origin=target_origin, destination=target_dest, forecast_date__gte=split_date
                ).delete()
                ForecastMonthly.objects.bulk_create(monthly_objects)

            # --- 2. 入库 ForecastQuarterly (ALL-ALL) ---
            quarterly_df = grand_total_df.resample('QS').sum()
            # 存全部还是只存未来？ingest_aggregated_pair 里是有过滤 q_start_limit 的。
            # 这里 ALL-ALL 我们通常希望能看到历史趋势对比，建议存多一点，或者保持一致只存未来。
            # 保持一致性：只存 split_date 之后的季度
            q_start_limit = split_date.to_period('Q').start_time
            quarterly_df = quarterly_df[quarterly_df.index >= q_start_limit]

            # 剔除末尾不完整
            last_date = grand_total_df.index.max()
            if last_date.month not in [3, 6, 9, 12]:
                quarterly_df = quarterly_df.iloc[:-1]

            self.save_aggregated(ForecastQuarterly, quarterly_df, target_origin, target_dest)

            # --- 3. 入库 ForecastYearly (ALL-ALL) ---
            yearly_df = grand_total_df.resample('YS').sum()
            y_start_limit = split_date.to_period('Y').start_time
            yearly_df = yearly_df[yearly_df.index >= y_start_limit]

            if last_date.month != 12:
                yearly_df = yearly_df.iloc[:-1]

            self.save_aggregated(ForecastYearly, yearly_df, target_origin, target_dest)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"ALL-ALL 入库失败: {e}"))
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