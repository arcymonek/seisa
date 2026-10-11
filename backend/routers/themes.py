"""Colour themes for the UI: the list for the footer switch and the generated stylesheet (see backend/themes.py)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from backend.themes import load_themes, public_list, render_css

router = APIRouter()


@router.get("/themes")
async def list_themes() -> list[dict]:
    return public_list(load_themes())


@router.get("/themes.css")
async def themes_css() -> Response:
    return Response(content=render_css(load_themes()), media_type="text/css")
