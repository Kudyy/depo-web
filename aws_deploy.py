# aws_deploy.py - AWS deployment configuration
import uvicorn
import os
from server import app

# AWS-specific configuration
PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0")
WORKERS = int(os.environ.get("WORKERS", 4))

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        workers=WORKERS,
        access_log=True,
        log_level="info"
    )