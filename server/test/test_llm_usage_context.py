from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from core.request_context import current_llm_usage_context
from llm.agen_matchbox.models import Base, UsageLogEntry
from llm.agen_matchbox.tracked_model import UsageTrackingCallback


def test_usage_tracking_records_current_chat_task_context():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    callback = UsageTrackingCallback(
        user_id="100",
        model_id=1,
        platform_id=1,
        model_name="test-model",
        platform_name="test-platform",
        session_maker=Session,
        agent_name="agent_director",
    )

    token = current_llm_usage_context.set("chat_task:task-123")
    try:
        callback._record_usage(prompt_tokens=11, completion_tokens=7, success=True)
    finally:
        current_llm_usage_context.reset(token)

    with Session() as session:
        row = session.query(UsageLogEntry).one()

    assert row.context_key == "chat_task:task-123"
    assert row.total_tokens == 18
