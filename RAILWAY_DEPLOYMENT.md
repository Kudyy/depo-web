# Depo Web Railway Deployment

## Files to include in your Railway deployment:

### Core Application Files:
- server.py (main FastAPI application)
- api.py (API functions)
- utils.py (utility functions)
- depo.py (warehouse functions)
- TokenAlEntegra.py (token management)

### Templates and Static Files:
- templates/ (all HTML templates)
- static/ (all CSS and JS files)

### Configuration Files:
- requirements.txt (Python dependencies)
- Procfile (Railway startup command)
- runtime.txt (Python version)
- railway.json (Railway configuration)
- railway.toml (Railway settings)

### Data Files:
- output.json (order data)
- locations.csv (location data)
- token.txt (API token)

## Deployment Command:
Railway will automatically run: `uvicorn server:app --host 0.0.0.0 --port $PORT`

## Health Check:
Available at: `/health` endpoint