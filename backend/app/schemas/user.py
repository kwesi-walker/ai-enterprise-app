from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from app.models.user import UserRole

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.EMPLOYEE

class UserOut(BaseModel):
    id: UUID
    email: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}