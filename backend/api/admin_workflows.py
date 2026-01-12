import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import User, WorkflowConfig
from ..schemas.schemas import (
    WorkflowBaseDefinition,
    WorkflowOverrideUpdate,
    WorkflowResponse,
)

router = APIRouter()
require_sysadmin = require_roles("SYSADMIN")


WORKFLOWS_DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "WORKFLOWS.md"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "workflow"


def _label_from_key(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").title()


def _parse_status_key(raw: str) -> List[str]:
    if "/" in raw:
        parts = [part.strip() for part in raw.split("/") if part.strip()]
        return parts or [raw.strip()]
    return [raw.strip()]


def _load_base_workflows() -> List[Dict[str, Any]]:
    if not WORKFLOWS_DOC_PATH.exists():
        return []

    text = WORKFLOWS_DOC_PATH.read_text(encoding="utf-8")
    workflows: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    in_status_section = False
    status_keys: Optional[set[str]] = None

    for line in text.splitlines():
        if line.startswith("## "):
            title = line[3:].strip()
            page_key = _slugify(title)
            current = {
                "workflow_key": page_key,
                "page_key": page_key,
                "title": title,
                "base": {
                    "statuses": [],
                    "transitions": [],
                    "notifications": [],
                },
            }
            workflows.append(current)
            in_status_section = False
            status_keys = set()
            continue

        if line.startswith("### "):
            in_status_section = line[4:].strip().lower() == "key states / statuses"
            continue

        if in_status_section and current and line.lstrip().startswith("- "):
            match = re.search(r"\*\*(.+?)\*\*", line)
            if not match:
                continue
            raw_key = match.group(1).strip()
            for key in _parse_status_key(raw_key):
                if not key:
                    continue
                if status_keys is not None and key in status_keys:
                    continue
                if status_keys is not None:
                    status_keys.add(key)
                current["base"]["statuses"].append(
                    {"key": key, "label": _label_from_key(key), "category": None}
                )

    return workflows


def _merge_list(
    base_items: Iterable[Dict[str, Any]],
    override_items: Iterable[Dict[str, Any]],
    key_fn,
) -> List[Dict[str, Any]]:
    base_list = list(base_items)
    overrides_list = list(override_items)
    base_by_key = {key_fn(item): item for item in base_list}
    overrides_by_key = {key_fn(item): item for item in overrides_list}
    merged: List[Dict[str, Any]] = []

    for item in base_list:
        key = key_fn(item)
        override = overrides_by_key.pop(key, None)
        if override:
            if not override.get("enabled", True):
                continue
            merged_item = {**item, **{k: v for k, v in override.items() if k != "enabled"}}
            merged.append(merged_item)
        else:
            merged.append(item)

    for override in overrides_by_key.values():
        if not override.get("enabled", True):
            continue
        merged.append({k: v for k, v in override.items() if k != "enabled"})

    return merged


def _merge_effective(base: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    overrides = overrides or {}
    base_statuses = base.get("statuses", [])
    base_transitions = base.get("transitions", [])
    base_notifications = base.get("notifications", [])
    override_statuses = overrides.get("statuses", []) or []
    override_transitions = overrides.get("transitions", []) or []
    override_notifications = overrides.get("notifications", []) or []

    statuses = _merge_list(base_statuses, override_statuses, lambda item: item.get("key"))
    transitions = _merge_list(
        base_transitions, override_transitions, lambda item: (item.get("from"), item.get("to"))
    )

    def notification_key(item: Dict[str, Any]) -> Tuple[Any, Any, Any, Any, Any]:
        trigger = item.get("trigger") or {}
        return (
            item.get("event"),
            trigger.get("from"),
            trigger.get("to"),
            trigger.get("status"),
            item.get("template_key"),
        )

    notifications = _merge_list(base_notifications, override_notifications, notification_key)
    return {
        "statuses": statuses,
        "transitions": transitions,
        "notifications": notifications,
    }


def _build_response(
    base_workflow: Dict[str, Any],
    override_record: Optional[WorkflowConfig],
) -> WorkflowResponse:
    overrides_json = override_record.overrides_json if override_record else None
    base_definition = WorkflowBaseDefinition(**base_workflow["base"])
    effective = _merge_effective(base_workflow["base"], overrides_json)
    return WorkflowResponse(
        workflow_key=base_workflow["workflow_key"],
        page_key=base_workflow["page_key"],
        title=base_workflow["title"],
        base=base_definition,
        overrides=overrides_json,
        effective=effective,
    )


@router.get("/workflows", response_model=Dict[str, List[WorkflowResponse]])
def list_workflows(
    db: Session = Depends(get_db),
    _: User = Depends(require_sysadmin),
) -> Dict[str, List[WorkflowResponse]]:
    base_workflows = _load_base_workflows()
    keys = [workflow["workflow_key"] for workflow in base_workflows]
    overrides = (
        db.query(WorkflowConfig).filter(WorkflowConfig.workflow_key.in_(keys)).all() if keys else []
    )
    override_map = {record.workflow_key: record for record in overrides}
    workflows = [
        _build_response(workflow, override_map.get(workflow["workflow_key"]))
        for workflow in base_workflows
    ]
    return {"workflows": workflows}


@router.get("/workflows/{workflow_key}", response_model=WorkflowResponse)
def get_workflow(
    workflow_key: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_sysadmin),
) -> WorkflowResponse:
    base_workflows = _load_base_workflows()
    base_map = {workflow["workflow_key"]: workflow for workflow in base_workflows}
    base_workflow = base_map.get(workflow_key)
    if not base_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    override = (
        db.query(WorkflowConfig).filter(WorkflowConfig.workflow_key == workflow_key).one_or_none()
    )
    return _build_response(base_workflow, override)


@router.put("/workflows/{workflow_key}", response_model=WorkflowResponse)
def update_workflow(
    workflow_key: str,
    payload: WorkflowOverrideUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_sysadmin),
) -> WorkflowResponse:
    base_workflows = _load_base_workflows()
    base_map = {workflow["workflow_key"]: workflow for workflow in base_workflows}
    base_workflow = base_map.get(workflow_key)
    if not base_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    overrides_payload = payload.overrides.dict(by_alias=True, exclude_none=True)
    override = (
        db.query(WorkflowConfig).filter(WorkflowConfig.workflow_key == workflow_key).one_or_none()
    )
    if override:
        override.overrides_json = overrides_payload
        override.updated_by_user_id = user.id if user else None
        override.page_key = base_workflow["page_key"]
    else:
        override = WorkflowConfig(
            workflow_key=workflow_key,
            page_key=base_workflow["page_key"],
            overrides_json=overrides_payload,
            updated_by_user_id=user.id if user else None,
        )
        db.add(override)
    db.commit()
    db.refresh(override)
    return _build_response(base_workflow, override)
