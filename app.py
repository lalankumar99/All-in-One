import os
import re
import uuid
import shutil
import tempfile
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    send_from_directory
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import imageio_ffmpeg


# ==========================================
# MEDIA VAULT - FLASK BACKEND
# ==========================================

app = Flask(__name__)

# Configure maximum upload size (100 MB) and preserve JSON key order
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
app.config["JSON_SORT_KEYS"] = False

APP_NAME = "MediaVault"
VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_FILE = BASE_DIR / "index.html"

UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

MAX_FILE_SIZE = 100 * 1024 * 1024
MAX_CONVERSION_SECONDS = 180

ALLOWED_EXTENSIONS = {
    "mp4", "mov", "mkv", "webm", "m4v",
    "mp3", "wav", "m4a", "aac", "flac", "ogg"
}

SUPPORTED_PLATFORMS = {
    "Instagram": [
        "instagram.com",
        "www.instagram.com"
    ],
    "Facebook": [
        "facebook.com",
        "www.facebook.com",
        "fb.watch"
    ],
    "YouTube": [
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be"
    ]
}

# Bundled FFmpeg executable provided by imageio-ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def allowed_file(filename):
    """Check whether the filename has an allowed media extension."""
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def detect_platform(url):
    """Validate and detect supported social media platforms from a URL."""
    try:
        parsed = urlparse(url.strip())

        if parsed.scheme not in ("http", "https"):
            return None

        hostname = (parsed.hostname or "").lower().rstrip(".")

        if not hostname:
            return None

        # Reject suspicious hostnames and lookalike domains
        for platform, domains in SUPPORTED_PLATFORMS.items():
            if hostname in domains:
                return platform

        return None

    except (ValueError, AttributeError):
        return None


def valid_media_file(file):
    """Verify the uploaded file object has a safe and supported filename."""
    if not file or not file.filename:
        return False

    filename = secure_filename(file.filename)

    if not filename or not allowed_file(filename):
        return False

    return True


def api_error(message, status=400):
    """Return a standardized JSON error response."""
    return jsonify({
        "success": False,
        "error": message
    }), status


# ==========================================
# HOME / FRONTEND
# ==========================================

@app.route("/")
def home():
    """Serve index.html if present, or fallback status JSON."""
    if FRONTEND_FILE.exists():
        return send_from_directory(BASE_DIR, "index.html")

    return jsonify({
        "app": APP_NAME,
        "version": VERSION,
        "status": "Backend running",
        "message": "Place index.html in the project root."
    })


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/api/health", methods=["GET"])
def health():
    """Return service health and configuration metadata."""
    return jsonify({
        "success": True,
        "app": APP_NAME,
        "version": VERSION,
        "status": "online",
        "backend": "Flask",
        "converter": "FFmpeg",
        "max_upload_size": "100 MB"
    })


# ==========================================
# PLATFORM DETECTION
# ==========================================

@app.route("/api/detect", methods=["POST"])
def detect():
    """Detect whether a provided URL belongs to Instagram, Facebook, or YouTube."""
    data = request.get_json(silent=True) or {}

    url = str(data.get("url", "")).strip()

    if not url:
        return api_error("Please provide a URL.")

    if len(url) > 2048:
        return api_error("URL is too long.")

    platform = detect_platform(url)

    if not platform:
        return jsonify({
            "success": True,
            "detected": False,
            "platform": None,
            "message": "Unsupported or invalid platform URL."
        })

    return jsonify({
        "success": True,
        "detected": True,
        "platform": platform,
        "download_supported": False,
        "open_url": url,
        "message": (
            f"{platform} link detected. "
            "Use the platform's official download options "
            "or an authorized integration."
        )
    })


# ==========================================
# MEDIA CONVERSION TO MP3
# ==========================================

@app.route("/api/convert", methods=["POST"])
def convert():
    """Convert an uploaded video or audio file into a 192kbps stereo MP3."""
    work_dir = None
    cleanup_immediately = True

    try:
        if "file" not in request.files:
            return api_error("No media file uploaded.")

        media = request.files["file"]

        if not valid_media_file(media):
            return api_error("Unsupported media file format.")

        original_name = secure_filename(media.filename)

        # Create a unique temporary working directory inside uploads/
        work_dir = tempfile.mkdtemp(
            prefix="mediavault_",
            dir=str(UPLOAD_FOLDER)
        )

        input_path = Path(work_dir) / original_name
        output_name = f"MediaVault_{uuid.uuid4().hex[:12]}.mp3"
        output_path = Path(work_dir) / output_name

        # Save uploaded file
        media.save(str(input_path))

        if not input_path.exists() or input_path.stat().st_size == 0:
            return api_error("Uploaded file is empty.")

        if input_path.stat().st_size > MAX_FILE_SIZE:
            return api_error("File exceeds the upload limit.")

        # FFmpeg conversion command
        command = [
            FFMPEG_PATH,
            "-nostdin",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-threads", "1",
            "-i", str(input_path),
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-metadata", "title=MediaVault Audio",
            str(output_path)
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=MAX_CONVERSION_SECONDS,
            check=False
        )

        if result.returncode != 0:
            error_message = result.stderr.strip()
            app.logger.warning(
                "FFmpeg conversion failed: %s",
                error_message[:1000]
            )
            return api_error(
                "Unable to convert this file. "
                "Check that it is a valid media file."
            )

        if not output_path.exists() or output_path.stat().st_size == 0:
            return api_error("MP3 conversion failed.")

        # Send converted file to user
        response = send_file(
            output_path,
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name="MediaVault_Audio.mp3"
        )

        # Defer cleanup until after the file stream response closes
        cleanup_immediately = False
        temp_dir_to_clean = work_dir
        response.call_on_close(
            lambda: shutil.rmtree(temp_dir_to_clean, ignore_errors=True)
        )

        return response

    except subprocess.TimeoutExpired:
        return api_error(
            "Conversion timed out. Try a smaller media file.",
            408
        )

    except RequestEntityTooLarge:
        return api_error("Maximum upload size is 100 MB.", 413)

    except Exception:
        app.logger.exception("Media conversion error")
        return api_error(
            "An internal server error occurred.",
            500
        )

    finally:
        # Ensure temporary files are always cleaned up if an error occurred before streaming
        if cleanup_immediately and work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


# ==========================================
# API ERROR HANDLERS
# ==========================================

@app.errorhandler(413)
def file_too_large(error):
    return api_error("Maximum upload size is 100 MB.", 413)


@app.errorhandler(404)
def not_found(error):
    return api_error("API endpoint not found.", 404)


@app.errorhandler(405)
def method_not_allowed(error):
    return api_error("HTTP method not allowed.", 405)


@app.errorhandler(500)
def internal_error(error):
    return api_error("Internal server error.", 500)


# ==========================================
# APPLICATION START
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
)
