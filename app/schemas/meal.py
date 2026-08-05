from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class DietaryPreference(str, Enum):
    NONE = "none"
    LOW_SUGAR = "low_sugar"
    LOW_SALT = "low_salt"
    LOW_OIL = "low_oil"
    SOFT_FOOD = "soft_food"
    VEGETARIAN = "vegetarian"
    HIGH_PROTEIN = "high_protein"
    LOW_CARB = "low_carb"
    GLUTEN_FREE = "gluten_free"
    HALAL = "halal"
    NO_PORK = "no_pork"
    NO_SEAFOOD = "no_seafood"
    LOW_PURINE = "low_purine"


class Meal(BaseModel):
    id: str = Field(..., description="餐食唯一ID")
    image_id: Optional[str] = Field(None, description="餐食图片唯一ID")
    name: str = Field(..., description="餐食名称")
    description: str = Field(..., description="餐食简要描述")
    price: float = Field(..., ge=0, description="价格（元）")
    image_url: Optional[str] = Field(None, description="餐食图片地址")
    dietary_tags: list[DietaryPreference] = Field(default=[], description="饮食标签")
    calories: Optional[int] = Field(None, description="预估热量（kcal）")
    eta_minutes: int = Field(35, description="预计送达分钟（Demo 模拟值）")


class MealRecommendRequest(BaseModel):
    text_input: str = Field(..., description="老人的文字或语音转文字输入")
    family_id: str = Field(default="family_001", description="家属ID，用于获取家属设置的规则")


class TodayRequest(BaseModel):
    """今日推荐请求：由大模型综合 评分最高 + 天气 + 历史下单 推荐三份餐食。"""
    family_id: str = Field(default="family_001", description="家属ID")
    elder_id: str = Field(default="elder_001", description="老人ID")
    lat: Optional[float] = Field(None, description="纬度（用于天气推荐）")
    lon: Optional[float] = Field(None, description="经度（用于天气推荐）")


class RecommendStreamRequest(BaseModel):
    """推荐工作流流式请求：前端按步骤实时展示大模型推理进度。"""
    text_input: str = Field(..., description="老人的文字或语音转文字输入")
    family_id: str = Field(default="family_001", description="家属ID")
    elder_id: str = Field(default="elder_001", description="老人ID")
    mode: str = Field("input", description="input=文字/语音输入；today=今日推荐")
    lat: Optional[float] = Field(None, description="纬度（今日推荐天气用）")
    lon: Optional[float] = Field(None, description="经度（今日推荐天气用）")


class MealRecommendResponse(BaseModel):
    meals: list[Meal] = Field(..., description="推荐的餐食列表")
    query_summary: str = Field(..., description="系统理解的老人需求摘要")
    reasons: list[str] = Field(default=[], description="每份餐食的推荐理由（与meals一一对应）")
    ai_mode: str = Field("local", description="意图解析来源：remote=真实大模型，local=本地规则降级")
