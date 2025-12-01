# 预测更新守护进程与API使用说明

## 目录
1. [守护进程启动说明](#守护进程启动说明)
2. [触发更新API使用说明](#触发更新api使用说明)

---

## 守护进程启动说明

### 概述

`run_forecast_daemon.py` 是一个Django管理命令，作为守护进程运行，用于监听数据库中的 `ForecastUpdateLog` 表，自动执行预测更新任务。

### 功能特点

- 自动监听数据库中的预测更新任务
- 每10秒轮询一次数据库，检查是否有待执行的任务
- 自动执行 `update_forecasts` 命令
- 支持任务失败自动重试（最多重试1次）
- 支持超时检测（48小时超时）

### 启动命令

#### 基本语法

```bash
python manage.py run_forecast_daemon [参数]
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top_n` | int | 500 | 指定每次更新任务运行前多少条航线 |
| `--max_workers` | int | None | 并行进程数（如果不指定，将使用 `update_forecasts` 命令的默认值） |

#### 启动示例

**示例1：使用默认配置启动**

```bash
python manage.py run_forecast_daemon
```

这将使用默认的 `top_n=500`，其他参数使用 `update_forecasts` 命令的默认值。

**示例2：指定 top_n 和 max_workers**

```bash
python manage.py run_forecast_daemon --top_n 5 --max_workers 8
```

### 运行状态

启动成功后，守护进程会显示：

```
=== 预测任务守护进程已启动 ===
=== 当前运行配置: [Top n] (Ctrl+C 停止) ===
```

### 停止守护进程

使用 `Ctrl+C` 可以安全停止守护进程。

### 注意事项

1. **守护进程需要持续运行**：确保守护进程在服务器上持续运行，可以使用 `nohup`、`screen` 或 `systemd` 等服务管理工具。

2. **数据库连接**：确保数据库连接正常，守护进程需要访问 `ForecastUpdateLog` 表。

3. **任务状态**：
   - `status=0`: 待执行（Pending）
   - `status=1`: 运行中（Running）
   - `status=2`: 成功（Success）
   - `status=3`: 失败（Failed）

4. **生产环境建议**：在生产环境中，建议使用进程管理工具（如 `supervisor` 或 `systemd`）来管理守护进程，确保其自动重启和日志记录。

---

## 触发更新API使用说明

### 概述

`trigger_update_forecast` 是一个HTTP API接口，用于触发预测更新任务。该接口会检查当前是否有正在运行的任务，如果没有或任务已超时/失败，则创建新的更新任务。

### API端点

```
POST /predict/forecast/update_topn/
```

### 请求方式

- **方法**: `POST`
- **Content-Type**: `application/json`（可选，接口不强制要求请求体）

### 功能逻辑

1. **检查运行状态**：检查数据库中是否有正在运行的任务（`status=0` 或 `status=1`）
2. **超时检测**：如果任务运行时间超过48小时，视为死锁，允许创建新任务
3. **创建任务**：如果系统空闲或任务失败/超时，创建新的更新任务（`status=0`）
4. **返回结果**：返回任务状态和相关信息

### 响应格式

#### 成功响应（任务已启动）

**HTTP状态码**: `200 OK`

```json
{
    "code": 200,
    "status": "started",
    "message": "更新请求已提交，系统开始计算。",
    "data": {
        "estimated_time": "约24小时",
        "last_success_date": "2024-01-15 14:30",
        "note": "在此期间，系统将展示上一次成功的预测数据。"
    }
}
```

**字段说明**：
- `code`: 响应代码，200表示成功
- `status`: 任务状态，`"started"` 表示任务已创建
- `message`: 提示信息
- `data.estimated_time`: 预计完成时间
- `data.last_success_date`: 上一次成功更新的时间（格式：`YYYY-MM-DD HH:MM`）
- `data.note`: 附加说明

#### 拒绝响应（任务正在运行）

**HTTP状态码**: `200 OK`（注意：虽然任务被拒绝，但HTTP状态码仍为200）

```json
{
    "code": 400,
    "status": "running",
    "message": "系统正在进行预测更新，请耐心等待。",
    "data": {
        "start_time": "2024-01-15 10:00"
    }
}
```

**字段说明**：
- `code`: 响应代码，400表示请求被拒绝
- `status`: 任务状态，`"running"` 表示任务正在运行
- `message`: 提示信息
- `data.start_time`: 当前任务开始时间（格式：`YYYY-MM-DD HH:MM`）

### 使用示例

#### 前端调用示例（JavaScript/Axios）

```javascript
// 使用 Axios
import axios from 'axios';

async function triggerForecastUpdate() {
    try {
        const response = await axios.post('/predict/forecast/update_topn/');
        
        if (response.data.code === 200) {
            console.log('更新任务已启动');
            console.log('上次成功时间:', response.data.data.last_success_date);
            // 显示成功提示
            alert('预测更新任务已启动，预计需要约24小时完成。');
        } else {
            console.log('任务正在运行中');
            console.log('开始时间:', response.data.data.start_time);
            // 显示等待提示
            alert('系统正在进行预测更新，请耐心等待。');
        }
    } catch (error) {
        console.error('请求失败:', error);
        alert('请求失败，请稍后重试。');
    }
}
```

#### 后端调用示例（Python/Requests）

```python
import requests

def trigger_forecast_update():
    """
    触发预测更新任务
    """
    url = 'http://your-domain.com/predict/forecast/update_topn/'
    
    try:
        response = requests.post(url)
        response.raise_for_status()
        data = response.json()
        
        if data['code'] == 200:
            print(f"更新任务已启动")
            print(f"上次成功时间: {data['data']['last_success_date']}")
            return True
        else:
            print(f"任务正在运行中，开始时间: {data['data']['start_time']}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return False
```

#### cURL 示例

```bash
# 触发更新
curl -X POST http://localhost:8000/predict/forecast/update_topn/

# 带详细输出的示例
curl -X POST http://localhost:8000/predict/forecast/update_topn/ \
  -H "Content-Type: application/json" \
  -v
```

### 工作流程

```
前端/后端调用API
    ↓
检查 ForecastUpdateLog 表
    ↓
是否有正在运行的任务？
    ├─ 是 → 检查是否超时（48小时）
    │   ├─ 未超时 → 返回 "running" 状态
    │   └─ 已超时 → 标记为失败，创建新任务
    └─ 否 → 创建新任务（status=0）
        ↓
守护进程检测到新任务
    ↓
执行 update_forecasts 命令
    ↓
更新任务状态（成功/失败）
```

### 注意事项

1. **任务执行时间**：预测更新任务可能需要较长时间（约24小时），在此期间系统会展示上一次成功的预测数据。

2. **超时机制**：如果任务运行超过48小时仍未完成，系统会将其视为死锁，允许创建新任务。

3. **守护进程要求**：**必须确保守护进程 `run_forecast_daemon` 正在运行**，否则创建的任务不会被自动执行。

4. **并发控制**：API会自动检查是否有正在运行的任务，防止重复执行。

5. **错误处理**：建议在前端和后端调用时都添加适当的错误处理和用户提示。

6. **状态查询**：如果需要查询任务状态，可以查询 `ForecastUpdateLog` 表中的最新记录。

### 与守护进程的配合

1. **启动守护进程**：
   ```bash
   python manage.py run_forecast_daemon --top_n 1000 --max_workers 4
   ```

2. **通过API触发任务**：
   ```bash
   curl -X POST http://localhost:8000/predict/forecast/update_topn/
   ```

3. **守护进程自动执行**：守护进程检测到新任务后，会自动执行 `update_forecasts` 命令。

4. **任务完成**：任务完成后，状态更新为成功或失败，可以再次通过API触发新任务。

---

## 常见问题

### Q1: 守护进程启动后没有执行任务？

**A**: 检查以下几点：
- 确认数据库中是否有 `status=0` 的任务记录
- 检查守护进程的日志输出
- 确认 `update_forecasts` 命令是否正常工作

### Q2: API返回 "running" 状态，但任务已经完成？

**A**: 检查任务的实际状态，可能是任务状态未正确更新。可以手动检查 `ForecastUpdateLog` 表。

### Q3: 如何查看任务执行日志？

**A**: 任务执行日志存储在 `ForecastUpdateLog` 表的 `log_message` 字段中。

### Q4: 守护进程意外停止怎么办？

**A**: 使用进程管理工具（如 `supervisor`）确保守护进程自动重启。如果任务正在运行中，守护进程重启后不会影响正在执行的任务。

