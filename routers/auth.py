from typing import Literal

import asyncio

from pydantic import BaseModel, EmailStr, Field, model_validator

from fastapi import APIRouter, Header

from services import auth_db
from services.auth_service import (
    jwt_expires_in_seconds,
    login_account,
    register_account,
    send_code,
    user_from_token,
    verify_code,
)

router = APIRouter()


class SendCodeRequest(BaseModel):
    email: EmailStr = Field(..., description="接收验证码的邮箱")


class SendCodeResponse(BaseModel):
    sent: bool = Field(..., description="是否已发送")
    expires_in: int = Field(..., description="验证码有效期（秒）")


class VerifyCodeRequest(BaseModel):
    email: EmailStr = Field(..., description="邮箱")
    code: str = Field(..., min_length=4, max_length=8, description="收到的验证码")


class UserOut(BaseModel):
    id: int
    phone: str | None = None
    email: str | None = None
    account_type: Literal["phone", "email"] | None = Field(
        default=None, description="账号类型：手机号或邮箱"
    )
    created_at: str
    last_login: str | None = None


class VerifyCodeResponse(BaseModel):
    token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    is_new_user: bool = Field(..., description="是否为本次自动注册的新用户")
    user: UserOut


class AccountRegisterRequest(BaseModel):
    """注册：手机号或邮箱 + 密码（三选一提供账号即可）。"""

    account: str | None = Field(default=None, description="手机号或邮箱")
    phone: str | None = Field(default=None, description="手机号（与 account 二选一）")
    email: EmailStr | None = Field(default=None, description="邮箱（与 account 二选一）")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    invite_code: str | None = Field(default=None, max_length=32, description="邀请码（选填）")

    @model_validator(mode="after")
    def _require_account(self) -> "AccountRegisterRequest":
        if not self.resolved_account():
            raise ValueError("请提供手机号或邮箱。")
        return self

    def resolved_account(self) -> str:
        if self.account and self.account.strip():
            return self.account.strip()
        if self.phone and self.phone.strip():
            return self.phone.strip()
        if self.email:
            return str(self.email).strip()
        return ""


class AccountLoginRequest(BaseModel):
    """登录：手机号或邮箱 + 密码。"""

    account: str | None = Field(default=None, description="手机号或邮箱")
    phone: str | None = Field(default=None, description="手机号（与 account 二选一）")
    email: EmailStr | None = Field(default=None, description="邮箱（与 account 二选一）")
    password: str = Field(..., min_length=6, max_length=64, description="密码")

    @model_validator(mode="after")
    def _require_account(self) -> "AccountLoginRequest":
        if not self.resolved_account():
            raise ValueError("请提供手机号或邮箱。")
        return self

    def resolved_account(self) -> str:
        if self.account and self.account.strip():
            return self.account.strip()
        if self.phone and self.phone.strip():
            return self.phone.strip()
        if self.email:
            return str(self.email).strip()
        return ""


# 兼容旧字段名
RegisterRequest = AccountRegisterRequest
LoginRequest = AccountLoginRequest
EmailRegisterRequest = AccountRegisterRequest
EmailLoginRequest = AccountLoginRequest


class AuthTokenResponse(BaseModel):
    token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="令牌有效期（秒）")
    user: UserOut


def _public_email(user: dict) -> str | None:
    email = user.get("email")
    if not isinstance(email, str):
        return None
    if email.endswith(auth_db._PHONE_EMAIL_SUFFIX):
        return None
    return email


def _account_type(user: dict) -> Literal["phone", "email"]:
    if user.get("phone"):
        return "phone"
    return "email"


def _user_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"],
        phone=user.get("phone"),
        email=_public_email(user),
        account_type=_account_type(user),
        created_at=user["created_at"],
        last_login=user.get("last_login"),
    )


def _auth_response(user: dict, token: str) -> AuthTokenResponse:
    return AuthTokenResponse(
        token=token,
        expires_in=jwt_expires_in_seconds(),
        user=_user_out(user),
    )


@router.post("/send-code", response_model=SendCodeResponse)
async def auth_send_code(body: SendCodeRequest) -> SendCodeResponse:
    expires_in = await send_code(body.email)
    return SendCodeResponse(sent=True, expires_in=expires_in)


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def auth_verify_code(body: VerifyCodeRequest) -> VerifyCodeResponse:
    from services.points_service import setup_new_user

    user, is_new, token = await verify_code(body.email, body.code)
    if is_new:
        await setup_new_user(user["id"], None)
    return VerifyCodeResponse(
        token=token,
        is_new_user=is_new,
        user=_user_out(user),
    )


@router.post("/register", response_model=AuthTokenResponse)
async def auth_register(body: AccountRegisterRequest) -> AuthTokenResponse:
    """注册：手机号或邮箱 + 密码，成功后返回 JWT 与用户信息。"""
    from services.points_service import setup_new_user

    user, token = await register_account(
        body.resolved_account(),
        body.password,
        body.invite_code,
    )
    await setup_new_user(user["id"], body.invite_code)
    return _auth_response(user, token)


@router.post("/login", response_model=AuthTokenResponse)
async def auth_login(body: AccountLoginRequest) -> AuthTokenResponse:
    """登录：校验账号密码，通过后返回 JWT 与用户信息。"""
    user, token = await login_account(body.resolved_account(), body.password)
    return _auth_response(user, token)


@router.get("/me", response_model=UserOut)
async def auth_me(authorization: str | None = Header(default=None)) -> UserOut:
    """根据 Authorization: Bearer <token> 返回当前用户信息。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("未登录，请先登录。")
    token = authorization[7:].strip()
    if not token:
        raise ValueError("未登录，请先登录。")
    user = await asyncio.to_thread(user_from_token, token)
    return _user_out(user)


@router.post("/register-email", response_model=AuthTokenResponse, deprecated=True)
async def auth_register_email(body: AccountRegisterRequest) -> AuthTokenResponse:
    """（兼容）邮箱注册，请使用 POST /register。"""
    user, token = await register_account(
        body.resolved_account(),
        body.password,
        body.invite_code,
    )
    return _auth_response(user, token)


@router.post("/login-email", response_model=AuthTokenResponse, deprecated=True)
async def auth_login_email(body: AccountLoginRequest) -> AuthTokenResponse:
    """（兼容）邮箱登录，请使用 POST /login。"""
    user, token = await login_account(body.resolved_account(), body.password)
    return _auth_response(user, token)
