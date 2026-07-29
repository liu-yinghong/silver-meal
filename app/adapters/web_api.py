from fastapi import APIRouter, HTTPException

from app.schemas.meal import MealRecommendRequest, MealRecommendResponse
from app.schemas.order import OrderCreateRequest, OrderCreateResponse, OrderStatusResponse, OrderConfirmRequest
from app.schemas.family import FamilySettingsUpdate, FamilyOrderStatus, FamilyContactRequest, FamilyContactResponse, FamilyRule
from app.core.meal_service import MealService
from app.core.order_service import OrderService
from app.core.rule_engine import RuleEngine
from app.repositories.mock_repo import MockMealRepository, MockOrderRepository, MockFamilyRepository


meal_repo = MockMealRepository('data/meals.json')
order_repo = MockOrderRepository()
family_repo = MockFamilyRepository()
family_repo.set_order_repo(order_repo)

meal_service = MealService(meal_repo)
order_service = OrderService(order_repo)
rule_engine = RuleEngine()

router = APIRouter()


# ---- 餐食推荐 ----
@router.post('/api/meals/recommend', response_model=MealRecommendResponse)
def recommend_meals(req: MealRecommendRequest):
    meals, summary = meal_service.recommend_for_elder(req.text_input, family_rules=None)
    return MealRecommendResponse(meals=meals, query_summary=summary)


# ---- 订单 ----
@router.post('/api/orders', response_model=OrderCreateResponse)
def create_order(req: OrderCreateRequest):
    return order_service.create_order(req.meal_id, req.elder_id, req.family_id)


@router.get('/api/orders/{order_id}', response_model=OrderStatusResponse)
def get_order(order_id: str):
    result = order_service.get_status(order_id)
    if not result:
        raise HTTPException(status_code=404, detail='订单不存在')
    return result


@router.post('/api/orders/{order_id}/advance', response_model=OrderStatusResponse)
def advance_order(order_id: str):
    result = order_service.advance_to_next(order_id)
    if not result:
        raise HTTPException(status_code=404, detail='订单不存在')
    return result


@router.post('/api/orders/{order_id}/deliver', response_model=OrderStatusResponse)
def deliver_order(order_id: str):
    result = order_service.advance_to_delivered(order_id)
    if not result:
        raise HTTPException(status_code=404, detail='订单不存在')
    return result


@router.post('/api/orders/confirm', response_model=OrderStatusResponse)
def confirm_order(req: OrderConfirmRequest):
    result = order_service.confirm_received(req.order_id)
    if not result:
        raise HTTPException(status_code=404, detail='订单不存在')
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
    order = order_service.get_status(req.order_id)
    if not order:
        raise HTTPException(status_code=404, detail='订单不存在')
    return FamilyContactResponse(
        status='success',
        message=f'已模拟向老人发起{req.contact_type}联系（模拟功能，未实际拨打）',
    )