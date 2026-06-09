from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.models import ContentType, DataSource, SourceType, User, UserSettings
from app.schemas.schemas import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.services.crawlers.jin10 import (
    JIN10_CALENDAR_EXTERNAL_ID,
    JIN10_FLASH_EXTERNAL_ID,
    JIN10_NEWS_EXTERNAL_ID,
    JIN10_PROFILE_URL,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    existing_user = await db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        display_name=payload.display_name or payload.email.split("@")[0],
    )
    db.add(user)
    await db.flush()

    db.add(UserSettings(user_id=user.id))
    for source_def in (
        {
            "external_id": JIN10_FLASH_EXTERNAL_ID,
            "name": "市场快讯",
            "content_type": ContentType.NEWS,
            "source_config": {"mcp_tool": "list_flash", "jin10_section": "flash"},
        },
        {
            "external_id": JIN10_NEWS_EXTERNAL_ID,
            "name": "财经资讯",
            "content_type": ContentType.ARTICLE,
            "source_config": {"mcp_tool": "list_news", "jin10_section": "news"},
        },
        {
            "external_id": JIN10_CALENDAR_EXTERNAL_ID,
            "name": "财经日历",
            "content_type": ContentType.MARKET,
            "source_config": {"mcp_tool": "list_calendar", "jin10_section": "calendar"},
        },
    ):
        db.add(
            DataSource(
                user_id=user.id,
                source_type=SourceType.FINANCE_NEWS,
                external_id=source_def["external_id"],
                name=source_def["name"],
                profile_url=JIN10_PROFILE_URL,
                content_type=source_def["content_type"],
                source_config=source_def["source_config"],
            )
        )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
