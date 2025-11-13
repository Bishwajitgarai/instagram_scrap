from app import app
from app.core.config import settings
import uvicorn
if __name__ == "__main__":
    uvicorn.run(
        app, 
        host=settings.API_HOST, 
        port=settings.API_PORT,
        access_log=True,
        timeout_keep_alive=60,
        timeout_graceful_shutdown=30
    )
