from app.schemas.meal import Meal
from app.schemas.family import FamilyRule


class RuleCheckResult:
    def __init__(self, passed: bool, detail: str = ''):
        self.passed = passed
        self.detail = detail


class RuleEngine:
    def check_meal_against_rules(self, meal: Meal, rules: FamilyRule | None) -> RuleCheckResult:
        if rules is None:
            return RuleCheckResult(True, '未设置家属规则，默认通过')

        reasons = []

        if meal.price > rules.max_price:
            reasons.append(f'价格 {meal.price} 元超出上限 {rules.max_price} 元')

        if rules.blocked_items:
            for item in rules.blocked_items:
                if item in meal.name or item in meal.description:
                    reasons.append(f'含禁止食材: {item}')

        if rules.allowed_dietary:
            meal_tags = [t.value for t in meal.dietary_tags]
            if not any(tag in meal_tags for tag in rules.allowed_dietary):
                reasons.append('不含家属允许的任一饮食偏好')

        if reasons:
            return RuleCheckResult(False, '；'.join(reasons))
        return RuleCheckResult(True, '通过所有家属规则')

    def filter_meals_by_rules(self, meals: list[Meal], rules: FamilyRule | None) -> list[Meal]:
        if rules is None:
            return meals
        return [m for m in meals if self.check_meal_against_rules(m, rules).passed]