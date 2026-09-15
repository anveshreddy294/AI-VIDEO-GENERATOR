from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
from pathlib import Path

# Add parent directory to path to enable imports
sys.path.insert(0, str(Path(__file__).parent))

from video_generator import start_video_generation, get_job_status

# Get absolute path to frontend directory
FRONTEND_DIR = Path(__file__).parent / 'frontend'

app = Flask(__name__, 
            static_folder=str(FRONTEND_DIR),
            static_url_path='/static')
CORS(app)

# Ensure media directory exists (at project root level)
PROJECT_ROOT = Path(__file__).parent.parent
MEDIA_DIR = PROJECT_ROOT / 'media'
os.makedirs(MEDIA_DIR, exist_ok=True)


@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/api/generate', methods=['POST'])
def generate_video():
    """Start video generation"""
    try:
        data = request.get_json()
        
        topic = data.get('topic')
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        llm_provider = data.get('llm_provider', 'auto')
        enable_tts = data.get('enable_tts', True)
        
        # Start video generation
        job_id = start_video_generation(topic, enable_tts, llm_provider)
        
        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'message': 'Video generation started'
        }), 202
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    """Get video generation progress"""
    job = get_job_status(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job)


@app.route('/media/<path:filename>')
def serve_media(filename):
    """Serve generated media files"""
    return send_from_directory(MEDIA_DIR, filename)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Topic2Manim API'
    })


if __name__ == '__main__':
    print("=" * 80)
    print("Topic2Manim Server")
    print("=" * 80)
    print("Starting Flask server...")
    print("Access the web interface at: http://localhost:5000")
    print("=" * 80)
    print("\nNOTE: Auto-reload is disabled to prevent job state loss during video generation")
    print("      Restart the server manually if you make code changes.\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False,  # Disable auto-reload to prevent losing job state
        threaded=True
    )
