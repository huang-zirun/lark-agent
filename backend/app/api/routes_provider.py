from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.provider import ProviderConfig
from app.schemas.provider import ProviderCreate, ProviderUpdate, ProviderResponse, ProviderValidateResponse
from app.core.provider.provider_registry import encrypt_api_key, resolve_provider
from app.shared.ids import generate_id
from app.shared.errors import DevFlowError

router = APIRouter()


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProviderConfig).order_by(ProviderConfig.priority.desc()))
    return list(result.scalars().all())


@router.post("/providers", response_model=ProviderResponse, status_code=201)
async def create_provider(body: ProviderCreate, db: AsyncSession = Depends(get_db)):
    encrypted_key = encrypt_api_key(body.api_key) if body.api_key else None
    provider = ProviderConfig(
        id=generate_id(),
        name=body.name,
        provider_type=body.provider_type,
        api_base=body.api_base,
        api_key_encrypted=encrypted_key,
        default_model=body.default_model,
        enabled=body.enabled,
        priority=body.priority,
    )
    db.add(provider)
    await db.flush()
    return provider


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: str,
    body: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(ProviderConfig, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if body.name is not None:
        provider.name = body.name
    if body.api_base is not None:
        provider.api_base = body.api_base
    if body.api_key is not None:
        provider.api_key_encrypted = encrypt_api_key(body.api_key)
    if body.default_model is not None:
        provider.default_model = body.default_model
    if body.enabled is not None:
        provider.enabled = body.enabled
    if body.priority is not None:
        provider.priority = body.priority

    await db.flush()
    return provider


@router.post("/providers/{provider_id}/validate", response_model=ProviderValidateResponse)
async def validate_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    try:
        provider_instance = await resolve_provider(db, provider_id=provider_id)
        is_valid = await provider_instance.validate()
        return ProviderValidateResponse(
            valid=is_valid,
            message="Provider is valid and reachable" if is_valid else "Provider validation failed",
        )
    except DevFlowError as e:
        return ProviderValidateResponse(valid=False, message=str(e))
