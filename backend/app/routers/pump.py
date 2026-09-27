"""泵站运行接口：维护水泵机组，覆盖状态流转、运行数据分项提交与清单导出。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.pump import STATUS_ORDER, PumpService

router = APIRouter(prefix="/api/pump", tags=["泵站运行"])

service = PumpService()

LIST_FIELDS = ["机组编号", "所属厂站", "水泵型号", "额定流量", "运行电流", "累计运行时间", "轴承温度", "机组状态"]
STATUSES = STATUS_ORDER


# 注意：静态路径必须排在 /{entry_id} 之前，否则 export 会被当成机组编号
@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出泵站运行清单：返回当前全部机组的最新数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pump", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按机组编号检索"),
    status: str | None = Query(default=None, description="运行、备用、故障、已停机"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按机组编号与状态过滤泵站运行列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条水泵机组明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"水泵机组 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条水泵机组，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="水泵机组已登记", entry=entry)


@router.post("/{entry_id}/run-records", response_model=ActionResult)
def submit_run_record(entry_id: int, payload: EntryPayload) -> ActionResult:
    """提交单台机组的运行电流、累计运行时间与轴承温度；数据只落在该机组记录上。"""
    entry, message = service.submit_run_record(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单台水泵机组执行状态流转；已停机机组锁定，非法动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
