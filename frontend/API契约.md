# 饭心·银龄放心单 — API 接口契约（标准版）

> 版本：0.1.0 ｜ 更新日期：2026-07-31
> 本文件是前后端对接的唯一权威接口依据。后端已实现，前端按此文档联调。

---

## 一、通用约定

### Base URL
```
http://localhost:8000
```
后端启动方式：`uvicorn app.main:app --host 0.0.0.0 --port 8000`

### 数据格式
- 所有请求/响应均为 `application/json`（UTF-8）
- 时间字段为 ISO 8601 字符串，如 `2026-07-31T12:00:00.123456`

### 固定参数
| 参数 | 值 | 说明 |
|------|-----|------|
| `elder_id` | `elder_001` | 当前 Demo 固定老人（张奶奶） |
| `family_id` | `family_001` | 当前 Demo 固定家属 |

### 错误码约定
错误响应通过 **HTTP 状态码 + `X-Error-Code` 响应头** 双重标识：

```
HTTP/1.1 422
X-Error-Code: NO_ELIGIBLE_MEAL

{"detail": "没有符合您需求的餐品..."}
```

前端建议统一拦截 `X-Error-Code`，根据错误码做提示。

### 完整错误码表
| 状态码 | X-Error-Code | 触发场景 |
|--------|--------------|----------|
| 404 | `MEAL_NOT_FOUND` | 下单的餐品 ID 不存在 |
| 404 | `ORDER_NOT_FOUND` | 订单 ID 不存在 |
| 409 | `INVALID_ORDER_TRANSITION` | 订单状态机非法转换（详见第三节） |
| 422 | `NO_ELIGIBLE_MEAL` | 推荐无符合规则/输入的餐品 |
| 422 | `EMPTY_MESSAGE` | 留言内容为空 |

---

## 二、接口总览

| # | 方法 | 路径 | 说明 | 归属端 |
|---|------|------|------|--------|
| 1 | POST | `/api/meals/recommend` | 老人输入需求 → 返回推荐餐食 | 老人端 |
| 2 | POST | `/api/orders` | 创建订单 | 老人端 |
| 3 | GET | `/api/orders/{order_id}` | 查询订单状态 | 两端 |
| 4 | POST | `/api/orders/{order_id}/advance` | 推进订单状态（模拟制作/配送） | 老人端 |
| 5 | POST | `/api/orders/{order_id}/deliver` | 一键送达 | 老人端 |
| 6 | POST | `/api/orders/{order_id}/cancel` | 取消订单 | 老人端 |
| 7 | POST | `/api/orders/{order_id}/timeout` | 标记超时未确认 | 家属端 |
| 8 | POST | `/api/orders/confirm` | 老人确认收餐 | 老人端 |
| 9 | POST | `/api/family/settings` | 家属保存用餐规则 | 家属端 |
| 10 | GET | `/api/family/{family_id}/rules` | 获取家属规则 | 家属端 |
| 11 | GET | `/api/family/{family_id}/orders` | 查看老人订单列表 | 家属端 |
| 12 | POST | `/api/family/contact` | 联系老人（模拟电话/留言） | 家属端 |
| 13 | POST | `/api/messages` | 发送留言 | 家属端 |
| 14 | GET | `/api/messages/{elder_id}` | 获取全部留言 | 老人端 |
| 15 | GET | `/api/messages/{elder_id}/unread` | 获取未读留言 | 老人端 |
| 16 | POST | `/api/messages/{message_id}/read` | 标记留言已读 | 老人端 |
| 17 | POST | `/api/demo/reset` | 重置全部演示数据 | 两端调试 |
| 18 | GET | `/health` | 健康检查 | 两端 |

> 交互式文档：启动后访问 `http://localhost:8000/docs`（Swagger UI），可直接调试。

---

## 三、订单状态机（重要）

```
created → paid → preparing → delivering → delivered
                                                    │
                                    ┌───────────────┴───────────────┐
                                    ▼                               ▼
                               confirmed                        unconfirmed_timeout
```

### 合法转换规则
| 当前状态 | 可执行操作 | 结果状态 |
|----------|-----------|----------|
| created / paid / preparing / delivering | `advance` | 下一个状态 |
| delivering | `deliver` | delivered |
| created / paid / preparing / delivering | `cancel` | cancelled |
| delivered（未确认） | `confirm` | confirmed |
| delivered（未确认） | `timeout` | unconfirmed_timeout |
| delivered / confirmed 之后 | `cancel` | **非法 → 409** |
| delivered 之前 | `confirm` | **非法 → 409** |

> 前端建议：根据订单当前状态动态显示可用按钮，避免触发 409。

---

## 四、详细接口定义

### 1. 餐食推荐

**POST** `/api/meals/recommend`

请求：
```json
{
  "text_input": "今天想吃清淡一点，30元以内",
  "family_id": "family_001"
}
```

响应（200）：
```json
{
  "meals": [
    {
      "id": "meal_005",
      "image_id": "meal_005_ui",
      "name": "蔬菜豆腐汤配馒头",
      "description": "清淡蔬菜豆腐汤搭配白面馒头，低脂健康",
      "price": 15.0,
      "image_url": "/elder/images/meal_005_ui.png",
      "dietary_tags": ["low_oil", "low_salt", "soft_food"],
      "calories": 320,
      "eta_minutes": 35
    }
  ],
  "query_summary": "您说：今天想吃清淡一点，30元以内，为您推荐以下餐食（偏好：低油、低盐、软烂易消化）",
  "reasons": ["名称包含\"豆腐\"；符合低油、低盐；价格15元在预算内"],
  "ai_mode": "remote"
}
```

字段说明：
- `meals`：推荐餐食数组（1~3 份），`reasons` 与 `meals` 一一对应
- `ai_mode`：`remote` = 大模型解析，`local` = 本地规则降级（大模型不可用时自动降级）
- `dietary_tags` 枚举：`low_oil`(低油) `low_salt`(低盐) `low_sugar`(低糖) `soft_food`(软烂易消化) `vegetarian`(素食) `high_protein`(高蛋白) `low_carb`(低碳水) `gluten_free`(无麸质) `halal`(清真) `no_pork`(无猪肉) `no_seafood`(无海鲜) `low_purine`(低嘌呤) `none`

错误：
- 422 `NO_ELIGIBLE_MEAL`：无符合餐品，`detail` 含建议放宽的条件

---

### 2. 创建订单

**POST** `/api/orders`

请求：
```json
{
  "meal_id": "meal_001",
  "elder_id": "elder_001",
  "family_id": "family_001"
}
```

响应（200）：
```json
{
  "order_id": "ORD-26BED11A",
  "status": "created",
  "created_at": "2026-07-31T12:00:00.123456",
  "eta_minutes": 35
}
```

> **幂等**：同一老人 + 同一餐品在 active 状态（created~delivering）重复下单，返回同一个 `order_id`，不产生新订单。

错误：404 `MEAL_NOT_FOUND`

---

### 3. 查询订单状态

**GET** `/api/orders/{order_id}`

响应（200）：
```json
{
  "order_id": "ORD-26BED11A",
  "status": "delivered",
  "meal_name": "清蒸鲈鱼套餐",
  "meal_price": 28.0,
  "eta_minutes": 35,
  "updated_at": "2026-07-31T12:30:00.123456",
  "confirmed": false,
  "confirmed_at": null
}
```

错误：404 `ORDER_NOT_FOUND`

---

### 4. 推进订单状态

**POST** `/api/orders/{order_id}/advance`

无请求体。按状态机推进一步，返回与接口 3 相同的订单对象。

---

### 5. 一键送达

**POST** `/api/orders/{order_id}/deliver`

无请求体。将 delivering 状态推进到 delivered，返回订单对象。

---

### 6. 取消订单

**POST** `/api/orders/{order_id}/cancel`

无请求体。仅 created~delivering 状态可取消。返回订单对象（status=cancelled）。

错误：409 `INVALID_ORDER_TRANSITION`（已送达/已确认后不可取消）

---

### 7. 标记超时未确认

**POST** `/api/orders/{order_id}/timeout`

无请求体。将 delivered（未确认）状态标记为 unconfirmed_timeout。返回订单对象。

---

### 8. 确认收餐

**POST** `/api/orders/confirm`

请求：
```json
{
  "order_id": "ORD-26BED11A",
  "action": "confirm"
}
```

响应（200）：
```json
{
  "order_id": "ORD-26BED11A",
  "status": "confirmed",
  "confirmed": true,
  "confirmed_at": "2026-07-31T12:35:00.123456",
  "meal_name": "清蒸鲈鱼套餐",
  "meal_price": 28.0,
  "eta_minutes": 35,
  "updated_at": "2026-07-31T12:35:00.123456"
}
```

错误：409 `INVALID_ORDER_TRANSITION`（送达前确认）；404 `ORDER_NOT_FOUND`

---

### 9. 家属保存规则

**POST** `/api/family/settings`

请求：
```json
{
  "family_id": "family_001",
  "elder_id": "elder_001",
  "rules": {
    "max_price": 35,
    "allowed_dietary": ["low_oil", "low_salt"],
    "blocked_items": ["辣椒", "花生"],
    "notify_on_unconfirm": true,
    "unconfirm_timeout_minutes": 30,
    "notes": "多加米饭、不要辣"
  }
}
```

响应（200）：
```json
{ "status": "ok", "message": "家属规则已保存" }
```

`rules` 字段（FamilyRule）：
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `max_price` | number | 35 | 单餐最高金额（元） |
| `allowed_dietary` | string[] | [] | 允许的饮食偏好（枚举见接口1） |
| `blocked_items` | string[] | [] | 禁止食材关键词 |
| `notify_on_unconfirm` | boolean | true | 超时未确认是否提醒 |
| `unconfirm_timeout_minutes` | number | 30 | 超时分钟数 |
| `notes` | string | "" | 备注 |

---

### 10. 获取家属规则

**GET** `/api/family/{family_id}/rules?elder_id=elder_001`

响应（200）：返回 `rules` 对象（结构同上）。未设置时返回默认值。

---

### 11. 查看老人订单列表

**GET** `/api/family/{family_id}/orders`

响应（200）：订单数组（最新在前）：
```json
[
  {
    "order_id": "ORD-26BED11A",
    "elder_name": "张奶奶",
    "meal_name": "清蒸鲈鱼套餐",
    "meal_price": 28.0,
    "eta_minutes": 35,
    "status": "delivered",
    "confirmed": false,
    "rule_passed": true,
    "rule_detail": "单餐最高35元 | 低油、低盐 | 备注：多加米饭",
    "created_at": "2026-07-31T12:00:00.123456",
    "updated_at": "2026-07-31T12:30:00.123456",
    "confirmed_at": null
  }
]
```

---

### 12. 联系老人（模拟）

**POST** `/api/family/contact`

请求：
```json
{
  "order_id": "latest",
  "family_id": "family_001",
  "contact_type": "call"
}
```

- `order_id`：具体订单 ID，或 `"latest"` 表示该家庭最新订单
- `contact_type`：`call`（电话）或 `message`（留言）

响应（200）：
```json
{
  "status": "success",
  "message": "已模拟向老人发起call联系（模拟功能，未实际拨打）"
}
```

> ⚠️ 此接口仅返回模拟提示，**不会真的拨打或留言**。真实留言请走接口 13。

---

### 13. 发送留言

**POST** `/api/messages`

请求：
```json
{
  "elder_id": "elder_001",
  "family_id": "family_001",
  "content": "记得喝水"
}
```

响应（200）：
```json
{ "status": "ok", "message": "留言已发送", "id": "MSG-A1B2C3D4" }
```

错误：422 `EMPTY_MESSAGE`（内容为空或纯空白）；内容超过 500 字符自动截断。

---

### 14. 获取全部留言

**GET** `/api/messages/{elder_id}`

响应（200）：留言数组，最新在前：
```json
[
  {
    "id": "MSG-A1B2C3D4",
    "family_id": "family_001",
    "elder_id": "elder_001",
    "content": "记得喝水",
    "created_at": "2026-07-31T12:00:00.123456",
    "read": false
  }
]
```

---

### 15. 获取未读留言

**GET** `/api/messages/{elder_id}/unread`

响应（200）：未读留言数组（结构同接口 14）。

> 老人端建议：**轮询此接口**（如每 3~5 秒），有未读时弹窗提示并调用接口 16 标记已读。

---

### 16. 标记留言已读

**POST** `/api/messages/{message_id}/read`

无请求体。响应（200）：`{ "status": "ok" }`

---

### 17. 重置演示数据

**POST** `/api/demo/reset`

清空全部订单、家属规则、留言。响应：
```json
{
  "status": "ok",
  "message": "演示状态已重置",
  "cleared": { "orders": 5, "family_rules": 2, "messages": 3 }
}
```

---

### 18. 健康检查

**GET** `/health`

响应（200）：`{ "status": "ok" }`

---

## 五、餐食数据（meals.json）

50 道适老餐食，字段结构与接口 1 的 `meals` 元素一致。示例：

| id | 名称 | 价格 | 标签 |
|----|------|------|------|
| meal_001 | 清蒸鲈鱼套餐 | 28 | low_oil, low_salt |
| meal_002 | 番茄鸡蛋面 | 18 | soft_food, low_oil |
| meal_003 | 小米粥配蒸饺 | 22 | soft_food, low_oil |
| ... | ... | ... | ... |
| meal_030 | 咖喱鸡肉饭 | 28 | （无） |
| ... | ... | ... | ... |
| meal_050 | 素三鲜饺子 | 18 | vegetarian, low_oil, low_salt, no_pork, no_seafood |

---

## 六、推荐引擎与 AI 模式

### 推荐链路
```
老人输入 → [大模型解析 或 本地规则] → 意图(偏好/预算/关键词)
        → 家属规则硬过滤 → 综合评分 → Top 3 推荐 + 理由
```

### AI 模式说明
- 配置环境变量 `OPENAI_API_KEY`（阿里云百炼）后，默认调用 `qwen3.7-max` 大模型解析
- 未配置 Key / 网络异常 / 解析失败 → **自动降级**为本地关键词解析（`ai_mode: "local"`）
- 前端可用 `ai_mode` 字段标识来源，不影响使用
