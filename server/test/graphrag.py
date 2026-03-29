"""
GraphRAG smoke CLI.

该脚本不再包含独立实现，而是直接调用正式模块：agents.graphrag.GraphRAGService。
用途：本地快速验证 build/query/status/reset 四个动作。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.graphrag import GraphRAGService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SparkArc GraphRAG smoke CLI")
    parser.add_argument("--user-id", default="1", help="用户 ID")
    parser.add_argument("--project", required=True, help="项目名")
    parser.add_argument(
        "--action",
        choices=["build", "query", "status", "reset"],
        default="status",
        help="执行动作",
    )
    parser.add_argument("--question", default="", help="query 动作的问题")
    parser.add_argument(
        "--mode",
        choices=["local", "global", "drift"],
        default="drift",
        help="query 模式",
    )
    parser.add_argument("--force-rebuild", action="store_true", help="build 时强制重建")
    parser.add_argument("--max-hops", type=int, default=2, help="query 图遍历跳数")
    parser.add_argument("--max-edges", type=int, default=56, help="query 最大关系条数")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    service = GraphRAGService(user_id=str(args.user_id), project_name=args.project)

    if args.action == "status":
        print(json.dumps(service.get_status(), ensure_ascii=False, indent=2))
        return 0

    if args.action == "reset":
        print(json.dumps(service.reset(), ensure_ascii=False, indent=2))
        return 0

    if args.action == "build":
        print(json.dumps(service.build_index(force_rebuild=args.force_rebuild), ensure_ascii=False, indent=2))
        return 0

    if not args.question.strip():
        print("query 动作必须传 --question")
        return 2

    print(
        json.dumps(
            service.query(
                question=args.question,
                query_mode=args.mode,
                max_hops=args.max_hops,
                max_edges=args.max_edges,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
