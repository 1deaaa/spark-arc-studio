"""
逻辑审核 - 剧本评审

严格评估编剧提供的剧本初稿，检查 AI 味残留、视角一致性、逻辑连贯性等。
"""
import json
from typing import Any, Dict, List, Optional

from llm.agen_matchbox import matchbox
from llm.agen_matchbox.reasoning_compat import extract_visible_text_from_plain_text
from agents.agent_utils import load_prompt
from agents.prompt_layout import build_prompt_messages
from .communication import SparkBaseAgent


class CriticAgent(SparkBaseAgent):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_critic", user_id=user_id)
        # Critic 主要走 invoke 路径（非流式），使用 llm.invoke() 调用
        self.llm = matchbox().get_user_llm(str(user_id), agent_name="agent_critic")

    def _stringify_style_profile(self, style_profile: object = None) -> str:
        if style_profile is None:
            return "用户未提供参考风格档案。请根据剧本内容和主题，自行判断最合适的文笔风格作为审稿参照。"
        if isinstance(style_profile, str):
            return style_profile
        return json.dumps(style_profile, ensure_ascii=False, indent=2)

    def _serialize_review_target(
        self,
        script_nodes: Optional[List[Dict[str, Any]]] = None,
        script_text: str = "",
    ) -> str:
        if script_text and script_text.strip():
            return script_text.strip()
        if script_nodes:
            return json.dumps(script_nodes, ensure_ascii=False, indent=2)
        return "（未提供待审阅正文）"

    def _normalize_grade(self, raw: Any, default: str = "B") -> str:
        if isinstance(raw, str):
            grade = raw.strip().upper()
            if grade in {"S", "A", "B", "C", "D"}:
                return grade
        if isinstance(raw, (int, float)):
            value = float(raw)
            if value >= 90:
                return "S"
            if value >= 80:
                return "A"
            if value >= 65:
                return "B"
            if value >= 45:
                return "C"
            return "D"
        return default

    def _normalize_dimension_grades(self, raw: Any) -> Dict[str, str]:
        base = {
            "structure_ai_flavor": "B",
            "language_ai_flavor": "B",
            "dialogue_ai_flavor": "B",
            "literary_flatness": "B",
            "logic_and_character": "B",
        }
        if not isinstance(raw, dict):
            return base
        alias_map = {
            "structure_ai_flavor": ["structure_ai_flavor", "structure", "structure_grade", "structure_score"],
            "language_ai_flavor": ["language_ai_flavor", "language", "language_grade", "language_score"],
            "dialogue_ai_flavor": ["dialogue_ai_flavor", "dialogue", "dialogue_grade", "dialogue_score"],
            "literary_flatness": ["literary_flatness", "literary", "literary_grade", "literary_score"],
            "logic_and_character": ["logic_and_character", "logic", "character_consistency", "logic_grade", "logic_score"],
        }
        for key, aliases in alias_map.items():
            for alias in aliases:
                if alias in raw:
                    base[key] = self._normalize_grade(raw.get(alias), default=base[key])
                    break
        return base

    def _normalize_hits(self, raw_hits: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_hits, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for item in raw_hits:
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence")
            if isinstance(evidence, dict):
                evidence = [evidence]
            if not isinstance(evidence, list):
                evidence = []
            normalized.append(
                {
                    "feature": str(item.get("feature") or item.get("feature_name") or "unknown_issue"),
                    "severity": str(item.get("severity") or "minor"),
                    "reason": str(item.get("reason") or item.get("why_it_feels_ai") or ""),
                    "suggestion": str(item.get("suggestion") or ""),
                    "evidence": [e for e in evidence if isinstance(e, dict)],
                    "fix_ticket": item.get("fix_ticket") if isinstance(item.get("fix_ticket"), dict) else None,
                }
            )
        return normalized

    def _collect_fix_tickets(self, raw_fix_tickets: Any, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tickets: List[Dict[str, Any]] = []
        if isinstance(raw_fix_tickets, list):
            tickets.extend([item for item in raw_fix_tickets if isinstance(item, dict)])
        for hit in hits:
            ticket = hit.get("fix_ticket")
            if isinstance(ticket, dict):
                tickets.append(ticket)
        return tickets

    def _normalize_review_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        decision = str(result.get("decision") or "").strip().upper()
        overall_grade = self._normalize_grade(
            result.get("overall_grade") or result.get("grade") or result.get("score"),
            default="A" if str(result.get("status", "")).upper() == "APPROVE" else "C",
        )
        if decision not in {"PASS", "REVISE", "REJECT"}:
            if overall_grade in {"S", "A"}:
                decision = "PASS"
            elif overall_grade == "B":
                decision = "REVISE"
            else:
                decision = "REJECT"

        legacy_status = "APPROVE" if decision in {"PASS", "REVISE"} else "REJECT"
        critique = str(result.get("critique") or result.get("summary") or result.get("overall_summary") or "").strip()
        specific_feedback = str(result.get("specific_feedback") or result.get("feedback") or result.get("rewrite_brief") or "").strip()

        dimension_grades = self._normalize_dimension_grades(
            result.get("dimension_grades") or result.get("dimension_scores")
        )
        hits = self._normalize_hits(result.get("hits"))
        rewrite_brief = str(result.get("rewrite_brief") or specific_feedback or critique).strip()
        overall_summary = str(
            result.get("overall_summary")
            or (result.get("overall_risk") or {}).get("summary")
            or critique
            or specific_feedback
            or ""
        ).strip()
        fix_tickets = self._collect_fix_tickets(result.get("fix_tickets"), hits)

        return {
            "decision": decision,
            "overall_grade": overall_grade,
            "overall_summary": overall_summary,
            "dimension_grades": dimension_grades,
            "hits": hits,
            "fix_tickets": fix_tickets,
            "rewrite_required": bool(result.get("rewrite_required", decision != "PASS")),
            "rewrite_brief": rewrite_brief,
            # legacy / compatibility fields
            "status": legacy_status,
            "critique": critique,
            "specific_feedback": specific_feedback,
            "feedback": rewrite_brief,
        }

    def _normalize_public_share_review_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        decision = str(result.get("decision") or result.get("status") or "").strip().upper()
        if decision not in {"PASS", "REJECT"}:
            decision = "PASS" if result.get("allow") is True else "REJECT"

        reason = str(
            result.get("reason")
            or result.get("summary")
            or result.get("message")
            or ("审核通过" if decision == "PASS" else "未明确满足公开分享要求")
        ).strip()

        raw_risk_tags = result.get("risk_tags") or result.get("tags") or []
        raw_evidence = result.get("evidence") or []

        risk_tags = [
            str(item).strip()
            for item in raw_risk_tags
            if str(item).strip()
        ] if isinstance(raw_risk_tags, list) else []
        evidence = [
            str(item).strip()
            for item in raw_evidence
            if str(item).strip()
        ] if isinstance(raw_evidence, list) else []

        return {
            "decision": decision,
            "reason": reason,
            "risk_tags": risk_tags,
            "evidence": evidence,
        }

    def _invoke_prompt_json(self, prompts: Dict[str, Any]) -> Dict[str, Any]:
        messages = build_prompt_messages(system_prompt=prompts["system"], user_prompt=prompts["user"])

        response = self.llm.invoke(messages)
        raw_content = response.content if isinstance(response.content, str) else str(response.content)
        content = self._clean_json_block(
            extract_visible_text_from_plain_text(raw_content)
        )
        return json.loads(content)

    def evaluate(
        self,
        script_nodes: Optional[List[Dict[str, Any]]] = None,
        script_text: str = "",
        context: str = "",
        guidance: str = "",
        worldview: str = "",
        roles: str = "",
        style_profile: object = None,
        review_target: str = "",
        story_tags: str = "",
    ) -> Dict[str, Any]:
        """
        结构化评审当前文本。
        """
        serialized_script = self._serialize_review_target(
            script_nodes=script_nodes,
            script_text=script_text,
        )
        style_profile_text = self._stringify_style_profile(style_profile)

        # 从 YAML 加载提示词
        prompts = load_prompt(
            'critic',
            context=context,
            guidance=guidance or "",
            worldview=worldview or "",
            roles=roles or "",
            style_profile=style_profile_text or "",
            script=serialized_script,
            review_target=review_target or "当前文本/场景",
            story_tags=story_tags or "",
        )

        try:
            result = self._invoke_prompt_json(prompts)
            return self._normalize_review_result(result)
            
        except Exception as e:
            raise RuntimeError(f"[Critic] 评审失败: {e}")

    def moderate_public_share(
        self,
        content_text: str,
        review_target: str = "公开分享内容",
    ) -> Dict[str, Any]:
        prompts = load_prompt(
            "critic",
            "public_share_moderation",
            review_target=review_target or "公开分享内容",
            content=content_text.strip() or "（未提供待审核文本）",
        )

        try:
            result = self._invoke_prompt_json(prompts)
            return self._normalize_public_share_review_result(result)
        except Exception as e:
            raise RuntimeError(f"[Critic] 公开分享审核失败: {e}")

    def _clean_json_block(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline+1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

