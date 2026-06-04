from pydantic import BaseModel, EmailStr, field_validator
import re


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_safe(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9._@\-]{3,64}$", v):
            raise ValueError("username inválido")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
