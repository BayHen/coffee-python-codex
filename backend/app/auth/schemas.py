"""Validated authentication request and response bodies."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=1024)
    role: Literal["Admin", "Manager", "Staff"]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserStatusUpdate(BaseModel):
    is_active: bool


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserView(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
