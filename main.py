import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from routers.search import router as search_router
from routers.admin import router as admin_router
from services.multilingual_lexicon import MultilingualLexiconService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("km_lexicon")

# Initialize global multilingual lexicon service
multilingual_lexicon = MultilingualLexiconService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting km_lexicon engine (Phase 4) with Multilingual Lexicon support...")
    try:
        # Pre-warm / validate multilingual lexicon service
        test_lookup = multilingual_lexicon.get_translation("computer", "km")
        logger.info(f"MultilingualLexiconService active. Test lookup 'computer' -> {test_lookup}")
    except Exception as e:
        logger.error(f"MultilingualLexiconService initialization warning: {e}")
    yield
    logger.info("Shutting down km_lexicon engine...")

app = FastAPI(
    title="km_lexicon Engine",
    description="Khmer Computational Linguistics & 5-Language Multilingual Search API",
    version="4.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core routers
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
    return {
        "status": "ok",
        "phase": 4,
        "multilingual_engine": "active",
        "supported_languages": ["en", "km", "th", "lo", "vi"]
    }

@app.get("/api/v1/translate")
async def translate_term(term: str, target: str = "km"):
    """Direct application-level translation lookup across supported languages."""
    result = multilingual_lexicon.get_translation(term, target)
    if not result:
        raise HTTPException(status_code=404, detail=f"Term '{term}' not found for target language '{target}'")
    return {"term": term, "target_language": target, "translation": result}

@app.post("/api/v1/multilingual")
async def get_all_translations(payload: dict):
    """Retrieve 5-language translations anchored by English."""
    term = payload.get("term")
    if not term:
        raise HTTPException(status_code=400, detail="Missing 'term' in request body")
    translations = multilingual_lexicon.get_all_translations(term)
    if not translations:
        raise HTTPException(status_code=404, detail=f"Term '{term}' not found in multilingual lexicon")
    return {"anchor_term": term, "translations": translations}
