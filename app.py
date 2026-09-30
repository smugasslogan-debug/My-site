import os
import shutil
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from yt_dlp import YoutubeDL


app = Flask(__name__)
CORS(app)

# Render provides PORT automatically.
# Locally, this defaults to 5000.
PORT = int(os.environ.get("PORT", 5000))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_video():
    data = request.get_json(silent=True) or {}

    video_url = data.get("url")
    requested_format = str(data.get("format", "mp3")).lower()

    # Validate URL
    if not video_url:
        return jsonify({
            "error": "Missing video URL."
        }), 400

    # Validate requested format
    if requested_format not in ("mp3", "mp4"):
        return jsonify({
            "error": "Unsupported format. Use mp3 or mp4."
        }), 400

    # Create a temporary directory for this conversion.
    temp_dir = tempfile.mkdtemp(prefix="video_convert_")

    try:
        output_template = os.path.join(
            temp_dir,
            "%(title)s.%(ext)s"
        )

        if requested_format == "mp3":
            ydl_opts = {
                "format": "bestaudio/best",

                "outtmpl": output_template,

                "noplaylist": True,

                "concurrent_fragment_downloads": 5,

                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "128",
                    }
                ],

                "quiet": True,
                "no_warnings": True,

                # Avoid unnecessary metadata/files.
                "writethumbnail": False,
                "writeinfojson": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
            }

        else:
            ydl_opts = {
                # Prefer MP4/H.264 + M4A when available.
                "format": (
                    "bestvideo[ext=mp4][vcodec^=avc1]+"
                    "bestaudio[ext=m4a]/"
                    "best[ext=mp4][vcodec^=avc1]/"
                    "bestvideo+bestaudio/best"
                ),

                "outtmpl": output_template,

                "noplaylist": True,

                "concurrent_fragment_downloads": 5,

                # Make the final merged file MP4.
                "merge_output_format": "mp4",

                "quiet": True,
                "no_warnings": True,

                "writethumbnail": False,
                "writeinfojson": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
            }

        # Download / convert.
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Find the final output file.
        expected_extension = f".{requested_format}"

        output_files = [
            path
            for path in Path(temp_dir).iterdir()
            if path.is_file()
            and path.suffix.lower() == expected_extension
        ]

        if not output_files:
            return jsonify({
                "error": "Conversion completed, but the output file could not be found."
            }), 500

        # There should normally only be one output file.
        target_path = output_files[0]

        # Pick the correct MIME type.
        if requested_format == "mp3":
            mimetype = "audio/mpeg"
        else:
            mimetype = "video/mp4"

        # Prevent weird filenames from causing problems.
        download_name = target_path.name

        response = send_file(
            target_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_name
        )

        # Delete the temporary directory after the response is finished.
        @response.call_on_close
        def cleanup():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as error:
                app.logger.error(
                    "Failed to clean temporary directory: %s",
                    error
                )

        return response

    except Exception as error:
        # Clean up immediately if conversion fails.
        shutil.rmtree(temp_dir, ignore_errors=True)

        app.logger.exception("Conversion failed")

        return jsonify({
            "error": str(error)
        }), 500


@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "error": "Request is too large."
    }), 413


@app.errorhandler(404)
def page_not_found(error):
    return jsonify({
        "error": "Endpoint not found."
    }), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "error": "Internal server error."
    }), 500


if __name__ == "__main__":
    print(f"Backend server active on http://127.0.0.1:{PORT}")

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
