import pandas as pd
import json
import os

# 获得机场名和三字码映射
# === 配置文件路径 ===
FILE_PATH = "D:\desk\Airlinepredict\中国机场代码.xlsx" # 替换为你的路径
OUTPUT_JSON = "iata_city_airport_mapping.json"

# === 读取 Excel 文件 ===
try:
    df = pd.read_excel(FILE_PATH, usecols=["服务地区", "三字码", "中文名称", "省份"], engine="openpyxl")
except Exception as e:
    print(f"❌ 文件读取失败: {e}")
    exit()

# === 去除空值和重复 ===
df = df.dropna(subset=["三字码"]).drop_duplicates(subset=["三字码"])

# === 构建映射 ===
mapping = {}
failures = []

for _, row in df.iterrows():
    code = row["三字码"].strip()
    city = row["服务地区"]
    airport = row["中文名称"]
    province = row["省份"]

    if pd.isna(city) or pd.isna(airport) or pd.isna(province):
        failures.append(code)
        continue

    mapping[code] = {
        "city": str(city).strip(),
        "airport": str(airport).strip(),
        "province": str(province).strip()
    }

# === 保存结果 ===
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

# === 日志输出 ===
print(f"✅ 映射共生成 {len(mapping)} 条记录，已保存为 {OUTPUT_JSON}")
if failures:
    print(f"⚠️ 以下 {len(failures)} 个三字码因缺少信息未被记录：")
    print(", ".join(failures))
