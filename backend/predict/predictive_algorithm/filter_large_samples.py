import pandas as pd
import numpy as np


def filter_routes(min_ratio=None, report_path=None, span_ratio_threshold=0.9,
                  filter_mode='top_n', top_n=None):
    """
    筛选满足条件的航线，仅支持 Top-N 模式。
    适配新的 route_ranking.csv 格式 (包含 Calculated_Value)。

    参数:
    report_path - 航线报告文件路径
    top_n - 前n条航线数量
    min_ratio, span_ratio_threshold, filter_mode - 保留这些参数以兼容旧代码调用，但不再生效

    返回:
    (valid_routes, remaining_routes) - 满足条件的航线DataFrame和剩余航线DataFrame
    """
    # 1. 读取航线报告
    if report_path is None:
        print("错误: 必须提供 report_path")
        return pd.DataFrame(), pd.DataFrame()

    route_report = pd.read_csv(report_path)

    # 2. 确保必要的列存在
    required_cols = ['Origin', 'Destination', 'Calculated_Value']
    for col in required_cols:
        if col not in route_report.columns:
            print(f"错误: 报告中缺少列 {col}")
            return pd.DataFrame(), pd.DataFrame()

    # 3. 预处理年月列
    # 新格式类似: 2011-01-01 00:00:00 -> 转换为 YYYY-MM 字符串以便阅读
    if 'Min_YearMonth' in route_report.columns:
        route_report['Min_YearMonth'] = pd.to_datetime(route_report['Min_YearMonth']).dt.strftime('%Y-%m')
    if 'Max_YearMonth' in route_report.columns:
        route_report['Max_YearMonth'] = pd.to_datetime(route_report['Max_YearMonth']).dt.strftime('%Y-%m')

    # 4. 按 Calculated_Value 降序排序 (数值越大排名越高)
    # 如果 Calculated_Value 缺失，尝试使用 Total_Seats_Prev_Year
    sort_col = 'Calculated_Value'
    if sort_col not in route_report.columns and 'Total_Seats_Prev_Year' in route_report.columns:
        sort_col = 'Total_Seats_Prev_Year'

    route_report = route_report.sort_values(by=sort_col, ascending=False).reset_index(drop=True)

    # 5. 执行 Top-N 筛选
    if top_n is None:
        # 如果未指定top_n，尝试默认值或报错，这里设默认值防止崩溃
        top_n = 50
        print(f"警告: 未提供 top_n 参数，默认使用前 {top_n} 条")

    print(f"筛选模式: Top-N (依据 {sort_col})")

    # 直接取前n条航线
    final_routes = route_report.head(top_n).copy()
    print(f"筛选出前 {len(final_routes)} 条航线")

    # 6. 添加辅助信息 (Time_Span)
    if 'Min_YearMonth' in final_routes.columns and 'Max_YearMonth' in final_routes.columns:
        final_routes['Time_Span'] = final_routes['Min_YearMonth'].astype(str) + " to " + final_routes[
            'Max_YearMonth'].astype(str)

    # 7. 获取剩余航线（不在筛选结果中的航线）
    if not final_routes.empty:
        # 创建航线标识符用于比较 (Origin, Destination)
        final_routes_ids = set(
            zip(final_routes['Origin'], final_routes['Destination'])
        )
        # 使用 apply 逐行检查是否在 final_routes 中
        # 注意：这里直接操作 route_report 的索引可能更快，但为了准确使用 Origin/Dest 对比
        remaining_mask = route_report.apply(
            lambda row: (row['Origin'], row['Destination']) not in final_routes_ids,
            axis=1
        )
        remaining_routes = route_report[remaining_mask].copy().reset_index(drop=True)
    else:
        remaining_routes = route_report.copy()

    return final_routes, remaining_routes


def double_filter_routes(report_path=None, top_n=None):
    """
    筛选满足条件的航线，支持无向 Top-N 模式。
    逻辑：将 A->B 和 B->A 视为同一条航线对，将其 Calculated_Value 相加后排名。
    选出前 N 个航线对后，返回这些对所包含的所有有向航线（通常是 2*N 条）。

    参数:
    report_path - 航线报告文件路径
    top_n - 前n个航线对（无向）
    """
    # 1. 读取航线报告
    if report_path is None:
        print("错误: 必须提供 report_path")
        return pd.DataFrame(), pd.DataFrame()

    route_report = pd.read_csv(report_path)

    # 2. 确保必要的列存在
    required_cols = ['Origin', 'Destination', 'Calculated_Value']
    for col in required_cols:
        if col not in route_report.columns:
            print(f"错误: 报告中缺少列 {col}")
            return pd.DataFrame(), pd.DataFrame()

    # 3. 确定排序依据列
    sort_col = 'Calculated_Value'
    if sort_col not in route_report.columns and 'Total_Seats_Prev_Year' in route_report.columns:
        sort_col = 'Total_Seats_Prev_Year'

    # 4. 执行无向 Top-N 筛选逻辑
    if top_n is None:
        top_n = 50
        print(f"警告: 未提供 top_n 参数，默认使用前 {top_n} 对航线")

    print(f"筛选模式: 无向 Top-N (依据 {sort_col} 聚合 A<->B 总和)")

    # --- 核心修改开始 ---

    # 4.1 创建无向标识符 (将 Origin 和 Destination 字母排序组合)
    # 例如 SZX-PEK 和 PEK-SZX 都会变成 ('PEK', 'SZX')
    route_report['Undirected_Pair_ID'] = route_report.apply(
        lambda row: tuple(sorted([str(row['Origin']), str(row['Destination'])])),
        axis=1
    )

    # 4.2 按无向标识符聚合计算总价值
    # 计算每一对航线的总价值 (Direction A + Direction B)
    pair_stats = route_report.groupby('Undirected_Pair_ID')[sort_col].sum().reset_index()
    pair_stats.rename(columns={sort_col: 'Pair_Total_Value'}, inplace=True)

    # 4.3 对航线对进行降序排序
    pair_stats = pair_stats.sort_values(by='Pair_Total_Value', ascending=False)

    # 4.4 取前 N 个航线对的 ID
    top_n_pair_ids = set(pair_stats.head(top_n)['Undirected_Pair_ID'])

    print(f"已选出前 {len(top_n_pair_ids)} 个高价值航线对 (Top Pairs)")

    # 4.5 回溯筛选原始数据
    # 如果某条有向航线属于这 Top N 个对之一，则保留
    mask_top = route_report['Undirected_Pair_ID'].isin(top_n_pair_ids)

    final_routes = route_report[mask_top].copy()
    remaining_routes = route_report[~mask_top].copy()

    # 为了方便查看，我们可以把 Pair_Total_Value merge 回去，并按这个总价值排序
    # 这样最终输出的 valid_routes.csv 里，同一个对的往返航线会排在一起
    final_routes = final_routes.merge(pair_stats, on='Undirected_Pair_ID', how='left')
    final_routes = final_routes.sort_values(by=['Pair_Total_Value', 'Undirected_Pair_ID'], ascending=[False, True])

    # 清理临时列
    final_routes.drop(columns=['Undirected_Pair_ID', 'Pair_Total_Value'], inplace=True, errors='ignore')
    remaining_routes.drop(columns=['Undirected_Pair_ID'], inplace=True, errors='ignore')

    # --- 核心修改结束 ---

    print(f"最终筛选出 {len(final_routes)} 条有向航线 (对应 {len(top_n_pair_ids)} 个无向对)")
    print(f"剩余 {len(remaining_routes)} 条有向航线归入 Other")

    # 6. 添加辅助信息 (Time_Span) - 保持原有逻辑
    if 'Min_YearMonth' in final_routes.columns and 'Max_YearMonth' in final_routes.columns:
        # 转换时间格式
        try:
            final_routes['Min_YearMonth'] = pd.to_datetime(final_routes['Min_YearMonth']).dt.strftime('%Y-%m')
            final_routes['Max_YearMonth'] = pd.to_datetime(final_routes['Max_YearMonth']).dt.strftime('%Y-%m')
            final_routes['Time_Span'] = final_routes['Min_YearMonth'].astype(str) + " to " + final_routes[
                'Max_YearMonth'].astype(str)
        except Exception as e:
            print(f"时间格式转换警告: {e}")

    return final_routes.reset_index(drop=True), remaining_routes.reset_index(drop=True)