from datetime import datetime, timedelta, timezone

from app.schemas.order import OrderCreateResponse, OrderStatusResponse
from app.repositories.base import OrderRepository


class OrderService:
    def __init__(self, order_repo: OrderRepository):
        self._repo = order_repo

    def create_order(self, meal_id: str, elder_id: str, family_id: str | None = None,
                     meal_name: str = '', meal_price: float = 0.0, eta_minutes: int = 35) -> OrderCreateResponse:
        return self._repo.create_order(meal_id, elder_id, family_id, meal_name, meal_price, eta_minutes)

    def get_status(self, order_id: str) -> OrderStatusResponse | None:
        return self._repo.get_order_status(order_id)

    def advance_to_next(self, order_id: str) -> OrderStatusResponse | None:
        return self._repo.advance_status(order_id)

    def advance_to_delivered(self, order_id: str) -> OrderStatusResponse | None:
        result = None
        for _ in range(10):
            status = self._repo.get_order_status(order_id)
            if status is None:
                return None
            if status.status.value == 'delivered':
                return status
            result = self._repo.advance_status(order_id)
            if result and result.status.value == 'delivered':
                return result
        return result

    def cancel_order(self, order_id: str) -> OrderStatusResponse | None:
        return self._repo.cancel_order(order_id)

    def confirm_received(self, order_id: str) -> OrderStatusResponse | None:
        return self._repo.confirm_order(order_id)

    def mark_timeout(self, order_id: str) -> OrderStatusResponse | None:
        return self._repo.mark_unconfirmed_timeout(order_id)

    def check_timeout(self, order_id: str, timeout_minutes: int = 30) -> bool:
        status = self._repo.get_order_status(order_id)
        if not status:
            return False
        if status.status.value != 'delivered':
            return False
        if status.confirmed:
            return False
        updated = status.updated_at
        if updated.tzinfo is None:
            # 仓库用 datetime.now() 生成，是本地时间；转成 UTC 再比较
            updated = updated.astimezone(timezone.utc)
        return (datetime.now(timezone.utc) - updated) > timedelta(minutes=timeout_minutes)