"""
Gunicorn configuration for production deployment.
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'gevent'  # Use gevent for async support
worker_connections = 1000
max_requests = 1000  # Restart workers after this many requests
max_requests_jitter = 50  # Randomize restart to avoid all workers restarting simultaneously
timeout = 120  # Worker timeout in seconds
keepalive = 5  # Keep-alive connections

# Threading
threads = int(os.getenv('GUNICORN_THREADS', 4))

# Server mechanics
daemon = False
pidfile = '/var/run/gunicorn/newsagent.pid'
user = os.getenv('GUNICORN_USER', 'www-data')
group = os.getenv('GUNICORN_GROUP', 'www-data')
tmp_upload_dir = None

# Logging
accesslog = '/var/log/gunicorn/newsagent_access.log'
errorlog = '/var/log/gunicorn/newsagent_error.log'
loglevel = os.getenv('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'newsagent'

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("Starting NewsAgent application...")


def when_ready(server):
    """Called just after the server is started."""
    print(f"NewsAgent is ready. Workers: {workers}")


def on_reload(server):
    """Called to recycle workers during a reload."""
    print("Reloading NewsAgent workers...")


def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    print(f"Worker {worker.pid} interrupted")


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker spawned (pid: {worker.pid})")


def pre_exec(server):
    """Called just before a new master process is forked."""
    print("Forking new master process...")


def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug(f"{req.method} {req.path}")


def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    pass


def worker_abort(worker):
    """Called when a worker times out."""
    print(f"Worker {worker.pid} timeout")
