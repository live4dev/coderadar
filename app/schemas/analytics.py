"""Schemas for analytics (treemap tree)."""
from __future__ import annotations
from pydantic import BaseModel


class TreemapNode(BaseModel):
    """One node in the treemap tree (recursive)."""
    name: str
    value: int | float
    id: int | None = None
    type: str | None = None  # "project" | "repository" | "root"
    children: list[TreemapNode] | None = None
