# Re-export FastAPI app for uvicorn entrypoints
from .app import app, create_app

__all__ = ["app", "create_app"]
