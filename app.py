import os
import shutil
import tempfile
from flask import Flask, request, jsonify, send_file, render_template, after_this_request
from flask_cors import CORS
from yt_dlp import YoutubeDL

app = Flask(__name__)
CORS(app)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert_video():
    data = request.json or {}
    video_url = data.get('url')
    requested_format = data.get('format', 'mp3').lower()

    if not video_url:
        return jsonify({"error": "Missing video URL"}), 400

    if requested_format not in ['mp3', 'mp4']:
        return jsonify({"error": "Unsupported format type. Use mp3 or mp4."}), 400

    # Temporary directory for this download instance
    temp_dir = tempfile.mkdtemp()

    # Automatically clean up the temp directory after the response is sent
    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            app.logger.error(f"Error cleaning up temp directory: {e}")
        return response

    try:
        if requested_format == 'mp3':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'concurrent_fragment_downloads': 5,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': True,
                'no_warnings': True
            }
        else:  # MP4 configuration
            ydl_opts = {
                # Prefer H.264 video + AAC audio (plays everywhere),
                # then fall back to whatever is best if unavailable.
                'format': (
                    'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/'
                    'best[ext=mp4][vcodec^=avc1]/'
                    'bestvideo+bestaudio/best'
                ),
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'concurrent_fragment_downloads': 5,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True
            }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

            # yt-dlp reports the final file path (after merging/post-processing)
            target_path = None
            downloads = info.get('requested_downloads') or []
            if downloads:
                target_path = downloads[0].get('filepath')

            # Fallback: search the temp dir for a file with the requested extension
            if not target_path or not os.path.exists(target_path):
                matching_files = [
                    os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                    if f.endswith(f".{requested_format}")
                ]
                if matching_files:
                    target_path = matching_files[0]
                else:
                    return jsonify({"error": "Output target file missing after conversion."}), 500

            mimetype = "audio/mpeg" if requested_format == 'mp3' else "video/mp4"
            download_name = os.path.basename(target_path)

            # Stream file directly from disk instead of loading into RAM
            return send_file(
                target_path,
                mimetype=mimetype,
                as_attachment=True,
                download_name=download_name
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("Backend server active at http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)