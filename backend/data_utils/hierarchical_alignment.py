import pandas as pd
import numpy as np
import re
from sklearn.linear_model import LinearRegression
import warnings

# 解析 'YYYY-Qn' → 用该季度末月的1号 (3/6/9/12-01)
_Q_PAT = re.compile(r'^(\d{4})-Q([1-4])$')
def _q_to_ts(s):
    m = _Q_PAT.match(str(s))
    if m:
        y = int(m.group(1)); q = int(m.group(2))
        return pd.Timestamp(year=y, month=q * 3, day=1)
    return pd.to_datetime(s, errors='coerce')

def _format_quarter_label(ts: pd.Timestamp) -> str:
    if pd.isna(ts): return None
    return f"{ts.year}-Q{(ts.month - 1)//3 + 1}"



# 线性对齐
def linear_reconcile_monthly_to_quarterly(result_monthly, result_quarterly):
    """
    将月度预测按季度总量线性校准，返回含 Predicted_Reconciled 的月度表。
    只调整 Set=='Future'，历史不动。
    需要列：YearMonth, Predicted, Set
    """
    rm = result_monthly.copy()
    rq = result_quarterly.copy()

    # 规范时间
    rm['YearMonth'] = pd.to_datetime(rm['YearMonth'], errors='coerce', format='%Y-%m')
    rq['YearMonth'] = rq['YearMonth'].apply(_q_to_ts)

    # 生成季度键
    rm['quarter'] = rm['YearMonth'].dt.to_period('Q').dt.to_timestamp()
    rq['quarter'] = rq['YearMonth'].dt.to_period('Q').dt.to_timestamp()

    # 聚合
    monthly_q = rm.groupby('quarter', as_index=False)['Predicted'].sum().rename(columns={'Predicted': 'monthly_sum'})
    quarterly_q = rq.groupby('quarter', as_index=False)['Predicted'].sum().rename(columns={'Predicted': 'quarterly_sum'})

    merged_q = pd.merge(monthly_q, quarterly_q, on='quarter', how='inner')
    if merged_q.empty:
        # 无公共季度 -> 不调整
        rm['Predicted_Reconciled'] = rm['Predicted']
        return rm

    # 线性回归校准
    reg = LinearRegression().fit(merged_q[['monthly_sum']], merged_q['quarterly_sum'])

    monthly_q['adjusted'] = reg.predict(monthly_q[['monthly_sum']]).astype(float)
    rm = pd.merge(rm, monthly_q[['quarter', 'monthly_sum', 'adjusted']], on='quarter', how='left')

    # 防零/NaN
    rm['adjust_ratio'] = rm['adjusted'] / rm['monthly_sum']
    rm['adjust_ratio'].replace([np.inf, -np.inf], 1.0, inplace=True)
    rm['adjust_ratio'].fillna(1.0, inplace=True)

    rm['Predicted_Reconciled'] = rm.apply(
        lambda row: row['Predicted'] * row['adjust_ratio'] if row.get('Set') == 'Future' else row['Predicted'], axis=1
    )
    return rm



# MinT（Minimum Trace）最优层级对齐（OLS）
def mint_reconcile_monthly_to_quarterly(result_monthly, result_quarterly, W=None):
    """
    MinT-OLS 对齐：返回含 Predicted_Reconciled 的月度表；仅调整 Set in {'Future','Test'}
    需要列：YearMonth, Predicted, Set（月度）；YearMonth, Predicted（季度，YYYY-Qn）
    """
    rm = result_monthly.copy()
    rq = result_quarterly.copy()

    rm['YearMonth'] = pd.to_datetime(rm['YearMonth'], errors='coerce', format='%Y-%m')
    rq['YearMonth'] = rq['YearMonth'].apply(_q_to_ts)

    rm['quarter'] = rm['YearMonth'].dt.to_period('Q').dt.to_timestamp()
    rq['quarter'] = rq['YearMonth'].dt.to_period('Q').dt.to_timestamp()

    valid_quarters = rq['quarter'].dropna().unique()
    mf = rm[rm['quarter'].isin(valid_quarters)].copy()
    if mf.empty or rq.empty:
        rm['Predicted_Reconciled'] = rm['Predicted']
        return rm

    mf['Predicted'] = pd.to_numeric(mf['Predicted'], errors='coerce').fillna(0.0)
    rq_agg = rq.groupby('quarter', as_index=False)['Predicted'].sum().rename(columns={'Predicted': 'q_total'})

    quarters = rq_agg['quarter'].to_numpy()
    q_index = {q: i for i, q in enumerate(quarters)}
    n_q, n_m = len(quarters), len(mf)

    S = np.zeros((n_q, n_m), dtype=float)
    for j, q in enumerate(mf['quarter']):
        i = q_index.get(q, None)
        if i is not None:
            S[i, j] = 1.0

    y_m = mf['Predicted'].to_numpy(dtype=float)
    y_q = rq_agg['q_total'].to_numpy(dtype=float)

    if W is None:
        W = np.eye(n_m, dtype=float)

    SWS = S @ W @ S.T
    SWS_inv = np.linalg.pinv(SWS)
    G = W @ S.T @ SWS_inv
    y_rec = y_m + G @ (y_q - S @ y_m)

    mask = mf['Set'].isin(['Future', 'Test']).to_numpy()
    mf['Predicted_Reconciled'] = mf['Predicted']
    mf.loc[mask, 'Predicted_Reconciled'] = y_rec[mask]

    rm = rm.merge(mf[['YearMonth', 'Predicted_Reconciled']], on='YearMonth', how='left')
    rm['Predicted_Reconciled'] = rm['Predicted_Reconciled'].fillna(rm['Predicted'])
    return rm
