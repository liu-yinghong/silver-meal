from app.schemas.meal import Meal, MealRecommendResponse
from app.repositories.mock_repo import MockMealRepository


class MealService:
    def __init__(self, meal_repo: MockMealRepository):
        self.meal_repo = meal_repo

    def recommend_meals(self, query: str, limit: int = 3) -> MealRecommendResponse:
        meals = self.meal_repo.filter_meals(query, limit=limit)
        summary = f"根据您的需求"{query}"，为您推荐以下餐食"
        return MealRecommendResponse(meals=meals, query_summary=summary)

    def get_meal(self, meal_id: str) -> Meal | None:
        return self.meal_repo.get_meal_by_id(meal_id)

    def get_all_meals(self) -> list[Meal]:
        return self.meal_repo.get_all_meals()