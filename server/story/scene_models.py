import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

LEGACY_SCENE_KEYS = {"cap", "scene", "dia", "button_text", "buttonText", "btn", "conditions", "cond", "hiden", "hidden"}
LEGACY_DIALOG_KEYS = {"id", "chr", "txt", "opt", "act", "next"}
LEGACY_OPTION_KEYS = {"optn", "dia"}


def _deepcopy(value: Any) -> Any:
    return copy.deepcopy(value)


def _strip_private_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        for key in list(payload.keys()):
            if isinstance(key, str) and key.startswith("__"):
                del payload[key]
            else:
                _strip_private_fields(payload[key])
    elif isinstance(payload, list):
        for item in payload:
            _strip_private_fields(item)
    return payload


@dataclass
class DialogueOption:
    name: str
    dialogues: List["DialogueNode"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DialogueOption":
        opt_name = str(payload.get("optn", ""))
        raw_dialogues = payload.get("dia") or []
        dialogues = [DialogueNode.from_dict(d) for d in raw_dialogues if isinstance(d, dict)]
        return cls(name=opt_name, dialogues=dialogues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "optn": self.name,
            "dia": [dialogue.to_dict() for dialogue in self.dialogues],
        }


@dataclass
class DialogueNode:
    identifier: int
    character: int
    text: str
    options: List[DialogueOption] = field(default_factory=list)
    act: Optional[Dict[str, Any]] = None
    next_scene: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DialogueNode":
        identifier = int(payload.get("id", 0) or 0)
        character = int(payload.get("chr", 0) or 0)
        text = str(payload.get("txt", ""))
        options_payload = payload.get("opt") or []
        options = [DialogueOption.from_dict(opt) for opt in options_payload if isinstance(opt, dict)]
        act_payload = payload.get("act") if isinstance(payload.get("act"), dict) else None
        next_scene = payload.get("next")
        return cls(
            identifier=identifier,
            character=character,
            text=text,
            options=options,
            act=_deepcopy(act_payload) if act_payload else None,
            next_scene=str(next_scene) if isinstance(next_scene, str) else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        node: Dict[str, Any] = {
            "id": self.identifier,
            "chr": self.character,
            "txt": self.text,
        }
        if self.options:
            node["opt"] = [option.to_dict() for option in self.options]
        if self.act:
            node["act"] = _deepcopy(self.act)
        if self.next_scene:
            node["next"] = self.next_scene
        return node


@dataclass
class SceneModel:
    name: str
    caption: str
    dialogues: List[DialogueNode]
    button_text: Optional[str] = None
    conditions: Optional[Any] = None
    hidden: Optional[bool] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SceneModel":
        sanitized = _strip_private_fields(_deepcopy(payload or {}))
        name = str(sanitized.get("scene") or sanitized.get("Scene") or "")
        caption = str(sanitized.get("cap", ""))
        raw_dialogues = sanitized.get("dia") or []
        dialogues = [DialogueNode.from_dict(d) for d in raw_dialogues if isinstance(d, dict)]

        button_text = sanitized.get("button_text") or sanitized.get("buttonText") or sanitized.get("btn")
        if isinstance(button_text, str):
            button_text = button_text.strip()

        conditions = sanitized.get("conditions") or sanitized.get("cond")
        hidden = sanitized.get("hiden") if "hiden" in sanitized else sanitized.get("hidden")
        hidden_value = bool(hidden) if isinstance(hidden, (bool, int)) else None

        extras = {
            key: _deepcopy(value)
            for key, value in sanitized.items()
            if key not in LEGACY_SCENE_KEYS and key != "scene" and key != "cap" and key != "dia" and key != "pgrs"
        }

        return cls(
            name=name,
            caption=caption,
            dialogues=dialogues,
            button_text=button_text if button_text else None,
            conditions=_deepcopy(conditions) if isinstance(conditions, (dict, list)) else None,
            hidden=hidden_value,
            extras=extras,
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "scene": self.name,
            "cap": self.caption,
            "dia": [dialogue.to_dict() for dialogue in self.dialogues],
        }
        if self.button_text:
            data["button_text"] = self.button_text
        if self.conditions is not None:
            data["conditions"] = _deepcopy(self.conditions)
        if self.hidden is not None:
            data["hiden"] = self.hidden
        data.update(_deepcopy(self.extras))
        return data


def scene_models_from_payload(payload: Any) -> List[SceneModel]:
    if not isinstance(payload, list):
        return []
    models: List[SceneModel] = []
    for raw_scene in payload:
        if isinstance(raw_scene, dict):
            models.append(SceneModel.from_dict(raw_scene))
    return models


def scene_models_to_plain(models: List[SceneModel]) -> List[Dict[str, Any]]:
    return [model.to_dict() for model in models]
