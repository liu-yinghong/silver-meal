# 饭心 · 银龄放心单

> **一顿饭，放两个人的心**
>
> 帮助恢复期独居老人安全、低负担地完成一顿饭，让家人安心。

## 品牌介绍

| 项目 | 内容 |
|------|------|
| **产品品牌** | 饭心 |
| **项目名称** | 银龄放心单 |
| **品牌标语** | 一顿饭，放两个人的心 |
| **品牌调性** | 温暖、安心、可信赖 — 暖橙色调，适老设计 |

## 项目简介

银龄放心单是一个**适老点餐 项目（Demo）**，目标用户为恢复期独居老人及其家属。老人可通过日常语言输入需求，系统智能推荐三份适合的餐食，家属在另一端设置饮食规则（预算、偏好、禁止食材），下单后模拟完整的外卖流程（制作→配送→送达→确认收餐）。异常情况（如送达后老人长时间未确认）会自动提醒家属。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI (Python 3.10+) | 异步高性能 Web 框架 |
| **数据验证** | Pydantic v2 | 接口契约定义与校验 |
| **前端** | 原生 HTML/CSS/JS（适老化设计，本仓库 `frontend/`） | 由后端静态托管 |
| **数据层** | JSON 内存模拟 + Repository 模式 | 可替换为任意数据库 |
| **部署** | uvicorn 本地启动 | 一键启动 |

## 架构设计

### 前后端一体化（后端托管前端）

```
┌────────────────────────────┐   HTTP / JSON   ┌──────────────────┐
│   前端页面（本仓库 frontend/）│  ────────────►  │   FastAPI 后端    │
│  /elder/  /family/         │                │  localhost:8000   │
└────────────────────────────┘  ◄────────────  │   /api/...        │
                                               └──────────────────┘
```

前端页面存放在 `frontend/`（`elder/` 老人端、`family/` 家属端），由后端通过静态文件服务托管于 `/elder/`、`/family/`。前端通过 `fetch` 调用后端接口，接口契约见 **`API契约.md`**，对接方法见 **`前后端连接指南.md`**。

### 后端分层架构

```
silver-meal/
├── app/
│   ├── main.py              # FastAPI 入口 & CORS 配置
│   ├── adapters/            # 适配层 —— Web API 接口
│   │   └── web_api.py       #   全部 /api/ 路由
│   ├── core/                # 业务逻辑层 —— 纯 Python，零框架依赖
│   │   ├── meal_service.py  #   餐食推荐服务
│   │   ├── order_service.py #   订单状态机
│   │   ├── rule_engine.py   #   家属规则校验引擎
│   │   ├── recommendation.py#   智能推荐评分引擎
│   │   ├── llm_service.py   #   大模型结构化提取（remote/local 降级）
│   │   └── exceptions.py    #   业务异常定义
│   ├── repositories/        # 数据访问层 —— 抽象接口 + 实现
│   │   ├── base.py          #   抽象接口（Protocol）
│   │   └── mock_repo.py     #   模拟数据实现
│   └── schemas/             # 接口契约（Pydantic 模型）
│       ├── meal.py          #   餐食相关
│       ├── order.py         #   订单相关
│       ├── family.py        #   家属规则相关
│       └── message.py       #   留言相关
├── frontend/
│   ├── elder/               # 老人端页面（html + css + js）
│   │   ├── index.html
│   │   ├── css/style.css
│   │   └── js/api.js, app.js
│   └── family/              # 家属端页面（html + css + js）
│       ├── index.html
│       ├── css/style.css
│       └── js/api.js, app.js
├── data/
│   └── meals.json           # 30 道适老餐食模拟数据
├── tests/                   # 后端测试（pytest）
├── requirements.txt         # Python 依赖
├── API契约.md               # ★ 前后端对接接口契约（标准版）
├── 前后端连接指南.md         # ★ 前后端对接方法
└── _start.bat              # Windows 一键启动脚本
```

### 核心设计原则

1. **依赖倒置**：`core/` 业务逻辑层依赖 `repositories/` 的抽象接口（Protocol），而非具体实现
2. **适配器模式**：`adapters/` 层隔离 Web 框架，更换 API 风格（如淘宝小程序）只需新增适配器
3. **状态机**：订单状态流转在 `order_service.py` 中统一管理，状态路径清晰可控
4. **适老设计**：前端大字体、高对比度、暖色调，符合老年人使用习惯

## 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/meals/recommend` | POST | 老人输入需求，返回三份推荐餐食及理由 |
| `/api/orders` | POST | 创建订单 |
| `/api/orders/{id}` | GET | 查询订单状态 |
| `/api/orders/{id}/advance` | POST | 推进订单状态（模拟制作/配送） |
| `/api/orders/{id}/deliver` | POST | 一键送达 |
| `/api/orders/{id}/cancel` | POST | 取消订单 |
| `/api/orders/{id}/timeout` | POST | 标记订单为送达后超时未确认 |
| `/api/orders/confirm` | POST | 老人确认收餐 |
| `/api/family/settings` | POST | 家属设置用餐规则 |
| `/api/family/{id}/rules` | GET | 获取家属规则 |
| `/api/family/{id}/orders` | GET | 家属查看老人订单列表 |
| `/api/family/contact` | POST | 联系老人（模拟电话/留言） |
| `/api/messages` | POST | 发送留言 |
| `/api/messages/{elder_id}` | GET | 获取老人留言列表 |
| `/api/messages/{elder_id}/unread` | GET | 获取未读留言 |
| `/api/messages/{id}/read` | POST | 标记留言已读 |
| `/api/demo/reset` | POST | 一键重置演示（清空订单/规则/留言） |

启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看完整 Swagger 文档。

## AI 意图解析（真实大模型，可选）

推荐链路中的「理解老人需求」这一步默认调用**阿里云百炼（DashScope）qwen3.7-max**，将自然语言解析为结构化需求（口味偏好 / 价格区间 / 食材关键词），推荐理由仍由本地规则引擎生成，保证可回溯与断网可用。

- **模型：** `qwen3.7-max`（OpenAI 兼容端点 `https://dashscope.aliyuncs.com/compatible-mode/v1`）
- **API Key：** 读取本机用户环境变量 `OPENAI_API_KEY`，无需写入代码
- **超时与降级：** 单次调用超时 20 秒、不重试；任何失败（无 Key / 断网 / 超时 / 解析失败）自动切回本地关键词解析，绝不阻断主链路
- **响应标记：** `/api/meals/recommend` 返回 `ai_mode`：`remote` 表示真实大模型解析，`local` 表示本地降级；老人端会据此显示「正在用本地餐品规则继续」
- **配置：** 可通过 `LLMService(api_key, model, base_url, timeout)` 构造参数覆盖，测试中可用 `use_remote=False` 强制本地

## 一键启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

或 Windows 下双击 `_start.bat`。

### 3. 打开页面

| 资源 | 地址 |
|------|------|
| **老人端** | [http://localhost:8000/elder/](http://localhost:8000/elder/) |
| **家属端** | [http://localhost:8000/family/](http://localhost:8000/family/) |
| **Swagger 文档** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **健康检查** | [http://localhost:8000/health](http://localhost:8000/health) |

> 前端页面由后端静态服务托管于 `/elder/`、`/family/`。接口契约见 `API契约.md`，对接方法见 `前后端连接指南.md`。

### 运行测试

```bash
pip install -r requirements-dev.txt   # pytest + httpx
python -m pytest -q                   # 覆盖 LLM 降级 / 推荐过滤 / 订单状态机 / API 冒烟
```

测试固定用本地意图解析（`use_remote=False`），不依赖网络与大模型。

## 演示重置与降级

- **重置**：`POST /api/demo/reset` 一键清空订单、规则、留言并刷新首页；可直接 `curl -X POST http://localhost:8000/api/demo/reset`。
- **AI 降级**：未配置 `OPENAI_API_KEY`、断网或超时时，推荐自动切回本地规则，接口返回 `ai_mode: "local"`。
- **无合格餐品**：当所有餐品都被家庭规则（预算/禁止食材/饮食偏好）排除时，接口返回 `422 NO_ELIGIBLE_MEAL`，前端应提示老人放宽条件后重试。

## 淘宝生态接入指南

### 适配架构

本项目从架构上已支持淘宝生态接入，核心原则是 **`core/` 业务逻辑层与平台无关**，只需新增适配层：

```
当前（Demo）         后期（淘宝小程序）
┌──────────────┐    ┌──────────────────┐
│  Web API      │    │  淘宝小程序前端   │
│  (adapters/   │    │  (支付宝小程序)   │
│   web_api.py) │    └──────┬───────────┘
└──────┬───────┘           │
       │ HTTP              │ 淘宝开放平台 API
       ▼                   ▼
┌──────────────┐    ┌──────────────────┐
│  core/       │    │  core/           │ ← 无需修改
│  业务逻辑     │    │  业务逻辑         │
└──────┬───────┘    └──────┬───────────┘
       │                   │
       ▼                   ▼
┌──────────────┐    ┌──────────────────┐
│ mock_repo    │    │ taobao_repo      │ ← 新增
│ (JSON 模拟)  │    │ (淘宝开放平台API) │
└──────────────┘    └──────────────────┘
```

### 接入步骤

1. **新增适配器**：在 `app/adapters/` 下创建 `taobao_miniapp.py`，实现淘宝小程序后端适配
2. **新增数据仓库**：在 `app/repositories/` 下创建 `taobao_repo.py`，对接淘宝开放平台 API（商品查询、订单管理等）
3. **前端重写**：使用淘宝小程序（支付宝小程序）框架重写前端页面，调用与 `adapters/` 对应的接口
4. **复用业务逻辑**：`app/core/` 下的所有服务无需修改，直接复用

### Demo 说明

当前 Demo 所有订单、支付、配送、联系入口均标注为**模拟**，不做真实平台接入。

## 团队成员

| 角色 | 姓名 | 职责 |
|------|------|------|
| 产品负责人 / 项目经理 | 施雁庭 | 路演、产品方向 |
| 技术负责人 / 全端整合 | **刘应鸿** | 架构、后端、家属端、整合 |
| 老人端与语音交互 | 刘勇波 | 老人端页面开发 |
| 数据、订单与测试 | 张林 | 数据模型、状态测试 |

## 项目红线

1. ❌ 不做真实平台接入（所有订单标注为模拟）
2. ❌ 不做独立骑手端
3. ❌ 主流程未通前不做语音和美化
4. ❌ 8月8日后不加功能，只修 Bug
5. ✅ 没有证据就不算完成

## 后期规划

- [x] 接入大模型真实 API，提升语音/文字理解精度（阿里云百炼 qwen3.7-max，见上方「AI 意图解析」）
- [x] 重写老人端 / 家属端前端页面（`frontend/elder/`、`frontend/family/`，已接入后端）
- [ ] 淘宝小程序前端适配
- [ ] 对接淘宝开放平台商品与订单 API
- [ ] 适老化语音交互（语音输入 + 语音播报）
- [ ] 多老人管理（家属端同时关注多位老人）
