import os
import shutil
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from yt_dlp import YoutubeDL


app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get("PORT", 5000))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_video():
    data = request.get_json(silent=True) or {}

    video_url = data.get("url")
    requested_format = str(data.get("format", "mp3")).lower()

    if not video_url:
        return jsonify({
            "error": "Missing video URL."
        }), 400

    if requested_format not in ("mp3", "mp4"):
        return jsonify({
            "error": "Unsupported format. Use mp3 or mp4."
        }), 400

    temp_dir = tempfile.mkdtemp(prefix="video_convert_")

    try:
        output_template = os.path.join(
            temp_dir,
            "%(title)s.%(ext)s"
        )

        # Helps YouTube extraction avoid some browser checks
        youtube_options = {
            "extractor_args": {
                "youtube": {
                    "player_client": ["android"]
                }
            }
        }

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

                **youtube_options
            }

        else:
            ydl_opts = {
                "format": (
                    "bestvideo[ext=mp4][vcodec^=avc1]+"
                    "bestaudio[ext=m4a]/"
                    "best[ext=mp4][vcodec^=avc1]/"
                    "bestvideo+bestaudio/best"
                ),

                "outtmpl": output_template,

                "noplaylist": True,

                "concurrent_fragment_downloads": 5,

                "merge_output_format": "mp4",

                "quiet": True,
                "no_warnings": True,

                **youtube_options
            }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        files = [
            path
            for path in Path(temp_dir).iterdir()
            if path.is_file()
            and path.suffix.lower() == f".{requested_format}"
        ]

        if not files:
            return jsonify({
                "error": "Output file missing after conversion."
            }), 500

        target_path = files[0]

        mimetype = (
            "audio/mpeg"
            if requested_format == "mp3"
            else "video/mp4"
        )

        response = send_file(
            target_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=target_path.name
        )

        @response.call_on_close
        def cleanup():
            shutil.rmtree(temp_dir, ignore_errors=True)

        return response

    except Exception as error:
        shutil.rmtree(temp_dir, ignore_errors=True)

        app.logger.exception("Conversion failed")

        return jsonify({
            "error": str(error)
        }), 500


if __name__ == "__main__":
    print(f"Backend running on port {PORT}")

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
