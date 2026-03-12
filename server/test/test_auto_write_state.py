from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.routes.auto_write_state import (  # noqa: E402
    build_auto_write_chapter_plan,
    build_chapter_output_filename,
    default_auto_write_state,
)


def test_build_chapter_output_filename_normalizes_title_for_arc():
    assert build_chapter_output_filename('第1章：风雪/夜归', 'arc') == '第1章风雪_夜归.arc'


def test_default_auto_write_state_starts_idle():
    state = default_auto_write_state()
    assert state['status'] == 'idle'
    assert state['runId'] == ''
    assert state['generatedFiles'] == []


def test_build_auto_write_chapter_plan_marks_existing_outputs(monkeypatch):
    outline = {
        'nodes': [
            {'type': 'chapter', 'chapter': 1, 'title': '第一章'},
            {'type': 'chapter', 'chapter': 2, 'title': '第二章'},
        ]
    }

    monkeypatch.setattr(
        'agents.routes.auto_write_state.get_project_stories_path',
        lambda user_id, project_name: '/virtual/stories',
    )
    monkeypatch.setattr(
        'agents.routes.auto_write_state.os.path.exists',
        lambda path: path.endswith('第二章.arc'),
    )

    plan = build_auto_write_chapter_plan('1', 'demo', outline, export_format='arc')

    assert plan == [
        {
            'chapterIndex': 0,
            'chapterNumber': 1,
            'chapterTitle': '第一章',
            'filename': '第一章.arc',
            'exists': False,
        },
        {
            'chapterIndex': 1,
            'chapterNumber': 2,
            'chapterTitle': '第二章',
            'filename': '第二章.arc',
            'exists': True,
        },
    ]