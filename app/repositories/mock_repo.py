import json
import uuid
from datetime import datetime
from pathlib import Path

from app.schemas.meal import Meal
from app.schemas.order import OrderCreateResponse, OrderStatus, OrderStatusResponse
from app.schemas.family import FamilyOrderStatus, FamilyRule
from app.core.exceptions import InvalidOrderTransition


class MockMealRepository:
    def __init__(self, data_path: str = 'data/meals.json'):
        _root = Path(__file__).resolve().parent.parent.parent
        _path = _root / data_path
        with open(str(_path), 'r', encoding='utf-8-sig') as f:
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
            '素食': ['vegetarian', 'no_pork', 'no_seafood'],
            '高蛋白': ['high_protein'],
            '低碳水': ['low_carb'],
            '无麸质': ['gluten_free'],
            '清真': ['halal', 'no_pork'],
            '不吃猪肉': ['no_pork'],
            '不吃海鲜': ['no_seafood'],
            '低嘌呤': ['low_purine'],
        }
        matched_tags: set[str] = set()
        for keyword, tags in keywords_map.items():
            if keyword in query:
                matched_tags.update(tags)

        for meal in self._meals:
            score = 0
            meal_tags = [t.value for t in meal.dietary_tags]
            if matched_tags and any(tag in meal_tags for tag in matched_tags):
                score += 2
            if any(kw in meal.name or kw in meal.description for kw in query_lower.split()):
                score += 1
            results.append((score, meal))

        results.sort(key=lambda x: x[0], reverse=True)
        return [meal for _, meal in results[:limit]]


class MockOrderRepository:
    def __init__(self, data_path: str | None = None):
        # data_path 提供时启用文件持久化（历史订单库），None 则纯内存（测试用）
        self._data_path = data_path
        self._orders = self._load_orders()
        self._status_flow = [
            OrderStatus.CREATED,
            OrderStatus.PAID,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERING,
            OrderStatus.DELIVERED,
        ]

    def _state_path(self) -> Path | None:
        if not self._data_path:
            return None
        return Path(__file__).resolve().parent.parent.parent / self._data_path

    def _load_orders(self) -> dict:
        path = self._state_path()
        if not path or not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return {oid: self._deserialize(o) for oid, o in data.items()}

    def _persist(self):
        path = self._state_path()
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {oid: self._serialize(o) for oid, o in self._orders.items()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    @staticmethod
    def _serialize(o: dict) -> dict:
        o2 = dict(o)
        o2['status'] = o['status'].value
        for k in ('created_at', 'updated_at', 'confirmed_at'):
            if o2.get(k):
                o2[k] = o2[k].isoformat()
        return o2

    @staticmethod
    def _deserialize(o: dict) -> dict:
        o2 = dict(o)
        o2['status'] = OrderStatus(o['status'])
        for k in ('created_at', 'updated_at', 'confirmed_at'):
            v = o2.get(k)
            if v:
                o2[k] = datetime.fromisoformat(v)
        return o2

    def create_order(self, meal_id: str, elder_id: str, family_id: str | None,
                     meal_name: str = '', meal_price: float = 0.0, eta_minutes: int = 35) -> OrderCreateResponse:
        existing = self._find_active_order(meal_id, elder_id)
        if existing:
            return OrderCreateResponse(
                order_id=existing['order_id'],
                status=existing['status'],
                created_at=existing['created_at'],
                eta_minutes=existing.get('eta_minutes', 35),
            )
        order_id = f'ORD-{uuid.uuid4().hex[:8].upper()}'
        self._orders[order_id] = {
            'order_id': order_id,
            'meal_id': meal_id,
            'elder_id': elder_id,
            'family_id': family_id,
            'meal_name': meal_name,
            'meal_price': meal_price,
            'eta_minutes': eta_minutes,
            'status': OrderStatus.CREATED,
            'confirmed': False,
            'confirmed_at': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }
        self._persist()
        return OrderCreateResponse(
            order_id=order_id,
            status=OrderStatus.CREATED,
            created_at=self._orders[order_id]['created_at'],
            eta_minutes=eta_minutes,
        )

    def _find_active_order(self, meal_id: str, elder_id: str) -> dict | None:
        active = {OrderStatus.CREATED, OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.DELIVERING}
        for order in self._orders.values():
            if order['meal_id'] == meal_id and order['elder_id'] == elder_id and order['status'] in active:
                return order
        return None

    def get_order_status(self, order_id: str) -> OrderStatusResponse | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        return OrderStatusResponse(
            order_id=order['order_id'],
            status=order['status'],
            meal_name=order.get('meal_name', ''),
            meal_price=order.get('meal_price', 0.0),
            eta_minutes=order.get('eta_minutes', 35),
            updated_at=order['updated_at'],
            confirmed=order['confirmed'],
            confirmed_at=order['confirmed_at'],
        )

    def confirm_order(self, order_id: str) -> OrderStatusResponse | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        if order['status'] != OrderStatus.DELIVERED:
            raise InvalidOrderTransition('餐品送达前无法确认收餐')
        order['confirmed'] = True
        order['confirmed_at'] = datetime.now()
        order['status'] = OrderStatus.CONFIRMED
        order['updated_at'] = datetime.now()
        self._persist()
        return self.get_order_status(order_id)

    def cancel_order(self, order_id: str) -> OrderStatusResponse | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        cancellable = {
            OrderStatus.CREATED, OrderStatus.PAID,
            OrderStatus.PREPARING, OrderStatus.DELIVERING,
        }
        if order['status'] not in cancellable:
            raise InvalidOrderTransition('当前状态不可取消订单')
        order['status'] = OrderStatus.CANCELLED
        order['updated_at'] = datetime.now()
        self._persist()
        return self.get_order_status(order_id)

    def mark_unconfirmed_timeout(self, order_id: str) -> OrderStatusResponse | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        if order['status'] == OrderStatus.DELIVERED and not order['confirmed']:
            order['status'] = OrderStatus.UNCONFIRMED_TIMEOUT
            order['updated_at'] = datetime.now()
            self._persist()
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
                self._persist()
        return self.get_order_status(order_id)

    def reset(self) -> int:
        count = len(self._orders)
        self._orders.clear()
        path = self._state_path()
        if path and path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        return count

    def get_meal_order_counts(self) -> dict[str, int]:
        """统计每份餐食的历史下单次数（含已完成订单）。"""
        counts: dict[str, int] = {}
        for order in self._orders.values():
            mid = order.get('meal_id')
            if mid:
                counts[mid] = counts.get(mid, 0) + 1
        return counts


class MockFamilyRepository:
    def __init__(self, data_path: str | None = None):
        self._data_path = data_path
        self._rules = self._load_rules()
        self._order_repo: MockOrderRepository | None = None

    def _state_path(self) -> Path | None:
        if not self._data_path:
            return None
        return Path(__file__).resolve().parent.parent.parent / self._data_path

    def _load_rules(self) -> dict:
        path = self._state_path()
        if not path or not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return {k: FamilyRule(**v) for k, v in data.items()}

    def _persist(self):
        path = self._state_path()
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v.model_dump() for k, v in self._rules.items()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    def set_order_repo(self, repo: MockOrderRepository):
        self._order_repo = repo

    def _key(self, family_id: str, elder_id: str) -> str:
        return f'{family_id}:{elder_id}'

    def get_family_rules(self, family_id: str, elder_id: str) -> FamilyRule | None:
        return self._rules.get(self._key(family_id, elder_id))

    def save_family_rules(self, family_id: str, elder_id: str, rules: FamilyRule) -> bool:
        self._rules[self._key(family_id, elder_id)] = rules
        self._persist()
        return True

    def reset(self) -> int:
        count = len(self._rules)
        self._rules.clear()
        path = self._state_path()
        if path and path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        return count

    def get_family_order_status(self, family_id: str) -> list[FamilyOrderStatus]:
        results = []
        if self._order_repo:
            pref_map = {
                'low_oil': '低油', 'low_salt': '低盐', 'low_sugar': '低糖', 'soft_food': '软烂易消化',
                'vegetarian': '素食', 'high_protein': '高蛋白', 'low_carb': '低碳水', 'gluten_free': '无麸质',
                'halal': '清真', 'no_pork': '无猪肉', 'no_seafood': '无海鲜', 'low_purine': '低嘌呤',
            }
            for order in self._order_repo._orders.values():
                if order.get('family_id') == family_id:
                    elder_id = order.get('elder_id', '')
                    rules = self.get_family_rules(family_id, elder_id)
                    detail = ''
                    if rules:
                        prefs = [pref_map.get(p, p) for p in rules.allowed_dietary]
                        parts = [f'单餐最高{rules.max_price}元']
                        if prefs:
                            parts.append('、'.join(prefs))
                        if rules.blocked_items:
                            parts.append(f'禁：{"、".join(rules.blocked_items)}')
                        if rules.notes:
                            parts.append(f'备注：{rules.notes}')
                        detail = ' | '.join(parts)
                    results.append(FamilyOrderStatus(
                        order_id=order['order_id'],
                        meal_id=order.get('meal_id'),
                        elder_name='张奶奶',
                        meal_name=order.get('meal_name', ''),
                        meal_price=order.get('meal_price', 0.0),
                        eta_minutes=order.get('eta_minutes', 35),
                        status=order['status'].value,
                        confirmed=order['confirmed'],
                        rule_passed=True,
                        rule_detail=detail,
                        created_at=order.get('created_at'),
                        updated_at=order['updated_at'],
                        confirmed_at=order.get('confirmed_at'),
                    ))
        # 最新订单在前（与接口契约一致）
        results.sort(key=lambda o: o.created_at or datetime.min, reverse=True)
        return results


class MockMessageRepository:
    def __init__(self, data_path: str | None = None):
        self._data_path = data_path
        self._messages: list[dict] = self._load_messages()

    def _state_path(self) -> Path | None:
        if not self._data_path:
            return None
        return Path(__file__).resolve().parent.parent.parent / self._data_path

    def _load_messages(self) -> list[dict]:
        path = self._state_path()
        if not path or not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return []

    def _persist(self):
        path = self._state_path()
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._messages, ensure_ascii=False, indent=2), encoding='utf-8')

    def send_message(self, elder_id: str, family_id: str, content: str, sender: str = '') -> dict:
        import uuid
        from datetime import datetime
        msg = {
            "id": f'MSG-{uuid.uuid4().hex[:8].upper()}',
            "family_id": family_id,
            "elder_id": elder_id,
            "sender": sender,
            "content": content,
            "created_at": datetime.now().isoformat(),
            "read": False,
        }
        self._messages.append(msg)
        self._persist()
        return msg

    def get_unread_messages(self, elder_id: str) -> list[dict]:
        return [m for m in self._messages if m["elder_id"] == elder_id and not m["read"]]

    def get_all_messages(self, elder_id: str) -> list[dict]:
        return [m for m in self._messages if m["elder_id"] == elder_id]

    def mark_as_read(self, message_id: str) -> bool:
        for m in self._messages:
            if m["id"] == message_id:
                m["read"] = True
                self._persist()
                return True
        return False

    def reset(self) -> int:
        count = len(self._messages)
        self._messages.clear()
        path = self._state_path()
        if path and path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        return count
