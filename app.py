import os
import sys
import logging
import tempfile
import mimetypes
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, render_template_string, request

from board_api.auth import KeyRing, SESSION_COOKIE, SESSION_TTL
from board_api.routes import bp as board_api_bp
from board_engine.store import DesignStore

# Ensure correct MIME types for modern ES modules and CSS
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/javascript', '.mjs')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('application/json', '.json')

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=None)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable static file caching during active development
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # bounded API payloads

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'), format='%(asctime)s %(levelname)s %(name)s: %(message)s')

def _writable_instance_dir():
    """BOARD_INSTANCE_DIR, else ./instance, else the system temp dir (read-only hosts such as Vercel)."""
    if os.environ.get('BOARD_INSTANCE_DIR'):
        return Path(os.environ['BOARD_INSTANCE_DIR'])
    for candidate in (BASE_DIR / 'instance', Path(tempfile.gettempdir()) / 'board-instance'):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / '.write-test'
            probe.write_text('ok')
            probe.unlink()
            if candidate != BASE_DIR / 'instance':
                logging.getLogger('board_api').warning(
                    'Project directory is read-only; using %s (data is per-instance and not persistent)', candidate)
            return candidate
        except OSError:
            continue
    raise RuntimeError('no writable directory for design storage; set BOARD_INSTANCE_DIR')


INSTANCE_DIR = _writable_instance_dir()
app.config['BOARD_STORE'] = DesignStore(INSTANCE_DIR / 'designs')
app.config['BOARD_KEYRING'] = KeyRing(str(INSTANCE_DIR))
app.config['BOARD_RATE_LIMIT'] = int(os.environ.get('BOARD_RATE_LIMIT', 600))
app.register_blueprint(board_api_bp)


def seed_example_designs():
    """Create the example boat through the real join pipeline if it does not exist yet."""
    store = app.config['BOARD_STORE']
    if not store.exists('boat'):
        from board_engine.examples.boat import build_design
        design, failures = build_design('boat')
        store.create(design, actor='seed')
        if failures:
            logging.getLogger('board_api').warning('boat seed: %d joints rejected', len(failures))


if os.environ.get('BOARD_SKIP_SEED') != '1':
    try:
        seed_example_designs()
    except Exception:  # a failed seed must never take the whole site down
        logging.getLogger('board_api').exception('could not seed example designs')


@app.after_request
def add_header(response):
    """Ensure no stale caching during interactive 3D model authoring and set CORS."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    if not request.path.startswith('/api/v1'):
        # Legacy read-only routes stay open; the board API grants no cross-origin access.
        response.headers['Access-Control-Allow-Origin'] = '*'
    return response


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
@app.route('/studio')
@app.route('/studio.html')
def page_studio():
    """Board Studio: 2D cut sheets + 3D assembly + validation + production (API-driven)."""
    response = send_from_directory(BASE_DIR, 'studio.html', mimetype='text/html')
    ring = app.config['BOARD_KEYRING']
    if not ring.session_valid(request.cookies.get(SESSION_COOKIE, '')):
        response.set_cookie(SESSION_COOKIE, ring.new_session(), max_age=SESSION_TTL, httponly=True,
                            samesite='Strict', secure=request.is_secure)
    return response


@app.route('/docs/<path:filename>')
def serve_docs(filename):
    return send_from_directory(BASE_DIR / 'docs', filename, mimetype='text/plain; charset=utf-8')


@app.route('/index.html')
@app.route('/assembly')
@app.route('/workbench')
def page_assembly():
    """Main 3D Assembly Workbench viewport."""
    return send_from_directory(BASE_DIR, 'index.html', mimetype='text/html')


@app.route('/inspector')
@app.route('/inspector.html')
def page_inspector():
    """Individual Part File 2D/3D Inspector."""
    return send_from_directory(BASE_DIR, 'inspector.html', mimetype='text/html')


@app.route('/manufacturing')
@app.route('/manufacturing.html')
def page_manufacturing():
    """2D Laser Cut Sheet Nesting Studio."""
    return send_from_directory(BASE_DIR, 'manufacturing.html', mimetype='text/html')


@app.route('/validation')
@app.route('/validation.html')
def page_validation():
    """Physical Fit Audit & Dependency Graph Validator."""
    return send_from_directory(BASE_DIR, 'validation.html', mimetype='text/html')


@app.route('/guide')
@app.route('/guide.html')
def page_guide():
    """Interactive Step-by-Step Construction Guide."""
    return send_from_directory(BASE_DIR, 'guide.html', mimetype='text/html')


# ============================================================================
# STATIC ASSET ROUTES (JS Modules, CSS, Assets)
# ============================================================================

@app.route('/js/<path:filename>')
def serve_js(filename):
    """Serve modular JavaScript files with explicit ES module MIME type."""
    response = send_from_directory(BASE_DIR / 'js', filename)
    if filename.endswith('.js') or filename.endswith('.mjs'):
        response.mimetype = 'application/javascript'
    return response


@app.route('/css/<path:filename>')
def serve_css(filename):
    """Serve CSS stylesheets."""
    response = send_from_directory(BASE_DIR / 'css', filename)
    if filename.endswith('.css'):
        response.mimetype = 'text/css'
    return response


@app.route('/ai-prompt.txt')
@app.route('/ai-promtp.txt')
@app.route('/ai_prompt.txt')
def serve_prompt_file():
    """Serve the AI prompt contest text file."""
    for fname in ['ai-prompt.txt', 'ai-promtp.txt', 'ai_prompt.txt']:
        p = BASE_DIR / fname
        if p.is_file():
            return send_from_directory(BASE_DIR, fname, mimetype='text/plain; charset=utf-8')
    return '', 200


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/api/prompt')
def api_prompt():
    """Returns the AI contest prompt contents."""
    for fname in ['ai-prompt.txt', 'ai-promtp.txt', 'ai_prompt.txt']:
        p = BASE_DIR / fname
        if p.is_file():
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if content.strip():
                    return jsonify({'success': True, 'content': content, 'filename': fname})
            except Exception as e:
                pass
    return jsonify({'success': True, 'content': '', 'filename': 'ai-prompt.txt'})

@app.route('/api/status')
def api_status():
    """Return backend status and environment details."""
    models_dir = BASE_DIR / 'js' / 'models'
    model_files = [f.name for f in models_dir.glob('*.js')] if models_dir.exists() else []

    firebase_config_path = BASE_DIR / 'js' / 'core' / 'firebase.js'

    return jsonify({
        'status': 'online',
        'platform': 'PuzzleCore 3D Physical Workbench',
        'server': 'Flask',
        'firebase': {
            'project_id': 'd-model-c2f16',
            'config_module': '/js/core/firebase.js',
            'config_present': firebase_config_path.exists(),
        },
        'python_version': sys.version.split()[0],
        'base_directory': str(BASE_DIR),
        'registered_model_files': model_files,
        'routes': [
            {'path': '/', 'name': '3D Assembly Workbench'},
            {'path': '/inspector', 'name': 'Part File Inspector'},
            {'path': '/manufacturing', 'name': '2D Cut Sheets'},
            {'path': '/validation', 'name': 'Fit Audit & Graph'},
            {'path': '/guide', 'name': 'Construction Guide'},
        ]
    })


@app.route('/api/models')
def api_models():
    """Discover available model scripts in js/models/."""
    models_dir = BASE_DIR / 'js' / 'models'
    models_info = []

    if models_dir.exists():
        for file_path in models_dir.glob('*.js'):
            if file_path.name in ['model-schema.js', 'registry.js']:
                continue
            stat = file_path.stat()
            models_info.append({
                'file_name': file_path.name,
                'size_kb': round(stat.st_size / 1024, 1),
                'modified': stat.st_mtime,
                'path': f'/js/models/{file_path.name}'
            })

    return jsonify({
        'count': len(models_info),
        'models': models_info
    })


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>404 — Page Not Found | PuzzleCore</title>
      <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-6">
      <div class="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl text-center space-y-4">
        <div class="text-4xl">🧩</div>
        <h1 class="text-xl font-bold text-amber-400">404 — Page Not Found</h1>
        <p class="text-xs text-slate-400">The requested route does not exist in PuzzleCore.</p>
        <div class="pt-2">
          <a href="/" class="inline-block px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-semibold transition">
            Return to 3D Assembly Workbench
          </a>
        </div>
      </div>
    </body>
    </html>
    '''), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)
