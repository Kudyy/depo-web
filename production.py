# production.py - Production server configuration
import uvicorn
from server import app
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=4 if settings.is_production else 1,
        reload=not settings.is_production,
        access_log=True,
        log_level="info" if settings.is_production else "debug"
    )