"""泵站运行业务规则：状态流转、运行数据分项保存与停机锁定都收在这里。

口径约定：
- ``status`` 是机组状态的唯一来源，列表、详情、运行记录弹窗都以它为准；
- 运行电流、累计运行时间、轴承温度是三个互相独立的字段，分别取值、分别落库，
  不允许其中一项把另一项覆盖掉；
- “已停机”是终态：只可查看，动作与运行数据修改一律拒绝。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "pump"
REQUIRED_FIELDS = ["机组编号", "所属厂站", "水泵型号", "额定流量"]
# 运行数据三项各自独立保存，互不覆盖
RUN_FIELDS = ["运行电流", "累计运行时间", "轴承温度"]

STATUS_RUNNING = "运行"
STATUS_STANDBY = "备用"
STATUS_FAULT = "故障"
STATUS_STOPPED = "已停机"
STATUS_ORDER = [STATUS_RUNNING, STATUS_STANDBY, STATUS_FAULT, STATUS_STOPPED]
# 终态集合：进入这些状态后机组只能查看，不能再改动
LOCKED_STATUSES = {STATUS_STOPPED}

# 动作到目标状态的映射，停机动作必须把状态同步成“已停机”
ACTION_RULES = {
    "切换备用": STATUS_STANDBY,
    "标记故障": STATUS_FAULT,
    "故障停机": STATUS_STOPPED,
    "启用备用": STATUS_RUNNING,
}


def _sync_status(entry: dict[str, Any]) -> dict[str, Any]:
    """把内部 status 同步到展示字段，保证列表/详情/弹窗的结论完全一致。"""
    entry["机组状态"] = entry.get("status")
    return entry


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
        page_rows = rows[start:start + size]
        return [_sync_status(dict(row)) for row in page_rows], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return _sync_status(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        # 三项运行数据与运行记录列表各自独立初始化，不与基础档案共用容器
        for field in RUN_FIELDS:
            entry[field] = ""
        entry["run_records"] = []
        entry["status"] = STATUS_RUNNING
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _sync_status(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"水泵机组 {entry_id} 不存在或已归档"
        current = str(entry.get("status") or "")
        if current in LOCKED_STATUSES:
            return None, f"机组 {entry.get('机组编号')} 已停机，状态已锁定，只能查看不能改动"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于泵站运行可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["机组状态"] = target
        entry["pending"] = target not in LOCKED_STATUSES
        entry["abnormal"] = target == STATUS_FAULT
        return entry, f"水泵机组 {entry.get('机组编号')} 已{action}，状态同步为「{target}」"

    def submit_run_record(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """提交某台机组的运行数据。

        数据按机组编号（id）定位、按字段分别落库；累计运行时间是必填项；
        已停机机组拒绝一切修改。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"水泵机组 {entry_id} 不存在或已归档"
        unit_no = str(entry.get("机组编号") or entry_id)
        if str(entry.get("status") or "") in LOCKED_STATUSES:
            return None, f"机组 {unit_no} 已停机，运行数据已锁定，只能查看不能修改"

        runtime = str(values.get("累计运行时间") or "").strip()
        if not runtime:
            return None, "累计运行时间为空，无法提交运行数据：请先填写该机组的累计运行时间"

        # 三项分别取值、分别写入本条机组，杜绝一条机组的内容落到另一条上
        for field in RUN_FIELDS:
            entry[field] = str(values.get(field) or "").strip()

        records = entry.setdefault("run_records", [])
        # 记录内快照机组编号与型号，弹窗展示时不会被上一条机组的信息盖掉
        records.append({
            "记录时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "机组编号": entry.get("机组编号"),
            "水泵型号": entry.get("水泵型号"),
            "运行电流": entry["运行电流"],
            "累计运行时间": entry["累计运行时间"],
            "轴承温度": entry["轴承温度"],
            "机组状态": entry.get("status"),
        })
        return _sync_status(entry), f"机组 {unit_no} 的运行数据已提交"
