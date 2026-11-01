from datetime import datetime
from typing import Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

Role = Literal["admin", "guard", "student", "staff", "lecturer"]
UserStatus = Literal["active", "inactive", "blacklisted"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    identifier: str = Field(
        min_length=1,
        max_length=120,
        validation_alias=AliasChoices("identifier", "username"),
        description="Account email address or registration number. The legacy username field is also accepted.",
    )
    password: str = Field(min_length=1, max_length=128)


class UserSummary(ORMModel):
    id: int
    full_name: str
    role: Role
    reg_number: str | None
    email: EmailStr | None
    status: UserStatus


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserSummary


class AccessTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class RegistrationRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    reg_number: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=10, max_length=72)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    reg_number: str = Field(min_length=2, max_length=60)
    role: Role
    password: str = Field(min_length=10, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    status: UserStatus | None = None


class UserOut(ORMModel):
    id: int
    full_name: str
    email: EmailStr | None
    reg_number: str | None
    role: Role
    qr_code: str | None = None
    qr_expires: datetime | None = None
    photo: str | None = None
    status: UserStatus
    created_at: datetime


class UserPublic(ORMModel):
    id: int
    full_name: str
    reg_number: str | None
    role: Role
    photo: str | None = None


class ScanRequest(BaseModel):
    qr_code: str = Field(min_length=1)
    gate_id: int = Field(gt=0)
    mode: Literal["guarded", "auto"] = "guarded"


class AdmitRequest(BaseModel):
    user_id: int = Field(gt=0)
    gate_id: int = Field(gt=0)
    direction: Literal["in", "out"]
    mode: Literal["guarded", "auto"] = "guarded"


class EntryOut(ORMModel):
    id: int
    user_id: int
    gate_id: int | None
    direction: Literal["in", "out"]
    scanned_at: datetime


class VisitorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    id_number: str | None = None
    phone: str | None = None
    reason: str | None = None
    host: str | None = None
    expected_exit: str | None = None


class VisitorOut(ORMModel):
    id: int
    name: str
    id_number: str | None
    reason: str | None
    host: str | None
    time_in: datetime | None
    expected_exit: datetime | None
    checked_out: bool


class AlertOut(ORMModel):
    id: int
    type: str
    description: str | None
    resolved: bool
    timestamp: datetime
