from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException
from app.server.browser_manager import InstagramScraper
from app.core.config import settings
import os,time
import asyncio
# Global scraper instance
scraper = InstagramScraper()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Instagram Scraper...")
    try:
        await scraper.initialize()
        print("Instagram Scraper ready!")
    except Exception as e:
        print(f"Failed to initialize scraper: {e}")
        print("API will start but scraper may not be functional")
    yield
    print("Shutting down Instagram Scraper...")
    await scraper.close()

from app.core.config import settings, limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# Create FastAPI app
app = FastAPI(
    title="Instagram GraphQL Scraper",
    description="High-performance Instagram GraphQL API scraper with persistent sessions",
    version="1.0.0",
    lifespan=lifespan
)

# Add limiter to state and register exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Import routes
from app.routes.v1.routes import v1_routers

# Include routers with versioning
app.include_router(v1_routers, prefix="/api/v1", tags=["v1"])

@app.get("/")
async def root():
    return {
        "message": "Instagram GraphQL Scraper API is running",
        "status": "ready" if scraper.is_initialized else "initializing",
        "version": "1.0.0",
        "endpoints": {
            "user": "GET /api/v1/scrape/{username}",
            "reels": "GET /api/v1/scrape/reels/{username}",
            "status": "GET /api/v1/status",
            "reload": "POST /api/v1/reload",
            "docs": "GET /docs"
        }
    }


@app.get("/status")
async def get_status():
    """Get scraper status"""
    status_info = {
        "status": "ready" if scraper.is_initialized else "not_initialized",
        "is_initialized": scraper.is_initialized,
        "user_data_dir": scraper.user_data_dir,
        "headless": scraper.headless,
        "timestamp": time.time()
    }
    
    auth_file = os.path.join(scraper.user_data_dir, 'auth.json')
    status_info['auth_file_exists'] = os.path.exists(auth_file)
    
    return status_info

@app.post("/reload")
async def reload_scraper():
    """Reload the scraper"""
    try:
        await scraper.close()
        await asyncio.sleep(2)
        await scraper.initialize()
        return {
            "success": True,
            "message": "Scraper reloaded successfully",
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
        )