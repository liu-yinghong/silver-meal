"""订单状态机单元测试：创建、推进、合法/非法确认与取消、超时。"""

from datetime import datetime, timedelta

import pytest

from app.core.exceptions import InvalidOrderTransition
from app.core.order_service import OrderService
from app.repositories.mock_repo import MockOrderRepository
from app.schemas.order import OrderStatus


@pytest.fixture()
def order_service():
    return OrderService(MockOrderRepository())


def test_create_order_status_created(order_service):
    resp = order_service.create_order('meal_001', 'elder_001', 'family_001', '清蒸鲈鱼套餐', 28.0)
    assert resp.status == OrderStatus.CREATED
    status = order_service.get_status(resp.order_id)
    assert status.meal_name == '清蒸鲈鱼套餐'
    assert status.meal_price == 28.0


def test_create_order_is_idempotent_for_active_order(order_service):
    first = order_service.create_order('meal_001', 'elder_001', 'family_001', '清蒸鲈鱼套餐', 28.0, 35)
    second = order_service.create_order('meal_001', 'elder_001', 'family_001', '清蒸鲈鱼套餐', 28.0, 35)
    assert first.order_id == second.order_id  # 活动订单不重复创建
    order_service.advance_to_delivered(first.order_id)
    order_service.confirm_received(first.order_id)
    third = order_service.create_order('meal_001', 'elder_001', 'family_001', '清蒸鲈鱼套餐', 28.0, 35)
    assert third.order_id != first.order_id  # 已收餐后允许再点


def test_order_eta_snapshot(order_service):
    resp = order_service.create_order('meal_001', 'elder_001', 'family_001', '清蒸鲈鱼套餐', 28.0, 40)
    assert resp.eta_minutes == 40
    assert order_service.get_status(resp.order_id).eta_minutes == 40


def test_advance_to_delivered(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    delivered = order_service.advance_to_delivered(resp.order_id)
    assert delivered.status == OrderStatus.DELIVERED


def test_confirm_before_delivered_raises(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    with pytest.raises(InvalidOrderTransition):
        order_service.confirm_received(resp.order_id)


def test_confirm_after_delivered_ok(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_delivered(resp.order_id)
    confirmed = order_service.confirm_received(resp.order_id)
    assert confirmed.status == OrderStatus.CONFIRMED
    assert confirmed.confirmed is True
    assert confirmed.confirmed_at is not None


def test_cancel_valid_from_preparing(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_next(resp.order_id)  # paid
    order_service.advance_to_next(resp.order_id)  # preparing
    cancelled = order_service.cancel_order(resp.order_id)
    assert cancelled.status == OrderStatus.CANCELLED


def test_cancel_from_delivered_raises(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_delivered(resp.order_id)
    with pytest.raises(InvalidOrderTransition):
        order_service.cancel_order(resp.order_id)


def test_cancel_from_confirmed_raises(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_delivered(resp.order_id)
    order_service.confirm_received(resp.order_id)
    with pytest.raises(InvalidOrderTransition):
        order_service.cancel_order(resp.order_id)


def test_check_timeout_only_when_delivered_and_unconfirmed(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    assert order_service.check_timeout(resp.order_id, 5) is False  # 未送达
    order_service.advance_to_delivered(resp.order_id)
    assert order_service.check_timeout(resp.order_id, 5) is False  # 刚送达未超时


def test_check_timeout_true_after_duration(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_delivered(resp.order_id)
    repo = order_service._repo
    repo._orders[resp.order_id]['updated_at'] = datetime.now() - timedelta(minutes=40)
    assert order_service.check_timeout(resp.order_id, 30) is True
    assert order_service.check_timeout(resp.order_id, 60) is False


def test_mark_unconfirmed_timeout(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_delivered(resp.order_id)
    timed_out = order_service.mark_timeout(resp.order_id)
    assert timed_out.status == OrderStatus.UNCONFIRMED_TIMEOUT


def test_mark_timeout_does_not_touch_confirmed(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_delivered(resp.order_id)
    order_service.confirm_received(resp.order_id)
    status = order_service.mark_timeout(resp.order_id)
    assert status.status == OrderStatus.CONFIRMED


def test_confirm_is_idempotent(order_service):
    resp = order_service.create_order('meal_001', 'elder_001')
    order_service.advance_to_delivered(resp.order_id)
    order_service.confirm_received(resp.order_id)
    with pytest.raises(InvalidOrderTransition):
        order_service.confirm_received(resp.order_id)  # 已确认后再确认非法


def test_reset_clears_orders(order_service):
    order_service.create_order('meal_001', 'elder_001')
    assert order_service._repo.reset() == 1
    assert order_service._repo.get_order_status('whatever') is None
