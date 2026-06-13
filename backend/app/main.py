from fastapi import FastAPI
from app.db.session import Base, engine
from app.db import base  # noqa: F401 — registers all models
from app.api.v1.endpoints import auth, users

Base.metadata.create_all(bind=engine)  # creates tables on startup

app = FastAPI(
    title="Enterprise AI Platform",
    description="Knowledge & Automation Platform API",
    version="0.1.0",
    docs_url="/docs",
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

@app.get("/", tags=["Root"])
def root():
    return {"message": "Enterprise AI Platform API"}

@app.get("/health", tags=["Root"])
def health():
    return {"status": "healthy"}