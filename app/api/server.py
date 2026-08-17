"""FastAPI Server application factory and static frontend mounting."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings, BASE_DIR
from app.api.routes import router as api_router, get_index

STATIC_DIR = BASE_DIR / "app" / "static"


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Citation-Grounded Research Agent with Hybrid Retrieval and Anti-Hallucination Guardrails.",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API endpoints
    app.include_router(api_router)

    # Ensure static directory exists
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "css").mkdir(exist_ok=True)
    (STATIC_DIR / "js").mkdir(exist_ok=True)

    # Mount static assets
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.on_event("startup")
    async def startup_event():
        """Pre-indexes documents on application boot."""
        try:
            index = get_index()
            print(f"Index ready: {len(index.documents)} documents, {len(index.chunks)} chunks.")
        except Exception as e:
            print(f"Startup indexing note: {e}")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        """Serves the research workbench UI."""
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {
            "message": f"Welcome to {settings.APP_NAME}",
            "docs": "/docs",
            "api": "/api/health"
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
