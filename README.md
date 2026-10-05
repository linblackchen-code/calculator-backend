# 算间后端

FastAPI + Python Decimal + SQLite。接收表达式，在后端校验、解析和计算；成功后保存记录，提供历史查询和指定删除接口。

## 环境与安装

Python 3.10+，建议 Python 3.13。在本仓库目录执行：

```bash
python -m venv .venv
# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Linux/macOS 使用 `.venv/bin/python` 替换上述解释器路径。

接口文档：<http://127.0.0.1:8000/docs>。

## 配置与数据库初始化

配置通过启动进程的环境变量读取；本后端不会自动加载 `.env`。根目录的 `.env` 仅由 Docker Compose 读取。

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `DATABASE_PATH` | 仓库内 `data/calculator.db` | SQLite 数据库文件路径 |
| `CORS_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | 允许的前端 origin，以逗号分隔 |

首次启动自动创建数据库目录与 `calculation_history` 表，无需另装数据库。表字段为 `id`、`expression`、`result`、`created_at`、`is_favorite`。旧版表在启动时自动增加默认未收藏的字段，保留已有记录。运算结果以十进制字符串保存；时间为带 UTC 时区的 ISO 8601 字符串。

前端须通过 HTTP 调用 API。跨域开发时，配置的 origin 必须包含正确的协议、主机和端口。

## 接口

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | `/api/health` | 检查服务和数据库 |
| POST | `/api/calculate` | 计算并保存记录，成功返回 201 |
| GET | `/api/history?page=1&limit=10&search=` | 历史倒序、搜索和分页 |
| GET | `/api/history/export?search=&favorites_only=false` | 导出全部匹配记录的 CSV，不分页 |
| PATCH | `/api/history/{id}/favorite` | 设置收藏状态；请求 `{"is_favorite": true}` 或 false |
| DELETE | `/api/history/{id}` | 删除指定记录；不存在时返回 404 |

计算请求：

```json
{"expression": "(1+2)*3"}
```

成功响应示例（ID 和时间以实际值为准）：

```json
{"success": true, "id": 1, "expression": "(1+2)*3", "result": "9", "created_at": "2026-10-05T00:00:00+00:00", "is_favorite": false}
```

错误响应：`{"success": false, "message": "除数不能为 0"}`，返回 400。错误参数返回 422，数据库不可用返回 503。成功计算必须完成数据库写入；非法表达式不生成历史。前端不能提交 `result` 字段。

历史查询也接受 `favorites_only=true`，与搜索条件取交集。CSV 使用 UTF-8 BOM、标准 CSV 引号及 attachment 响应；表达式以 `+` 或 `-` 等公式前缀开头时加单引号，避免表格软件把原表达式当公式计算。CSV 时间字段明确使用 UTC。收藏标记使用严格布尔值，重复设置同一状态不会反转状态。

## 运算规则

- 支持 `+ - * /`、`× ÷`、括号、小数和一元正负号。
- 使用自编递归下降解析器，不调用 `eval`、`exec` 或代码编译方法。
- 表达式最多 1024 字符，单个数字最多 50 位数字，嵌套最多 64 层。
- Decimal 以 50 位有效数字进行运算，采用默认 ROUND_HALF_EVEN 舍入；循环小数按此精度返回。
- 不支持幂、科学计数法、函数或隐式乘法。运算符必须显式输入。
- 历史为本应用共享记录，未实现用户登录和独立历史。

## 测试

```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用临时 SQLite 文件，覆盖四则运算、复合表达式、小数、正负号、异常、持久化、删除、分页搜索、参数校验和 CORS。

新增测试覆盖旧库升级、收藏持久化与筛选、PATCH 跨域，以及 CSV 的中文编码、跨页导出、过滤和空结果。

## Docker

`Dockerfile` 提供非 root 运行镜像。数据库路径为 `/data/calculator.db`，应挂载持久卷。使用完整项目的 Compose 配置可同时部署前后端和数据卷。

本仓库也包含独立的 [部署配置与说明](deployment/README.md)。将前端下载到同级 `calculator_frontend` 后，在 `deployment` 目录启动 Compose 即可组合运行两个仓库。系统设计见 [架构说明](docs/ARCHITECTURE.md)。
