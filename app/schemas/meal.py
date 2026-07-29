from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class DietaryPreference(str, Enum):
    NONE = "none"
    LOW_SUGAR = "low_sugar"
    LOW_SALT = "low_salt"
    LOW_OIL = "low_oil"
    SOFT_FOOD = "soft_food"


class Meal(BaseModel):
    id: str = Field(..., description="餐食唯一ID")
    name: str = Field(..., description="餐食名称")
    description: str = Field(..., description="餐食简要描述")
    price: float = Field(..., ge=0, description="价格（元）")
    image_url: Optional[str] = Field(None, description="餐食图片地址")
    dietary_tags: list[DietaryPreference] = Field(default=[], description="饮食标签")
    calories: Optional[int] = Field(None, description="预估热量（kcal）")


class MealRecommendRequest(BaseModel):
    text_input: str = Field(..., description="老人的文字或语音转文字输入")


class MealRecommendResponse(BaseModel):
    meals: list[Meal] = Field(..., description="推荐的三份餐食")
    query_summary: str = Field(..., description="系统理解的老人需求摘要")
