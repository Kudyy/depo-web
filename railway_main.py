#!/usr/bin/env python3
"""
Railway deployment script for Depo Web Application
Clean web-only entry point without GUI dependencies
"""
import os
import sys

def main():
    # Get port from Railway environment
    port = os.environ.get("PORT", "8000")
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"🚀 Starting Depo Web Application on {host}:{port}")
    
    # Import and run uvicorn
    try:
        import uvicorn
        from server import app
        
        uvicorn.run(
            app,
            host=host,
            port=int(port),
            log_level="info",
            access_log=True
        )
    except ImportError as e:
        print(f"❌ Import error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()