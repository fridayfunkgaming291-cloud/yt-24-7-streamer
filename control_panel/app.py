from flask import Flask, render_template_string, request, redirect, url_for, flash
from pathlib import Path
import os

# CONFIG
VIDEOS_DIR = Path("/mnt/shared/videos")
EXCLUSIVE_DIR = Path("/mnt/shared/exclusive_videos")
SHARED_DIR = Path("/mnt/shared")
FORCE_FILE = SHARED_DIR / "force_next.txt"
NOW_PLAYING = SHARED_DIR / "now_playing.txt"
SHUFFLE_MODE_FILE = SHARED_DIR / "shuffle_mode.txt"
CUSTOM_ORDER_FILE = SHARED_DIR / "custom_order.txt"
LIST_THEN_RANDOM_FILE = SHARED_DIR / "list_then_random.txt"
PAUSED_FLAG = SHARED_DIR / "paused.flag"

PASSWORD = os.environ.get("STREAM_PANEL_PASSWORD", "change_me")
SECRET = os.environ.get("STREAM_PANEL_SECRET", "secret_key_here")

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mkv", ".flv", ".mov", ".webm", ".swf"}

app = Flask(__name__)
app.secret_key = SECRET

# ---------------- Helper Functions ----------------
def allowed_file(fn):
    return Path(fn).suffix.lower() in ALLOWED_EXTENSIONS

def list_videos():
    return sorted([f.name for f in VIDEOS_DIR.iterdir() if f.is_file() and allowed_file(f.name)])

def list_exclusive_videos():
    return sorted([f.name for f in EXCLUSIVE_DIR.iterdir() if f.is_file() and allowed_file(f.name)])

def require_login(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*a, **kw):
        pw = request.cookies.get("auth")
        if pw != PASSWORD:
            return redirect(url_for("login"))
        return func(*a, **kw)
    return wrapper

# ---------------- Routes ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password")
        if pw == PASSWORD:
            resp = redirect(url_for("index"))
            resp.set_cookie("auth", PASSWORD)
            return resp
        flash("Bad password")
    return render_template_string("""
    <h2>Login</h2>
    <form method=post>
        <input type=password name=password>
        <input type=submit value=Login>
    </form>
    """)

@app.route("/logout")
def logout():
    resp = redirect(url_for("login"))
    resp.delete_cookie("auth")
    return resp

@app.route("/")
@require_login
def index():
    now = NOW_PLAYING.read_text() if NOW_PLAYING.exists() else "None"
    videos = list_videos()
    exclusive = list_exclusive_videos()
    shuffle_mode = SHUFFLE_MODE_FILE.read_text().strip() if SHUFFLE_MODE_FILE.exists() else "random"
    list_then_random_txt = LIST_THEN_RANDOM_FILE.read_text() if LIST_THEN_RANDOM_FILE.exists() else ""
    return render_template_string("""
    <h1>Stream Control Panel</h1>
    <p>Now playing: {{now}}</p>

    <h2>Shuffle Mode</h2>
    <form method="post" action="{{url_for('set_shuffle')}}">
        <select name="mode">
            <option value="random" {% if shuffle_mode=='random' %}selected{%endif%}>Random</option>
            <option value="alphabetical" {% if shuffle_mode=='alphabetical' %}selected{%endif%}>Alphabetical</option>
            <option value="custom" {% if shuffle_mode=='custom' %}selected{%endif%}>Custom</option>
            <option value="list_then_random" {% if shuffle_mode=='list_then_random' %}selected{%endif%}>List then Random</option>
        </select>
        <input type=submit value="Set">
    </form>

    <h3>List-Then-Random Videos</h3>
    <form method="post" action="{{url_for('set_list_then_random')}}">
        <textarea name="list_txt" rows="6" cols="40">{{ list_then_random_txt }}</textarea><br>
        <input type=submit value="Save List">
    </form>

    <h2>Videos</h2>
    <form method="post" action="{{url_for('upload')}}" enctype="multipart/form-data">
        <input type=file name=file multiple>
        <label>
            <input type=checkbox name=exclusive> Exclusive (force-only)
        </label>
        <input type=submit value="Upload">
    </form>

    <h3>Normal Videos</h3>
    <ul>
    {% for v in videos %}
        <li>{{v}}
            <form style="display:inline" method="post" action="{{url_for('force_next', video=v)}}"><button>Force Next</button></form>
        </li>
    {% endfor %}
    </ul>

    <h3>Exclusive Videos (force-only)</h3>
    <ul>
    {% for v in exclusive %}
        <li>{{v}}
            <form style="display:inline" method="post" action="{{url_for('force_next', video=v)}}"><button>Force Next</button></form>
        </li>
    {% endfor %}
    </ul>

    <form method="post" action="{{url_for('pause_resume')}}">
        {% if paused %}<button>Resume Stream</button>{% else %}<button>Pause Stream</button>{% endif %}
    </form>

    <p><a href="{{url_for('logout')}}">Logout</a></p>
    """, videos=videos, exclusive=exclusive, now=now, shuffle_mode=shuffle_mode, list_then_random_txt=list_then_random_txt, paused=PAUSED_FLAG.exists())

@app.route("/upload", methods=["POST"])
@require_login
def upload():
    files = request.files.getlist("file")
    exclusive = request.form.get("exclusive") == "on"
    dest_dir = EXCLUSIVE_DIR if exclusive else VIDEOS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f and allowed_file(f.filename):
            dest = dest_dir / f.filename
            f.save(dest)
    flash("Uploaded successfully")
    return redirect(url_for("index"))

@app.route("/force_next/<video>", methods=["POST"])
@require_login
def force_next(video):
    FORCE_FILE.write_text(video)
    flash(f"Will play {video} next")
    return redirect(url_for("index"))

@app.route("/set_shuffle", methods=["POST"])
@require_login
def set_shuffle():
    mode = request.form.get("mode", "random")
    SHUFFLE_MODE_FILE.write_text(mode)
    flash(f"Shuffle mode set to {mode}")
    return redirect(url_for("index"))

@app.route("/set_list_then_random", methods=["POST"])
@require_login
def set_list_then_random():
    txt = request.form.get("list_txt", "")
    LIST_THEN_RANDOM_FILE.write_text(txt)
    flash("List-then-random updated")
    return redirect(url_for("index"))

@app.route("/pause_resume", methods=["POST"])
@require_login
def pause_resume():
    if PAUSED_FLAG.exists():
        PAUSED_FLAG.unlink()
        flash("Stream resumed")
    else:
        PAUSED_FLAG.touch()
        flash("Stream paused")
    return redirect(url_for("index"))

# ---------------- Main ----------------
if __name__ == "__main__":
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    EXCLUSIVE_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
