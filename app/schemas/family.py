from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FamilyRule(BaseModel):
    max_price: float = Field(35.0, description="单餐最高金额（元）")
    allowed_dietary: list[str] = Field(default=[], description="允许的饮食偏好列表")
    blocked_items: list[str] = Field(default=[], description="禁止的食材或餐食关键词")
    notify_on_unconfirm: bool = Field(True, description="超时未确认时是否提醒家属")
    unconfirm_timeout_minutes: int = Field(30, description="送达后多久未确认则提醒（分钟）")
    notes: str = Field(default="", description="家属备注信息（如：多加米饭）")


class FamilySettingsUpdate(BaseModel):
    family_id: str = Field(..., description="家属ID")
    elder_id: str = Field(..., description="关联老人ID")
    rules: FamilyRule = Field(..., description="家属设置的规则")


class FamilyOrderStatus(BaseModel):
    order_id: str = Field(..., description="订单ID")
    meal_id: Optional[str] = Field(None, description="餐食ID（用于再来一份）")
    elder_name: str = Field(..., description="老人姓名")
    meal_name: str = Field(..., description="餐食名称")
    meal_price: float = Field(..., description="餐食价格")
    eta_minutes: int = Field(35, description="预计送达分钟（Demo 模拟值）")
    status: str = Field(..., description="订单状态")
    confirmed: bool = Field(False, description="老人是否已确认收餐")
    rule_passed: bool = Field(True, description="是否通过家属规则校验")
    rule_detail: Optional[str] = Field(None, description="规则校验详情")
    created_at: Optional[datetime] = Field(None, description="下单时间")
    updated_at: datetime = Field(..., description="最近更新时间")
    confirmed_at: Optional[datetime] = Field(None, description="确认收货时间")


class FamilyContactRequest(BaseModel):
    order_id: str = Field(..., description="订单ID")
    family_id: str = Field(..., description="家属ID")
    contact_type: str = Field("call", description="联系方式：call=电话, message=留言")


class FamilyContactResponse(BaseModel):
    status: str = Field(..., description="操作状态")
    message: str = Field(..., description="提示信息（模拟）")