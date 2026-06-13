from sqlalchemy.orm import Session
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password, create_access_token
from fastapi import HTTPException, status

def register_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=data.email, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    _log(db, user.id, "USER_REGISTERED")
    return user

def login_user(db: Session, email: str, password: str) -> str:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    _log(db, user.id, "USER_LOGIN")
    return create_access_token({"sub": str(user.id), "role": user.role})

def _log(db: Session, user_id, action: str):
    db.add(AuditLog(user_id=user_id, action=action))
    db.commit()