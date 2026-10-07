import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from routers.search import router as search_router
from routers.admin import router as admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("km_lexicon")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting km_lexicon engine (Phase 4)...")
    yield
    logger.info("Shutting down km_lexicon engine...")

app = FastAPI(
    title="km_lexicon Engine",
    description="Khmer Computational Linguistics & Search API",
    version="4.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router, prefix="/api/v1")
app.include_router(admin_router)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    elif os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "km_lexicon API running. Access /docs for API schema."}

@app.get("/health")
async def health_check():
    return {"status": "ok", "phase": 4}
