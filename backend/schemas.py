"""Validated API request models."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginData(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ChatMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class MenuItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    size_ml: int | None = Field(default=None, gt=0, le=5000)
    price: int = Field(gt=0, le=1_000_000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Drink name cannot be empty")
        return value


class MenuUpdate(BaseModel):
    items: list[MenuItemInput] = Field(min_length=1, max_length=1000)


class MenuDocument(MenuUpdate):
    """Canonical on-disk menu; prices are whole Kazakhstani tenge."""
    model_config = ConfigDict(extra="forbid")

    currency: Literal["KZT"] = "KZT"
