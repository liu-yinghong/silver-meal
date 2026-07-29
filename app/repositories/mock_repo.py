import json
import uuid
from datetime import datetime
from pathlib import Path

from app.schemas.meal import Meal
from app.schemas.order import OrderCreateResponse, OrderStatus, OrderStatusResponse
from app.schemas.family import FamilyOrderStatus, FamilyRule


class MockMealRepository:
    def __init__(self, data_path: str = 'data/meals.json'):
        with open(data_path, 'r', encoding='utf-8') as f:
            self._meals: list[Meal] = [Meal(**m) for m in json.load(f)]

    def get_all_meals(self) -> list[Meal]:
        return self._meals

    def get_meal_by_id(self, meal_id: str) -> Meal | None:
        for meal in self._meals:
            if meal.id == meal_id:
                return meal
        return None

    def filter_meals(self, query: str, limit: int = 3) -> list[Meal]:
        results = []
        query_lower = query.lower()
        keywords_map = {
            '清淡': ['low_oil', 'low_salt', 'soft_food'],
            '低糖': ['low_sugar'],
            '低盐': ['low_salt'],
            '低油': ['low_oil'],
            '软烂': ['soft_food'],
        }
        matched_tags: set[str] = set()
        for keyword, tags in keywords_map.items():
            if keyword in query:
                matched_tags.update(tags)

        for meal in self._meals:
            score = 0
            if matched_tags and any(tag.value in [t.value for t in meal.dietary_tags] for tag in matched_tags):
                score += 2
            if any(kw in meal.name or kw in meal.description for kw in query_lower.split()):
                score += 1
            results.append((score, meal))

        results.sort(key=lambda x: x[0], reverse=True)
        return [meal for _, meal in results[:limit]]


class MockOrderRepository:
    def __init__(self):
        self._orders: dict[str, dict] = {}
        self._status_flow = [
            OrderStatus.CREATED,
            OrderStatus.PAID,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERING,
            OrderStatus.DELIVERED,
        ]

    def create_order(self, meal_id: str, elder_id: str, family_id: str | None) -> OrderCreateResponse:
        order_id = f'ORD-{uuid.uuid4().hex[:8].upper()}'
        self._orders[order_id] = {
            'order_id': order_id,
            'meal_id': meal_id,
            'elder_id': elder_id,
            'family_id': family_id,
            'status': OrderStatus.CREATED,
            'confirmed': False,
            'confirmed_at': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }
        return OrderCreateResponse(
            order_id=order_id,
            status=OrderStatus.CREATED,
            created_at=self._orders[order_id]['created_at'],
        )

    def get_order_status(self, order_id: str) -> OrderStatusResponse | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        return OrderStatusResponse(
            order_id=order['order_id'],
            status=order['status'],
            meal_name='',
            meal_price=0.0,
            updated_at=order['updated_at'],
            confirmed=order['confirmed'],
            confirmed_at=order['confirmed_at'],
        )

    def confirm_order(self, order_id: str) -> OrderStatusResponse | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        order['confirmed'] = True
        order['confirmed_at'] = datetime.now()
        order['status'] = OrderStatus.CONFIRMED
        order['updated_at'] = datetime.now()
        return self.get_order_status(order_id)

    def advance_status(self, order_id: str) -> OrderStatusResponse | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        current = order['status']
        if current in self._status_flow:
            idx = self._status_flow.index(current)
            if idx < len(self._status_flow) - 1:
                order['status'] = self._status_flow[idx + 1]
                order['updated_at'] = datetime.now()
        return self.get_order_status(order_id)


class MockFamilyRepository:
    def __init__(self):
        self._rules: dict[str, FamilyRule] = {}
        self._order_repo: MockOrderRepository | None = None

    def set_order_repo(self, repo: MockOrderRepository):
        self._order_repo = repo

    def _key(self, family_id: str, elder_id: str) -> str:
        return f'{family_id}:{elder_id}'

    def get_family_rules(self, family_id: str, elder_id: str) -> FamilyRule | None:
        return self._rules.get(self._key(family_id, elder_id))

    def save_family_rules(self, family_id: str, elder_id: str, rules: FamilyRule) -> bool:
        self._rules[self._key(family_id, elder_id)] = rules
        return True

    def get_family_order_status(self, family_id: str) -> list[FamilyOrderStatus]:
        results = []
        if self._order_repo:
            for order in self._order_repo._orders.values():
                if order.get('family_id') == family_id:
                    results.append(FamilyOrderStatus(
                        order_id=order['order_id'],
                        elder_name='张奶奶',
                        meal_name='',
                        meal_price=0.0,
                        status=order['status'].value,
                        confirmed=order['confirmed'],
                        rule_passed=True,
                        rule_detail=None,
                        updated_at=order['updated_at'],
                    ))
        return results