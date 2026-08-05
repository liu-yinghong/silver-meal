from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Message(BaseModel):
    id: str = Field(..., description="消息ID")
    family_id: str = Field(..., description="发送家属ID")
    elder_id: str = Field(..., description="接收老人ID")
    sender: str = Field('', description="发送家属称呼（如：女儿）")
    content: str = Field(..., description="留言内容")
    created_at: datetime = Field(..., description="发送时间")
    read: bool = Field(False, description="是否已读")


class MessageCreateRequest(BaseModel):
    elder_id: str = Field(..., description="接收老人ID")
    family_id: str = Field(..., description="发送家属ID")
    sender: str = Field('', description="发送家属称呼（如：女儿）")
    content: str = Field(..., description="留言内容")
