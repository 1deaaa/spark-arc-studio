from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from core.auth import get_current_user, require_admin, user_db
from agents import skill_packs


skill_packs_router = APIRouter(prefix="/api/agents/skills", tags=["agent-skills"])


class ImportUrlRequest(BaseModel):
    url: str
    publish_global: bool = False


def _serialized_imports(items: list[skill_packs.ImportedSkill]) -> list[dict]:
    return [
        {
            "skill_id": item.skill_id,
            "name": item.name,
            "description": item.description,
            "domain": item.domain,
            "compatibility_status": item.compatibility_status,
            "duplicate_of": item.duplicate_of,
        }
        for item in items
    ]


@skill_packs_router.get("")
async def list_skills(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    is_admin = user_db.is_user_admin(user_id)
    return {
        "success": True,
        "is_admin": is_admin,
        "skills": [
            skill_packs.public_skill_record(item)
            for item in skill_packs.list_effective_skills(user_id)
        ],
    }


@skill_packs_router.post("/upload")
async def upload_skill(
    file: UploadFile = File(...),
    publish_global: bool = Form(False),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    if publish_global and not user_db.is_user_admin(user_id):
        raise HTTPException(status_code=403, detail={"success": False, "message": "需要管理员权限"})
    raw = await file.read()
    try:
        imported = skill_packs.import_skill_upload(
            user_id,
            file.filename or "SKILL.md",
            raw,
            domain="global" if publish_global else "user",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"success": False, "message": str(exc)}) from exc
    return {"success": True, "skills": _serialized_imports(imported)}


@skill_packs_router.post("/import-url")
async def import_skill_from_url(
    data: ImportUrlRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    if data.publish_global and not user_db.is_user_admin(user_id):
        raise HTTPException(status_code=403, detail={"success": False, "message": "需要管理员权限"})
    try:
        imported = skill_packs.import_skill_from_url(
            user_id,
            data.url,
            domain="global" if data.publish_global else "user",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"success": False, "message": str(exc)}) from exc
    return {"success": True, "skills": _serialized_imports(imported)}


@skill_packs_router.delete("/{skill_id:path}")
async def delete_skill(skill_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    try:
        deleted = skill_packs.delete_user_skill(
            user_id,
            skill_id,
            is_admin=user_db.is_user_admin(user_id),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"success": False, "message": str(exc)}) from exc
    return {"success": True, "deleted": deleted}


@skill_packs_router.post("/{skill_id:path}/publish")
async def publish_skill(skill_id: str, current_user: dict = Depends(require_admin)):
    user_id = current_user["user_id"]
    skill = skill_packs.find_skill(user_id, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail={"success": False, "message": "Skill 不存在"})
    if skill.get("domain") == "global":
        return {"success": True, "skill": skill}
    raw = skill_packs.read_raw_skill_markdown(user_id, skill_id)
    imported = skill_packs.import_skill_markdown(
        user_id,
        raw,
        domain="global",
        source_url=str(skill.get("source_url") or ""),
    )
    return {"success": True, "skills": _serialized_imports([imported])}
