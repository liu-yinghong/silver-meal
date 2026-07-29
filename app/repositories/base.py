from typing import Protocol
from app.schemas.meal import Meal
from app.schemas.order import OrderStatusResponse, OrderCreateResponse
from app.schemas.family import FamilyRule, FamilyOrderStatus


class MealRepository(Protocol):
    def get_all_meals(self) -> list[Meal]:
        ...

    def get_meal_by_id(self, meal_id: str) -> Meal | None:
        ...

    def filter_meals(self, query: str, limit: int = 3) -> list[Meal]:
        ...


class OrderRepository(Protocol):
    def create_order(self, meal_id: str, elder_id: str, family_id: str | None) -> OrderCreateResponse:
        ...

    def get_order_status(self, order_id: str) -> OrderStatusResponse | None:
        ...

    def confirm_order(self, order_id: str) -> OrderStatusResponse | None:
        ...

    def advance_status(self, order_id: str) -> OrderStatusResponse | None:
        ...


class FamilyRepository(Protocol):
    def get_family_rules(self, family_id: str, elder_id: str) -> FamilyRule | None:
        ...

    def save_family_rules(self, family_id: str, elder_id: str, rules: FamilyRule) -> bool:
        ...

    def get_family_order_status(self, family_id: str) -> list[FamilyOrderStatus]:
        ...