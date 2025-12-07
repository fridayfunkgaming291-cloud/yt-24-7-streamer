import os
import random
import time
import subprocess
from pathlib import Path

# ---------------- CONFIG ----------------
VIDEOS_DIR = Path("/mnt/shared/videos")
EXCLUSIVE_DIR = Path("/mnt/shared/exclusive_videos")
SHARED_DIR = Path("/mnt/shared")
FORCE_FILE = SHARED_DIR / "force_next.txt"
NOW_PLAYING = SHARED_DIR / "now_playing.txt"
SHUFFLE_MODE_FILE = SHARED_DIR / "shuffle_mode.txt"
CUSTOM_ORDER_FILE = SHARED_DIR / "custom_order.txt"
LIST_THEN_RANDOM_FILE = SHARED_DIR / "list_then_random.txt"
PAUSED_FLAG = SHARED_DIR / "paused.flag"
PAUSE_IMAGE = Path("/mnt/shared/paused_image.png")

# YouTube RTMP URL (set in Render environment variables)
RTMP_URL = os.environ.get("RTMP_URL")
if not RTMP_URL:
    raise Exception("Please set the RTMP_URL environment variable")

# ffmpeg settings
RES = "854x480"
VBITRATE = "800k"
MAXRATE = "1000k"
ABITRATE = "96k"
PRESET = "veryfast"

# ---------------- Helper Functions ----------------
def get_playlist():
    # All videos in regular folder
    files = [f for f in VIDEOS_DIR.iterdir() if f.is_file()]
    mode = "random"
    if SHUFFLE_MODE_FILE.exists():
        mode = SHUFFLE_MODE_FILE.read_text().strip()

    # EXCLUSIVE videos are never in auto playlist
    if mode == "alphabetical":
        files.sort(key=lambda f: f.name.lower())
    elif mode == "custom" and CUSTOM_ORDER_FILE.exists():
        order = [line.strip() for line in CUSTOM_ORDER_FILE.read_text().splitlines()]
        files.sort(key=lambda f: order.index(f.name) if f.name in order else len(order))
    elif mode == "list_then_random" and LIST_THEN_RANDOM_FILE.exists():
        list_videos = [f.strip() for f in LIST_THEN_RANDOM_FILE.read_text().splitlines()]
        # Listed videos first (if they exist)
        listed_files = [VIDEOS_DIR / v for v in list_videos if (VIDEOS_DIR / v).exists()]
        remaining_files = [f for f in files if f not in listed_files]
        random.shuffle(remaining_files)
        files = listed_files + remaining_files
    else:
        random.shuffle(files)
    return files

def stream_file(file_path):
    print(f"Streaming: {file_path.name}")
    NOW_PLAYING.write_text(file_path.name)
    ffmpeg_cmd = [
        "ffmpeg", "-re", "-i", str(file_path),
        "-vf", f"scale={RES}:flags=lanczos",
        "-c:v", "libx264", "-preset", PRESET, "-b:v", VBITRATE, "-maxrate", MAXRATE, "-bufsize", "2000k",
        "-g", "48", "-keyint_min", "48",
        "-c:a", "aac", "-b:a", ABITRATE, "-ar", "44100",
        "-f", "flv", RTMP_URL
    ]
    subprocess.run(ffmpeg_cmd)

def show_pause_image():
    if not PAUSE_IMAGE.exists():
        print("Paused image not found, waiting...")
        time.sleep(5)
        return
    NOW_PLAYING.write_text("PAUSED")
    ffmpeg_cmd = [
        "ffmpeg", "-loop", "1", "-i", str(PAUSE_IMAGE),
        "-vf", f"scale={RES}:flags=lanczos",
        "-c:v", "libx264", "-preset", PRESET, "-b:v", VBITRATE, "-maxrate", MAXRATE, "-bufsize", "2000k",
        "-t", "10",
        "-f", "flv", RTMP_URL
    ]
    subprocess.run(ffmpeg_cmd)

# ---------------- Main Loop ----------------
while True:
    # Pause check
    if PAUSED_FLAG.exists():
        print("Stream paused, showing placeholder")
        show_pause_image()
        time.sleep(1)
        continue

    # Force check (normal or exclusive)
    if FORCE_FILE.exists():
        fn = FORCE_FILE.read_text().strip()
        FORCE_FILE.unlink()
        forced_file = (VIDEOS_DIR / fn)
        if not forced_file.exists():
            forced_file = (EXCLUSIVE_DIR / fn)
        if forced_file.exists():
            stream_file(forced_file)
            continue
        else:
            print(f"Force file {fn} not found, skipping")
            continue

    # Get current playlist
    playlist = get_playlist()
    if not playlist:
        print("No videos found in regular folder, sleeping 5s")
        time.sleep(5)
        continue

    for f in playlist:
        if PAUSED_FLAG.exists() or FORCE_FILE.exists():
            break
        stream_file(f)
