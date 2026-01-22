import os
import django
import pandas as pd
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()
OUTPUT_DIR = os.path.join(
    settings.BASE_DIR, "Predict_Datas"
)
# --- 配置区：在此直接写入参数 ---
TOP_N = 500  # 你需要的 Top N 数量


def refresh_rankings():

    # 延迟导入，确保 Django 已初始化
    from predict.models import FlightMarketRecord
    from predict.predictive_algorithm.field_mapping import get_field_mapping

    print(f"=== 开始更新排名文件 (Top {TOP_N}) ===")

    # 1. 加载数据
    print("正在从数据库加载数据...")
    qs = FlightMarketRecord.objects.all().values()
    df = pd.DataFrame(list(qs))

    if df.empty:
        print("错误：数据库中没有发现 FlightMarketRecord 数据")
        return

    # 2. 字段映射与清洗
    field_mapping = get_field_mapping()
    df = df.rename(columns=field_mapping)

    # 转换数值列（排除非数值字段）
    exclude_cols = ['YearMonth', 'Origin', 'Destination', 'International Flight', 'Region', 'dt', 'year']
    for col in df.columns:
        if col not in exclude_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 3. 预处理日期
    df['dt'] = pd.to_datetime(df['YearMonth'])
    df['year'] = df['dt'].dt.year

    # 找到每条航线最大年份的前一年作为基准 (参考原脚本逻辑)
    route_max_dates = df.groupby(['Origin', 'Destination'])['dt'].max().reset_index()
    route_max_dates['target_year'] = route_max_dates['dt'].dt.year - 1
    merged = pd.merge(df, route_max_dates, on=['Origin', 'Destination'])
    target_data = merged[merged['year'] == merged['target_year']]

    # 4. 计算单向 ASK (Seats * Distance)
    stats = target_data.groupby(['Origin', 'Destination']).agg({
        'Route_Total_Seats': 'sum',
        'Distance (KM)': 'mean'
    }).reset_index()
    stats['Calculated_Value'] = stats['Route_Total_Seats'] * stats['Distance (KM)']

    # 生成无向对标识 (A-B 与 B-A 统一)
    stats['Route_Pair'] = stats.apply(lambda x: tuple(sorted([x['Origin'], x['Destination']])), axis=1)

    # --- 生成第一个排名文件 (Top N) ---
    print(f"正在生成 route_ranking.csv (Top {TOP_N})...")
    pair_stats = stats.groupby('Route_Pair')['Calculated_Value'].sum().reset_index()
    pair_stats = pair_stats.rename(columns={'Calculated_Value': 'Pair_Total_Value'})

    top_pairs_df = pair_stats.sort_values(by='Pair_Total_Value', ascending=False).head(TOP_N)
    top_pairs_set = set(top_pairs_df['Route_Pair'])

    ranking_df1 = stats[stats['Route_Pair'].isin(top_pairs_set)].copy()
    ranking_df1 = ranking_df1.sort_values(by='Calculated_Value', ascending=False)

    # --- 生成第二个排名文件 (全量排名) ---
    print("正在生成 route_ranking2.csv (全量)...")
    ranking_df2 = stats.sort_values(by='Calculated_Value', ascending=False)

    # 5. 保存结果
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    path1 = os.path.join(OUTPUT_DIR, 'route_ranking.csv')
    path2 = os.path.join(OUTPUT_DIR, 'route_ranking2.csv')

    ranking_df1.to_csv(path1, index=False)
    ranking_df2.to_csv(path2, index=False)

    print(f"成功！文件已保存：\n1. {path1}\n2. {path2}")


if __name__ == "__main__":
    refresh_rankings()