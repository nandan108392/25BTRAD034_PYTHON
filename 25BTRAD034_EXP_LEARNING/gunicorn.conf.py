"""
CityOS Gunicorn Production Configuration
-----------------------------------------
Configures worker processes, connection timeouts, and logging for production deployment.
"""

import os
import multiprocessing

# Network binding
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# Concurrency model: (2 x CPUs) + 1 workers recommended for I/O bound workloads
workers = int(os.environ.get("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 4)))
threads = int(os.environ.get("GUNICORN_THREADS", 2))
worker_class = "gthread"

# Connection management & timeouts
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Process naming
proc_name = "cityos_production"
