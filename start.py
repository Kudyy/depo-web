#!/usr/bin/env python3
import os
import uvicorn
from server import app

if __name__ == "__main__":
    # Railway provides PORT as environment variable
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        app,  # Use the app directly instead of string
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )