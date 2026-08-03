from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
import json

from app.schemas.meal import Meal, MealRecommendRequest, MealRecommendResponse, TodayRequest, RecommendStreamRequest
from app.schemas.order import OrderCreateRequest, OrderCreateResponse, OrderStatusResponse, OrderConfirmRequest
from app.schemas.family import FamilySettingsUpdate, FamilyOrderStatus, FamilyContactRequest, FamilyContactResponse, FamilyRule
from app.schemas.message import MessageCreateRequest
from app.core.meal_service import MealService
from app.core.order_service import OrderService
from app.core.exceptions import InvalidOrderTransition
from app.core.weather_service import WeatherService
from app.core.asr_service import ASRService
from app.core.today_service import TodayService
from app.core.agent_workflow import RecommendWorkflow
from app.core.analysis_service import AnalysisService
from app.core.llm_service import LLMService
from app.repositories.mock_repo import MockMealRepository, MockOrderRepository, MockFamilyRepository, MockMessageRepository


meal_repo = MockMealRepository('data/meals.json')
order_repo = MockOrderRepository('tmp/demo_state/orders.json')   # 历史订单库（文件持久化）
family_repo = MockFamilyRepository('tmp/demo_state/rules.json')
family_repo.set_order_repo(order_repo)
message_repo = MockMessageRepository('tmp/demo_state/messages.json')

meal_service = MealService(meal_repo)
local_meal_service = MealService(meal_repo, llm_service=LLMService(use_remote=False))  # 传统检索，不调用大模型
order_service = OrderService(order_repo)
today_service = TodayService(meal_repo, order_repo, family_repo)
workflow = RecommendWorkflow(meal_repo, order_repo, family_repo)
analysis_service = AnalysisService(meal_repo, order_repo, family_repo)

router = APIRouter()


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=message,
        headers={'X-Error-Code': code},
    )


# ---- 餐食推荐 ----
@router.post('/api/meals/recommend', response_model=MealRecommendResponse)
def recommend_meals(req: MealRecommendRequest):
    rules = family_repo.get_family_rules(req.family_id, 'elder_001')
    meals, summary, reasons, ai_mode = meal_service.recommend_with_reasons(req.text_input, family_rules=rules)
    if not meals:
        raise _http_error(422, 'NO_ELIGIBLE_MEAL', _no_eligible_message(req.text_input, rules))
    return MealRecommendResponse(meals=meals, query_summary=summary, reasons=reasons, ai_mode=ai_mode)


@router.post('/api/meals/recommend/local', response_model=MealRecommendResponse)
def recommend_local(req: MealRecommendRequest):
    """传统本地检索（不调用大模型）：按用户输入关键词/偏好 + 家属规则过滤排序，取评分前三。"""
    rules = family_repo.get_family_rules(req.family_id, 'elder_001')
    meals, summary, reasons, _ = local_meal_service.recommend_with_reasons(req.text_input, family_rules=rules)
    if not meals:
        raise _http_error(422, 'NO_ELIGIBLE_MEAL', _no_eligible_message(req.text_input, rules))
    return MealRecommendResponse(meals=meals, query_summary=summary, reasons=reasons, ai_mode='local')


@router.post('/api/meals/today', response_model=MealRecommendResponse)
def today_meals(req: TodayRequest):
    """今日推荐：评分最高 + 大模型按天气 + 历史下单最多，共三份餐食。"""
    meals, summary, reasons, ai_mode = today_service.recommend_today(
        req.family_id, req.elder_id, req.lat, req.lon)
    if not meals:
        raise _http_error(422, 'NO_ELIGIBLE_MEAL', summary)
    return MealRecommendResponse(meals=meals, query_summary=summary, reasons=reasons, ai_mode=ai_mode)


@router.post('/api/meals/recommend/stream')
def recommend_stream(req: RecommendStreamRequest):
    """大模型推荐工作流（SSE 流式）：理解需求→查看家庭设置→分析餐品→生成方案。
    前端按事件逐步打勾展示推理进度。"""
    def event_stream():
        for ev in workflow.stream(req.text_input, req.family_id, req.elder_id,
                                  mode=req.mode, lat=req.lat, lon=req.lon):
            yield f'data: {json.dumps(ev, ensure_ascii=False)}\n\n'
    return StreamingResponse(event_stream(), media_type='text/event-stream')


@router.get('/api/meals/{meal_id}', response_model=Meal)
def get_meal_detail(meal_id: str):
    """按 ID 查询单份餐食（用于再来一份直接展示上次下单的餐食）。"""
    meal = meal_service.get_meal(meal_id)
    if not meal:
        raise _http_error(404, 'MEAL_NOT_FOUND', '餐品不存在')
    return meal


@router.post('/api/analysis')
def get_analysis():
    """家属端 AI 分析：大模型分析家属饮食规则与推荐餐食的匹配，输出综合适合度。"""
    return analysis_service.analyze('family_001', 'elder_001')


def _no_eligible_message(text_input: str, rules: FamilyRule | None) -> str:
    parts = [f'没有符合您需求的餐品']
    if rules:
        constraints = [f'单餐最高{rules.max_price:g}元']
        if rules.allowed_dietary:
            pref_map = {
                'low_oil': '低油', 'low_salt': '低盐', 'low_sugar': '低糖', 'soft_food': '软烂易消化',
                'vegetarian': '素食', 'high_protein': '高蛋白', 'low_carb': '低碳水', 'gluten_free': '无麸质',
                'halal': '清真', 'no_pork': '无猪肉', 'no_seafood': '无海鲜', 'low_purine': '低嘌呤',
            }
            constraints.append('要求' + '、'.join(pref_map.get(p, p) for p in rules.allowed_dietary))
        if rules.blocked_items:
            constraints.append('禁食' + '、'.join(rules.blocked_items))
        parts.append('（当前家庭规则：' + '、'.join(constraints) + '）')
    parts.append('，请放宽一项条件后重试')
    return ''.join(parts)


# ---- 订单 ----
@router.post('/api/orders', response_model=OrderCreateResponse)
def create_order(req: OrderCreateRequest):
    meal = meal_service.get_meal(req.meal_id)
    if not meal:
        raise _http_error(404, 'MEAL_NOT_FOUND', '餐品不存在')
    return order_service.create_order(req.meal_id, req.elder_id, req.family_id, meal.name, meal.price, meal.eta_minutes)


@router.get('/api/orders/{order_id}', response_model=OrderStatusResponse)
def get_order(order_id: str):
    result = order_service.get_status(order_id)
    if not result:
        raise _http_error(404, 'ORDER_NOT_FOUND', '订单不存在')
    return result


@router.post('/api/orders/{order_id}/advance', response_model=OrderStatusResponse)
def advance_order(order_id: str):
    result = order_service.advance_to_next(order_id)
    if not result:
        raise _http_error(404, 'ORDER_NOT_FOUND', '订单不存在')
    return result


@router.post('/api/orders/{order_id}/deliver', response_model=OrderStatusResponse)
def deliver_order(order_id: str):
    result = order_service.advance_to_delivered(order_id)
    if not result:
        raise _http_error(404, 'ORDER_NOT_FOUND', '订单不存在')
    return result


@router.post('/api/orders/{order_id}/cancel', response_model=OrderStatusResponse)
def cancel_order(order_id: str):
    try:
        result = order_service.cancel_order(order_id)
    except InvalidOrderTransition as e:
        raise _http_error(409, 'INVALID_ORDER_TRANSITION', e.message)
    if not result:
        raise _http_error(404, 'ORDER_NOT_FOUND', '订单不存在')
    return result


@router.post('/api/orders/{order_id}/timeout', response_model=OrderStatusResponse)
def mark_order_timeout(order_id: str):
    result = order_service.mark_timeout(order_id)
    if not result:
        raise _http_error(404, 'ORDER_NOT_FOUND', '订单不存在')
    return result


@router.post('/api/orders/confirm', response_model=OrderStatusResponse)
def confirm_order(req: OrderConfirmRequest):
    try:
        result = order_service.confirm_received(req.order_id)
    except InvalidOrderTransition as e:
        raise _http_error(409, 'INVALID_ORDER_TRANSITION', e.message)
    if not result:
        raise _http_error(404, 'ORDER_NOT_FOUND', '订单不存在')
    return result


# ---- 家属 ----
@router.post('/api/family/settings', response_model=dict)
def update_family_settings(req: FamilySettingsUpdate):
    family_repo.save_family_rules(req.family_id, req.elder_id, req.rules)
    return {'status': 'ok', 'message': '家属规则已保存'}


@router.get('/api/family/{family_id}/rules', response_model=FamilyRule | None)
def get_family_rules(family_id: str, elder_id: str):
    rules = family_repo.get_family_rules(family_id, elder_id)
    if not rules:
        return FamilyRule()
    return rules


@router.get('/api/family/{family_id}/orders', response_model=list[FamilyOrderStatus])
def get_family_orders(family_id: str):
    return family_repo.get_family_order_status(family_id)


@router.post('/api/family/contact', response_model=FamilyContactResponse)
def contact_elder(req: FamilyContactRequest):
    order = None
    if req.order_id == 'latest':
        family_orders = family_repo.get_family_order_status(req.family_id)
        if family_orders:
            order = order_service.get_status(family_orders[0].order_id)
    else:
        order = order_service.get_status(req.order_id)
    if not order:
        raise _http_error(404, 'ORDER_NOT_FOUND', '订单不存在')
    return FamilyContactResponse(
        status='success',
        message=f'已模拟向老人发起{req.contact_type}联系（模拟功能，未实际拨打）',
    )


# ---- 消息 ----
@router.post('/api/messages', response_model=dict)
def send_message(req: MessageCreateRequest):
    content = (req.content or '').strip()
    if not content:
        raise _http_error(422, 'EMPTY_MESSAGE', '留言内容不能为空')
    content = content[:500]
    msg = message_repo.send_message(req.elder_id, req.family_id, content, (req.sender or '').strip())
    return {"status": "ok", "message": "留言已发送", "id": msg["id"]}


@router.get('/api/messages/{elder_id}', response_model=list[dict])
def get_all_messages(elder_id: str):
    return message_repo.get_all_messages(elder_id)


@router.get('/api/messages/{elder_id}/unread', response_model=list[dict])
def get_unread_messages(elder_id: str):
    return message_repo.get_unread_messages(elder_id)


@router.post('/api/messages/{message_id}/read', response_model=dict)
def mark_message_read(message_id: str):
    message_repo.mark_as_read(message_id)
    return {"status": "ok"}


# ---- 天气（智能体工具）----
@router.get('/api/weather')
def get_weather(lat: float | None = None, lon: float | None = None):
    """获取实时天气（Open-Meteo 真实数据，失败自动降级）。"""
    svc = WeatherService()
    return svc.get_weather(lat, lon)


# ---- 语音识别（智能体工具）----
@router.post('/api/asr')
async def transcribe_audio(file: UploadFile):
    """语音转文字（DashScope Paraformer）。上传 16kHz 单声道 WAV。"""
    content = await file.read()
    asr = ASRService()
    text = asr.transcribe(content)
    if not text:
        raise _http_error(422, 'ASR_FAILED', '语音识别失败，请重试或直接输入文字')
    return {'text': text}


# ---- Demo 控制 ----
@router.post('/api/demo/reset')
def demo_reset():
    cleared_orders = order_repo.reset()
    cleared_rules = family_repo.reset()
    cleared_messages = message_repo.reset()
    return {
        'status': 'ok',
        'message': '演示状态已重置',
        'cleared': {
            'orders': cleared_orders,
            'family_rules': cleared_rules,
            'messages': cleared_messages,
        },
    }
