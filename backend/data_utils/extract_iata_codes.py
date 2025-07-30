import pandas as pd
# 获取csv文件中机场的三字码
# 文件路径（换成你自己的路径）
file_path = "D:\\desk\\Airlinepredict\\final_data_0729.csv" # 替换为实际 CSV 文件路径

# 读取文件
df = pd.read_csv(file_path, usecols=["Origin", "Destination"])

# 获取 Origin 和 Destination 中唯一的三字码
iata_codes = set(df["Origin"].dropna().unique()).union(df["Destination"].dropna().unique())

# 保存到 txt 文件
with open("extracted_iata_codes.txt", "w", encoding="utf-8") as f:
    for code in sorted(iata_codes):
        f.write(code + "\n")

print(f"✅ 提取了 {len(iata_codes)} 个唯一三字码，已保存到 extracted_iata_codes.txt")


origin_iata_codes = set(df["Origin"].dropna().unique())
# 输出或保存
print(f"✈️ Origin 中共提取 {len(origin_iata_codes)} 个唯一三字码")

# 提取 Destination 列中唯一三字码
destination_iata_codes = set(df["Destination"].dropna().unique())

# 输出基本信息
print(f"🛬 Destination 中共提取 {len(destination_iata_codes)} 个唯一三字码")

# 合并两个集合，去重
iata_codes2 = origin_iata_codes.union(destination_iata_codes)

# 输出信息
print(f"✅ 提取了 {len(iata_codes2)} 个唯一三字码")