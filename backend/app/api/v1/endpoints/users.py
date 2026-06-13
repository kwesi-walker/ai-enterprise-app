from fastapi import APIRouter, Depends
from app.core.security import get_current_user, require_role
from app.models.user import UserRole

router = APIRouter()

@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return user

@router.get("/admin-only")
def admin_panel(user=Depends(require_role(UserRole.ADMIN))):
    return {"message": "Welcome, admin", "user": user}