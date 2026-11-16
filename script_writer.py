"""Gemini-backed Burmese recap script generation is implemented in bot.py.

This module remains as a small import-compatible wrapper for future integrations.
"""
from bot import generate_recap

async def generate_recap_outline(topic: str) -> str:
    return await generate_recap(topic)
