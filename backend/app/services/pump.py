"""泵站运行业务规则：机组状态、轴承温度与运行电流分开保存，每条机组编号的数据只落在自己那条上。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pump"
REQUIRED_FIELDS = ["机组编号", "所属厂站", "水泵型号"]
STATUSES = ["运行", "备用", "故障", "已停机"]
STOPPED = "已停机"
RUNTIME_FIELDS = ["轴承温度", "运行电流", "累计运行时间"]


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    """列表、详情与运行弹窗共用同一份判断：机组状态以 status 字段为准。"""
    data = dict(row)
    data["机组状态"] = str(row.get("status") or "备用")
    return data


class PumpService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("机组编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_serialize(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return _serialize(row) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        code = str(values.get("机组编号")).strip()
        if any(str(row.get("机组编号")) == code for row in store.rows(MODULE)):
            return None, f"机组编号 {code} 已经登记过，不能重复建档"
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ["机组编号", "所属厂站", "水泵型号", "额定流量"]:
            entry[field] = values.get(field)
        entry["status"] = "备用"
        entry["pending"] = True
        entry["abnormal"] = False
        for field in RUNTIME_FIELDS:
            entry[field] = None  # 运行数据留空，等首次提交，不借用别的机组的值
        rows.append(entry)
        return _serialize(entry), "水泵机组已登记，初始状态为备用"

    def submit_runtime(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """提交运行数据：只更新本机组的轴承温度、运行电流与累计运行时间，不动其他机组。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"水泵机组 {entry_id} 不存在或已归档"
        code = entry.get("机组编号", entry_id)
        if entry.get("status") == STOPPED:
            return None, f"机组 {code} 已停机，只能查看，不能再改动运行数据"
        hours = values.get("累计运行时间")
        if hours is None or not str(hours).strip():
            return None, "累计运行时间为空，不允许提交：请按当班抄表数填写累计运行时间后再提交"
        for field in RUNTIME_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = value  # 空值视为未填写，保留原值，避免把已填内容冲掉
        return _serialize(entry), f"机组 {code} 的运行数据已保存"

    def stop_unit(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """停机：状态同步成已停机，列表、详情与运行弹窗看到的是同一个结论。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"水泵机组 {entry_id} 不存在或已归档"
        code = entry.get("机组编号", entry_id)
        if entry.get("status") == STOPPED:
            return None, f"机组 {code} 已经是已停机状态，无需重复停机"
        entry["status"] = STOPPED
        entry["pending"] = False
        return _serialize(entry), f"机组 {code} 已停机，机组状态已同步为已停机"
