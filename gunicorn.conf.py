"""Production web server for the board-design app.

    pip install gunicorn
    python -m gunicorn -c gunicorn.conf.py app:app

Several worker processes (one per CPU core by default) compile designs in parallel - Flask's built-in server runs
everything in one process. Each worker also has threads, so the streaming compile and quick requests are served
while a large design compiles. Compile snapshots are shared between workers through the instance directory.
Environment: PORT / BIND, WEB_WORKERS, WEB_THREADS, BOARD_TIME_BUDGET (seconds per 900 boards, default 90).
"""
import multiprocessing
import os

bind = os.environ.get('BIND', f"0.0.0.0:{os.environ.get('PORT', '5000')}")
workers = int(os.environ.get('WEB_WORKERS', multiprocessing.cpu_count()))
worker_class = 'gthread'
threads = int(os.environ.get('WEB_THREADS', 4))
timeout = 960                  # longer than the 15-minute compile cap, so a large compile is never killed mid-way
graceful_timeout = 30
keepalive = 5
max_requests = 300             # recycle workers now and then (memory of very large designs)
max_requests_jitter = 60
accesslog = '-'
errorlog = '-'
