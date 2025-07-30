## 1、model.py

------

###  `RouteMonthlyStat` 模型解释

#### 作用：

该模型用于记录每条航线在每个月的运营统计数据，包括出发/到达机场、时间（月）、客运量、座位数、航班数量等。

------

### 字段解析

| 字段名                | 类型            | 说明                                       |
| --------------------- | --------------- | ------------------------------------------ |
| `origin_code`         | `CharField`     | 出发机场三字码（如 "SHA"）                 |
| `destination_code`    | `CharField`     | 到达机场三字码（如 "PEK"）                 |
| `year`                | `IntegerField`  | 数据对应的年份（如 2025）                  |
| `month`               | `IntegerField`  | 数据对应的月份（如 7）                     |
| `passenger_volume`    | `FloatField`    | 航线当月总客运量，单位：**万人次**，可为空 |
| `Route_Total_Seats`   | `FloatField`    | 航线当月总运力，单位：**座位数**，可为空   |
| `Route_Total_Flights` | `IntegerField`  | 航线当月总航班数量，单位：**班次**，可为空 |
| `created_at`          | `DateTimeField` | 数据创建时间，自动填充为添加时间           |

###  `Meta` 配置

```python
class Meta:
    unique_together = ("origin_code", "destination_code", "year", "month")
    ordering = ["-year", "-month"]
    verbose_name = "航线月度统计"
    verbose_name_plural = "航线月度统计"
```

- `unique_together`：确保每条航线在同一个年月只存一条记录（即每个月每条航线唯一）
- `ordering`：默认按 `年份倒序`、`月份倒序` 排序（最新数据在前）
- `verbose_name / plural`：设置在 Django Admin 后台的中文显示名

------

###  `__str__` 方法

```python
def __str__(self):
    return f"{self.origin_code} → {self.destination_code} - {self.year}-{self.month:02d}"
```

**作用：**
 定义在管理后台或终端打印对象时的展示格式，如：

```
SHA → PEK - 2025-07
```



## 2、views.py


### 初始化与工具函数部分

------

#### `build_info(iata_code)`

**作用：**
 根据三字码返回机场相关信息字典，包括城市、省份、机场名称。

**参数：**

- `iata_code` (str)：机场三字码

**返回值：**

```python
{
    "code": "PEK",
    "city": "北京",
    "province": "北京",
    "airport": "首都国际机场"
}
```

------

#### `get_codes_by_city(city_name)`

**作用：**
 返回该城市下的所有机场三字码列表，用于数据库查询过滤。

**参数：**

- `city_name` (str)：城市名（如“上海”）

**返回值：**

- `["SHA", "PVG"]` 等三字码列表

------

#### `get_city_name(code)`

**作用：**
 根据机场三字码获取其对应的城市名。

**参数：**

- `code` (str)：机场三字码

**返回值：**

- `"北京"` 或 None

------

#### `get_city_airport(iata_code)`

**作用：**
 根据机场三字码返回 `(城市名, 机场名)` 元组。

**参数：**

- `iata_code` (str)：机场三字码

**返回值：**

- `("北京", "首都国际机场")`
- 若找不到对应信息，则返回 `(iata_code, iata_code)`

------

### 航线图数据接口

------

#### `route_distribution_view(request)`

**接口路径：** `/api/routes/`
 **方法：** GET

**作用：**
 根据传入的月份和可选的城市，返回城市对之间的航班数量分布。

**参数：**

- `year_month` (str, 必填)：格式 `YYYY-MM`
- `city` (str, 可选)：起始城市

**逻辑说明：**

- 如果传了 `city`，则聚合该城市出发、按到达城市统计。
- 如果没有传 `city`，则全国范围内按 `(from, to)` 聚合。

**返回示例：**

```json
[
  {"from": "上海", "to": "北京", "flights": 322},
  {"from": "上海", "to": "广州", "flights": 350}
]
```

------

### 统计卡片接口

------

#### `statistics_summary_view(request)`

**接口路径：** `/api/statistics/summary/`
 **方法：** GET

**作用：**
 统计某月某条航线（或全国）总运力、客运量、航班数。

**参数：**

- `year_month` (str, 必填)：格式 `YYYY-MM`
- `start_city` (str, 可选)：出发城市
- `end_city` (str, 可选)：到达城市

**返回示例：**

```json
{
  "capacity": 1258000,
  "volume": 982000,
  "flights": 1280
}
```

------

### 趋势折线图接口

------

#### `statistics_trend_view(request)`

**接口路径：** `/api/statistics/trend/`
 **方法：** GET

**作用：**
 统计过去 12 个月的运力、客运量和航班数趋势。

**参数：**

- `start_city` (str, 可选)：出发城市
- `end_city` (str, 可选)：到达城市

**返回示例：**

```json
{
  "months": ["2024-08", "2024-09", ..., "2025-07"],
  "capacity": [1258, 1120, ...],
  "volume": [982, 860, ...],
  "flights": [128, 112, ...]
}
```

