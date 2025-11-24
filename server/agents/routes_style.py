from flask import Blueprint, request, jsonify
from core.auth import require_auth
from core.request_context import get_current_info, current_user_id, current_project_name
from .agent_style.workflow import save_style_profile
from .agent_style.utils import extract_text_from_epub
import os
import tempfile
from core.utils import get_project_path

style_bp = Blueprint('style_bp', __name__)

@style_bp.route('/api/ai/style-analyze', methods=['POST'])
@require_auth
@get_current_info
def analyze_style():
    """
    Style Agent: Analyze uploaded file and generate style profile.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    user_id = current_user_id.get()
    project_name = current_project_name.get() # Optional, style might be global or per project? 
    # Assuming style is per author (user) or per project. 
    # The workflow uses `author_id`. Let's use `user_id` or `project_name` as author_id.
    # For now, let's use `project_name` to keep it project-specific, or `user_id` if we want it global.
    # The user asked for "Style Agent", usually style is tied to an author.
    # But in this context, maybe we want to analyze a specific text to mimic its style for this project.
    # Let's use `project_name` as the ID for now so it doesn't conflict across projects if they want different styles.
    
    author_id = f"{user_id}_{project_name}" if project_name else f"{user_id}_default"

    try:
        # Save temp file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        chapters = []
        if suffix.lower() == '.epub':
            chapters = extract_text_from_epub(tmp_path, merge_short_chapters=True, min_chunk_size=3000)
        elif suffix.lower() == '.txt':
            with open(tmp_path, 'r', encoding='utf-8') as f:
                text = f.read()
                # Simple chunking for txt
                chapters = [text[i:i+5000] for i in range(0, len(text), 5000)]
        else:
            os.unlink(tmp_path)
            return jsonify({"error": "Unsupported file format. Please use .epub or .txt"}), 400

        os.unlink(tmp_path)

        if not chapters:
            return jsonify({"error": "Could not extract text from file"}), 400

        # Run analysis (force_regenerate=True to ensure we analyze this new file)
        # Note: This might take a while. Ideally should be async/background task.
        # For now, we'll run it synchronously but it might timeout.
        # In a real production app, use Celery/Redis Queue.
        
        style_profile = save_style_profile(
            author_id=author_id, 
            chapter_texts=chapters, 
            force_regenerate=True, 
            interactive=False, 
            parallel=True, # Use parallel for speed
            user_id=user_id # Pass user_id for LLM binding
        )

        if style_profile:
            return jsonify({"success": True, "style_profile": style_profile})
        else:
            return jsonify({"error": "Style analysis failed"}), 500

    except Exception as e:
        print(f"Error analyzing style: {e}")
        return jsonify({"error": str(e)}), 500

@style_bp.route('/api/ai/style-profile', methods=['GET'])
@require_auth
@get_current_info
def get_style_profile():
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    author_id = f"{user_id}_{project_name}" if project_name else f"{user_id}_default"
    
    from .agent_style.utils import load_style_profile_from_file
    profile = load_style_profile_from_file(author_id)
    
    if profile:
        return jsonify({"success": True, "style_profile": profile})
    else:
        return jsonify({"success": False, "message": "No style profile found"}), 404
