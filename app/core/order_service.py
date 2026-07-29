from app.schemas.order import OrderCreateResponse, OrderStatusResponse
from app.schemas.family import FamilyRule
from app.repositories.mock_repo import MockOrderRepository


class OrderService:
    def __init__(self, order_repo: MockOrderRepository):
        self._repo = order_repo

    def create_order(self, meal_id: str, elder_id: str, family_id: str | None = None) -> OrderCreateResponse:
        return self._repo.create_order(meal_id, elder_id, family_id)

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

    def confirm_received(self, order_id: str) -> OrderStatusResponse | None:
        return self._repo.confirm_order(order_id)

    def check_timeout(self, order_id: str, timeout_minutes: int = 30) -> bool:
        status = self._repo.get_order_status(order_id)
        if not status:
            return False
        if status.status.value != 'delivered':
            return False
        if status.confirmed:
            return False
        from datetime import timedelta
        elapsed = (status.updated_at - status.updated_at) + timedelta(minutes=0)
        return False