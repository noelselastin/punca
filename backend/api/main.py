"""Entry point for uvicorn. Run from backend/:  uvicorn api.main:app --reload"""
from api.factory import create_app

app = create_app()
