"""Search configuration CRUD endpoints.

Implements:
- GET /api/search-configs - List all search configs
- POST /api/search-configs - Create a new search config
- GET /api/search-configs/{id} - Get a single config
- PUT /api/search-configs/{id} - Update a config
- DELETE /api/search-configs/{id} - Delete a config
- PATCH /api/search-configs/{id}/toggle - Toggle enabled status
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.search_config import SearchConfig
from ..schemas.search_config import (
    SearchConfigCreate,
    SearchConfigListResponse,
    SearchConfigResponse,
    SearchConfigToggleResponse,
    SearchConfigUpdate,
)

router = APIRouter(prefix="/search-configs", tags=["search-configs"])
log = structlog.get_logger()


@router.get("", response_model=SearchConfigListResponse)
async def list_search_configs(
    db: AsyncSession = Depends(get_db),
    enabled_only: bool = False,
) -> SearchConfigListResponse:
    """List all search configurations.

    Args:
        enabled_only: If True, only return enabled configs

    Returns:
        List of search configs
    """
    log.info("list_search_configs_request", enabled_only=enabled_only)

    query = select(SearchConfig).order_by(SearchConfig.name)

    if enabled_only:
        query = query.where(SearchConfig.enabled == True)  # noqa: E712

    result = await db.execute(query)
    configs = list(result.scalars().all())

    return SearchConfigListResponse(
        configs=[SearchConfigResponse.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.post("", response_model=SearchConfigResponse, status_code=201)
async def create_search_config(
    config: SearchConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> SearchConfigResponse:
    """Create a new search configuration.

    Args:
        config: Search config data

    Returns:
        Created search config
    """
    log.info("create_search_config_request", name=config.name)

    db_config = SearchConfig(
        name=config.name,
        search_term=config.search_term,
        location=config.location,
        distance=config.distance,
        is_remote=config.is_remote,
        hours_old=config.hours_old,
        results_wanted=config.results_wanted,
        country=config.country,
        enabled=config.enabled,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(db_config)
    await db.flush()
    await db.refresh(db_config)

    log.info("create_search_config_success", id=db_config.id, name=db_config.name)

    return SearchConfigResponse.model_validate(db_config)


@router.get("/{config_id}", response_model=SearchConfigResponse)
async def get_search_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
) -> SearchConfigResponse:
    """Get a single search configuration.

    Args:
        config_id: The config ID to retrieve

    Returns:
        Search config details

    Raises:
        HTTPException: 404 if config not found
    """
    log.info("get_search_config_request", config_id=config_id)

    result = await db.execute(
        select(SearchConfig).where(SearchConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")

    return SearchConfigResponse.model_validate(config)


@router.put("/{config_id}", response_model=SearchConfigResponse)
async def update_search_config(
    config_id: int,
    update: SearchConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> SearchConfigResponse:
    """Update a search configuration.

    Args:
        config_id: The config ID to update
        update: Fields to update

    Returns:
        Updated search config

    Raises:
        HTTPException: 404 if config not found
    """
    log.info("update_search_config_request", config_id=config_id)

    result = await db.execute(
        select(SearchConfig).where(SearchConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")

    # Update only provided fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    config.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(config)

    log.info("update_search_config_success", config_id=config_id)

    return SearchConfigResponse.model_validate(config)


@router.delete("/{config_id}", status_code=204)
async def delete_search_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a search configuration.

    Args:
        config_id: The config ID to delete

    Raises:
        HTTPException: 404 if config not found
    """
    log.info("delete_search_config_request", config_id=config_id)

    result = await db.execute(
        select(SearchConfig).where(SearchConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")

    await db.delete(config)

    log.info("delete_search_config_success", config_id=config_id)


@router.patch("/{config_id}/toggle", response_model=SearchConfigToggleResponse)
async def toggle_search_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
) -> SearchConfigToggleResponse:
    """Toggle a search config's enabled status.

    Args:
        config_id: The config ID to toggle

    Returns:
        Updated enabled status

    Raises:
        HTTPException: 404 if config not found
    """
    log.info("toggle_search_config_request", config_id=config_id)

    result = await db.execute(
        select(SearchConfig).where(SearchConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")

    config.enabled = not config.enabled
    config.updated_at = datetime.now(timezone.utc)

    await db.flush()

    log.info(
        "toggle_search_config_success",
        config_id=config_id,
        enabled=config.enabled,
    )

    return SearchConfigToggleResponse(id=config_id, enabled=config.enabled)
