"""
Gunicorn configuration file for Zemicon Landing Cost Calculator.
Usage:
    gunicorn -c gunicorn.conf.py wsgi:app
"""
import multiprocessing
import os

# Server socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
backlog = 2048

# Worker processes
# Standard formula: (2 x $num_cores) + 1
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "-"   # stdout
errorlog = "-"    # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# Process naming
proc_name = "zemicon_landing_cost"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment and configure if terminating SSL directly in Gunicorn)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"
