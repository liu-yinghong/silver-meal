from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class OrderStatus(str, Enum):
    CREATED = "created"
    PAID = "paid"
    PREPARING = "preparing"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    CONFIRMED = "confirmed"
    UNCONFIRMED_TIMEOUT = "unconfirmed_timeout"


class OrderCreateRequest(BaseModel):
    meal_id: str = Field(..., description="选中的餐食ID")
    elder_id: str = Field(..., description="老人ID")
    family_id: Optional[str] = Field(None, description="关联家属ID")


class OrderCreateResponse(BaseModel):
    order_id: str = Field(..., description="订单ID")
    status: OrderStatus = Field(..., description="当前订单状态")
    created_at: datetime = Field(..., description="创建时间")


class OrderStatusResponse(BaseModel):
    order_id: str = Field(..., description="订单ID")
    status: OrderStatus = Field(..., description="当前订单状态")
    meal_name: str = Field(..., description="餐食名称")
    meal_price: float = Field(..., description="餐食价格")
    updated_at: datetime = Field(..., description="最近状态更新时间")
    confirmed: bool = Field(False, description="老人是否已确认收餐")
    confirmed_at: Optional[datetime] = Field(None, description="确认收餐时间")


class OrderConfirmRequest(BaseModel):
    order_id: str = Field(..., description="订单ID")
    action: str = Field("confirm", description="操作：confirm=确认收餐")