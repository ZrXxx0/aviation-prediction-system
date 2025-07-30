## `data_utils` 模块功能概览

该模块主要作用是：

- 清洗原始数据（CSV、Excel）
- 提取机场三字码信息
- 构建 IATA 到城市/省份/机场的映射
- 将清洗后的航线数据批量导入到数据库中

------

## 各脚本功能逐个解释：

### `extract_iata_codes.py`

**功能**：从航线数据中提取所有唯一的机场三字码（IATA 码）

**使用流程**：

1. 加载 `final_data_0729.csv` 文件，提取 `Origin` 和 `Destination` 两列
2. 获取所有不重复的三字码
3. 保存为 `extracted_iata_codes.txt`

```python
iata_codes = set(df["Origin"].dropna().unique()).union(df["Destination"].dropna().unique())
```

 输出：`extracted_iata_codes.txt`

------

### `generate_iata_city_map.py`

**功能**：从 Excel 文件中提取机场信息（城市、机场名、省份），构建成映射 JSON 文件

**输入**：如 `中国机场信息.xlsx`（你之前上传的图中可见）

**输出**：`iata_city_airport_mapping.json`

**核心内容示例**：

```json
{
  "PEK": {"city": "北京", "province": "北京", "airport": "首都国际机场"},
  "PVG": {"city": "上海", "province": "上海", "airport": "浦东机场"},
}
```

 提供给 Django 视图函数做三字码 → 城市、机场名、省份 的转换。

------

### `iata_city_airport_mapping.json`

**内容**：三字码与城市、机场名、省份的静态映射字典

**用途**：

- 在后端 API 中，通过 `get_city_name` / `get_city_airport` 等函数查找
- 可用于前端展示“从哪里飞到哪里”时显示中文

------

### `import_routes.py`（最早版）

**功能**：将 CSV 数据导入 `RouteMonthlyStat` 模型

- 将每一行数据手动处理成 model 实例
- 不带批量优化、不跳过重复项
- 属于原型版本

🟡 不推荐使用（已被更优的 `import_routes2.py` / `import_routes3.py` 替代）

------

### `import_routes2.py`

- #### 🔧 主要功能

  - 分块读取大型 CSV 文件（默认每次 5000 行）
  - 解析年月字段为 `year` 和 `month`
  - 将数据构造为 `RouteMonthlyStat` 实例
  - 使用 `bulk_create` 批量写入数据库，提高导入效率

  #### 核心函数

  ```python
  def import_csv_in_chunks(csv_path, chunk_size=5000):
  ```

  - **读取 CSV 分块处理**，适合大数据量导入
  - 对每一行：
    - 解析 `YearMonth`，提取 `year` 和 `month`
    - 提取航线三字码（`Origin`, `Destination`）
    - 解析乘客量、座位数、航班数
  - **异常处理**：
    - 如果某一行解析失败，则记录为 `failed_rows`
    - 最终将失败的数据导出为 `failed_imports.csv`
    - 然后可以把文件地址改为 `failed_imports.csv`重新运行

------

### `import_routes3.py`

#### 在import_routes2之上改进

- 添加了**去重机制**，避免重复插入已存在的数据（通过主键组合）
- 删除 CSV 中的重复行，清洗数据更彻底
- 分批 `bulk_create` 写入数据库，提高效率

------

## 脚本调用关系（执行顺序建议）：

1️⃣ `extract_iata_codes.py`
 → 提取唯一机场码，用于构建映射或校验数据一致性

2️⃣ `generate_iata_city_map.py`
 → 从机场信息表生成 JSON 映射（供 API 使用）

3️⃣ `import_routes3.py`**（只用这个函数就行）**
 → 将主数据导入数据库，供接口查询

