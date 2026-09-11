"""Auth JWT — bootstrap OPS + login."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field(default="OPS", pattern="^(MEMBER|OPS|ADMIN)$")


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(body: RegisterBody, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role=body.role,
        tenant_id="mulemacare",
    )
    db.add(user)
    await db.commit()
    token = create_access_token(
        user_id=user.id, email=user.email, role=user.role, tenant_id=user.tenant_id
    )
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.post("/login")
async def login(body: LoginBody, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        user_id=user.id, email=user.email, role=user.role, tenant_id=user.tenant_id
    )
    return {"access_token": token, "token_type": "bearer", "role": user.role}
