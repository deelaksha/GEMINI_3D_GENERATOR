# Running in production

The built-in server (`python start.py`) is for development: it runs every request in one process, so one large
compile slows everyone down. In production run the app under gunicorn:

```bash
pip install -r requirements.txt
python -m gunicorn -c gunicorn.conf.py app:app
```

`gunicorn.conf.py` starts one worker process per CPU core (`WEB_WORKERS`), each with 4 threads (`WEB_THREADS`), and a
worker timeout longer than the 15-minute compile cap, so large designs are never cut off. Put it behind a reverse
proxy (nginx, Caddy) for HTTPS, and let the proxy pass streaming responses through unbuffered
(nginx: `proxy_buffering off;` for `/api/v1/canvas/compile-stream`) with a read timeout of at least 960 s.

| Setting | Default | Meaning |
|---|---|---|
| `PORT` / `BIND` | `5000` / `0.0.0.0:$PORT` | where the server listens |
| `WEB_WORKERS` | CPU cores | compiles that can run at the same time |
| `WEB_THREADS` | 4 | requests per worker served while one compiles |
| `BOARD_TIME_BUDGET` | 90 | compile seconds per 900 boards (larger designs get more, at most 15 minutes) |
| `BOARD_INSTANCE_DIR` | `./instance` | designs and the compile cache (`compile-cache/`, shared by all workers) |
| `BOARD_RATE_LIMIT` | 600 | requests per minute per user |
| `BOARD_COMPILE_SLOTS` | 2 | compiles one user may run at the same time (more answer 429 "busy") |
| `BOARD_AI_PER_HOUR` | 20 | paid AI calls (Generate / Fix with AI) per user per hour |
| `BOARD_AI_PER_DAY` | 300 | paid AI calls per worker process per day: the real cap on the AI bill, since any visitor gets a session |
| `BOARD_COMPILE_TOTAL` | 2 x CPU cores (at least 4) | compiles one worker process runs at the same time (more answer 503 with `Retry-After`) |
| `TRUST_PROXY` | unset | number of reverse proxies in front; set it only behind a proxy, so HTTPS is detected and the session cookie stays `Secure` |

Health check: `GET /api/v1/healthz` answers `{"ok": true}` (503 when the design store is unreachable).
Dependencies for running tests: `pip install -r requirements-dev.txt`.

Notes
- The editor compiles twice (a fast pass for the 3D view, then cut sheets). The fast pass leaves a snapshot in
  `instance/compile-cache/` so the second request only adds the production work, whichever worker serves it.
- The rate limiter and design locks are per worker process; with several workers a user's limit is per worker.
- Size limits: designs up to 100 million characters, requests up to 128 MB.
