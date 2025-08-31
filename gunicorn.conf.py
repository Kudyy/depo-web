import os

# Railway configuration
bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
workers = int(os.environ.get('WEB_CONCURRENCY', 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "depo-web"

# Server mechanics
preload_app = True
daemon = False