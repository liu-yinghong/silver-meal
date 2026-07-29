# 银龄放心单 - 适老点餐 Demo

> 帮助恢复期独居老人安全、低负担地完成一顿饭。

## 项目简介

银龄放心单是一个浏览器网页型适老点餐 Demo，支持老人通过语音/文字输入需求，系统推荐三份餐食，家属设置规则授权，模拟下单与送达，老人确认收餐，异常时才提醒家属。

## 技术栈

- **后端**: FastAPI + Pydantic
- **前端**: 原生 HTML/CSS/JS（适老化大字体设计）
- **数据**: JSON 模拟数据（后期可替换为淘宝 API）
- **部署**: uvicorn 本地启动

## 架构说明

`
app/
├── main.py              # FastAPI 入口
├── adapters/            # 适配层（Demo Web API / 后期淘宝小程序）
│   └── web_api.py
├── core/                # 业务逻辑（平台无关）
│   ├── meal_service.py  # 餐食筛选
│   ├── order_service.py # 订单状态机
│   ├── rule_engine.py   # 家属规则判断
│   └── llm_service.py   # 大模型结构化提取
├── repositories/        # 数据层
│   ├── base.py          # 抽象接口
│   └── mock_repo.py     # 模拟数据实现
└── schemas/             # Pydantic 模型（接口契约）
    ├── meal.py
    ├── order.py
    └── family.py

frontend/
├── elder/               # 老人端页面
└── family/              # 家属端页面

data/
└── meals.json           # 模拟餐食数据
`

## 一键启动

### 1. 安装依赖

`ash
pip install -r requirements.txt
`

### 2. 启动后端服务

`ash
uvicorn app.main:app --reload --port 8000
`

### 3. 打开页面

- **老人端**: 直接在浏览器打开 rontend/elder/index.html
- **家属端**: 直接在浏览器打开 rontend/family/index.html
- **API 文档**: 访问 http://localhost:8000/docs

## 接口契约

启动服务后访问 http://localhost:8000/docs 查看完整的 Swagger API 文档。

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/meals/recommend | POST | 老人输入需求，返回三份推荐 |
| /api/orders | POST | 创建订单 |
| /api/orders/{id} | GET | 查询订单状态 |
| /api/orders/{id}/advance | POST | 推进订单状态（模拟制作/配送） |
| /api/orders/confirm | POST | 老人确认收餐 |
| /api/family/settings | POST | 家属设置规则 |
| /api/family/{id}/orders | GET | 家属查看老人订单状态 |
| /api/family/contact | POST | 家属联系老人（模拟） |

## 后期接入淘宝

- `adapters/` 下新增 `taobao_miniapp.py`（小程序接口适配）
- `repositories/` 下新增 `taobao_repo.py`（调用淘宝开放平台 API）
- `core/` 业务逻辑层无需修改

## 团队成员

- **刘应鸿** - 技术负责人 / 全端整合
- **刘勇波** - 老人端与语音交互负责人
- **张林** - 数据、订单状态与测试负责人
- **组长** - 产品负责人 / 项目经理 / 路演负责人

## 执行红线

1. 不做真实平台接入（所有订单标注为模拟）
2. 不做独立骑手端
3. 主流程未通前不做语音和美化
4. 8月8日后不加功能
5. 没有证据就不算完成