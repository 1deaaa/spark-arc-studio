import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents import agent_tools
from agents.tools import registry
from agents.tools.search import search_project


def test_agent_tools_facade_exposes_registry_single_source_of_truth():
    assert agent_tools.get_tools_for_agent is registry.get_tools_for_agent
    assert agent_tools.TOOLS_BY_NAME is registry.TOOLS_BY_NAME
    assert agent_tools.SCRIPTWRITER_TOOLS is registry.SCRIPTWRITER_TOOLS
    assert agent_tools.SHARED_READ_TOOLS is registry.SHARED_READ_TOOLS


def test_agent_tools_facade_exposes_search_cache_helpers_from_split_module():
    assert agent_tools._get_search_results is not None
    assert agent_tools._store_search_results is not None
    assert agent_tools.search_project is search_project
