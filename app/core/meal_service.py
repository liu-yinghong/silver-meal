from app.schemas.meal import Meal
from app.schemas.family import FamilyRule
from app.repositories.base import MealRepository
from app.core.llm_service import LLMService
from app.core.recommendation import RecommendationEngine


class MealService:
    def __init__(self, meal_repo: MealRepository, llm_service: LLMService | None = None):
        self._repo = meal_repo
        self._llm = llm_service or LLMService()
        self._recommender = RecommendationEngine(self._llm)

    def get_meal(self, meal_id: str) -> Meal | None:
        return self._repo.get_meal_by_id(meal_id)

    def recommend_for_elder(self, text_input: str, family_rules: FamilyRule | None = None):
        all_meals = self._repo.get_all_meals()
        results, summary, ai_mode = self._recommender.recommend(text_input, all_meals, family_rules)
        valid_ids = {m.id for m in all_meals}
        meals = [r.meal for r in results if r.meal.id in valid_ids]
        return meals, summary, ai_mode

    def recommend_with_reasons(self, text_input: str, family_rules: FamilyRule | None = None) -> tuple[list[Meal], str, list[str], str]:
        all_meals = self._repo.get_all_meals()
        results, summary, ai_mode = self._recommender.recommend(text_input, all_meals, family_rules)
        # 仅返回 meals.json 中真实存在的餐食（显式检索校验）
        valid_ids = {m.id for m in all_meals}
        meals = [r.meal for r in results if r.meal.id in valid_ids]
        reasons = [r.reason_text for r in results if r.meal.id in valid_ids]
        return meals, summary, reasons, ai_mode
