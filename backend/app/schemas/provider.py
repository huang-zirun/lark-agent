from datetime import datetime

from pydantic import BaseModel, Field

from app.models.provider import ProviderType


class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1)
    provider_type: ProviderType
    api_base: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool = True
    priority: int = 0


class ProviderUpdate(BaseModel):
    name: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class ProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: ProviderType
    api_base: str | None
    default_model: str | None
    enabled: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderValidateResponse(BaseModel):
    valid: bool
    message: str
