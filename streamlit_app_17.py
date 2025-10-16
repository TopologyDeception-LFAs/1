import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta, time as dtime
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo
import altair as alt

st.set_page_config(page_title="门店排班与轮值管理", layout="wide")

# ===== Time helpers (Melbourne) =====
TZ = ZoneInfo("Australia/Melbourne")
def now() -> datetime: return datetime.now(TZ)
def today_key() -> str: return now().strftime("%Y-%m-%d")
def fmt(dt: Optional[datetime]) -> str: return dt.strftime("%Y-%m-%d %H:%M") if dt else ""
def fmt_t(dt: Optional[datetime]) -> str: return dt.strftime("%H:%M") if dt else ""

# ===== Persistence =====
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
def parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s: return None
    x = datetime.fromisoformat(s)
    return x if x.tzinfo else x.replace(tzinfo=TZ)
def serialize_state() -> Dict:
    return {
        "employees": [{"name": e["name"], "check_in": e["check_in"].isoformat(), "next_free": e["next_free"].isoformat(), "served_count": e["served_count"], "role": e.get("role","正式")} for e in st.session_state.employees],
        "services": st.session_state.services,
        "assignments": [{**{k:v for k,v in r.items() if k not in ("start","end")}, "start": r["start"].isoformat(), "end": r["end"].isoformat()} for r in st.session_state.assignments],
        "waiting": [{"customer_id": w["customer_id"], "service": w["service"], "arrival": w["arrival"].isoformat(), "count": w["count"]} for w in st.session_state.waiting],
        "reservations": [{"id": r["id"], "customer": r["customer"], "service": r["service"], "employee": r["employee"], "start": r["start"].isoformat(), "status": r.get("status","pending")} for r in st.session_state.reservations],
        "_customer_seq": st.session_state._customer_seq,
    }
def load_state():
    path = DATA_DIR / f"{today_key()}.json"
    if not path.exists(): return False
    data = json.loads(path.read_text(encoding="utf-8"))
    st.session_state.employees = [{"name": e["name"], "check_in": parse_dt(e["check_in"]), "next_free": parse_dt(e["next_free"]), "served_count": int(e.get("served_count",0)), "role": e.get("role","正式")} for e in data.get("employees",[])]
    st.session_state.services = data.get("services", st.session_state.services)
    st.session_state.assignments = [{**{k:v for k,v in r.items() if k not in ("start","end")}, "start": parse_dt(r["start"]), "end": parse_dt(r["end"])} for r in data.get("assignments",[])]
    st.session_state.waiting = [{"customer_id": w["customer_id"], "service": w["service"], "arrival": parse_dt(w["arrival"]), "count": int(w["count"])} for w in data.get("waiting",[])]
    st.session_state.reservations = [{"id": r["id"], "customer": r["customer"], "service": r["service"], "employee": r["employee"], "start": parse_dt(r["start"]), "status": r.get("status","pending")} for r in data.get("reservations",[])]
    st.session_state._customer_seq = int(data.get("_customer_seq",1)); return True
def save_state():
    (DATA_DIR / f"{today_key()}.json").write_text(json.dumps(serialize_state(), ensure_ascii=False, indent=2), encoding="utf-8")

# ===== State init =====
if "loaded_today" not in st.session_state:
    st.session_state.employees = st.session_state.get("employees", [])
    st.session_state.services = st.session_state.get("services", [
        {"name": "颈肩头（20分钟）", "minutes": 20, "price": 40.0},
        {"name": "颈肩头（30分钟）", "minutes": 30, "price": 50.0},
        {"name": "颈肩背（45分钟）", "minutes": 45, "price": 75.0},
        {"name": "全身（60分钟）", "minutes": 60, "price": 100.0},
        {"name": "足疗（30分钟）", "minutes": 30, "price": 50.0},
    ])
    st.session_state.assignments = st.session_state.get("assignments", [])
    st.session_state.waiting = st.session_state.get("waiting", [])
    st.session_state.reservations = st.session_state.get("reservations", [])
    st.session_state._customer_seq = st.session_state.get("_customer_seq", 1)
    if load_state(): st.toast("已恢复今日数据 ✅")
    st.session_state.loaded_today = True

def ensure_payment_fields():
    for rec in st.session_state.assignments:
        for k in ("pay_cash","pay_transfer","pay_eftpos","pay_voucher","payment_note"):
            if k not in rec: rec[k] = 0.0 if k!="payment_note" else ""

# ===== Capability mapping (Chinese-aware) =====
def service_tags(name: str):
    """
    根据项目名称打标签：
    - NSH：颈/肩/头 类（不包含背/腿/全身/理疗等）
    - FOOT：脚/足/足疗/脚底/反射
    - OTHER：其余
    支持中英文关键词混用。
    """
    raw = name or ""
    n = raw.lower()
    zh = raw

    tags = set()

    # FOOT（足疗/脚/反射）
    foot_kw_en = ["feet", "foot", "reflexology"]
    foot_kw_zh = ["脚", "足", "足疗", "脚底", "足底", "反射"]
    if any(k in n for k in foot_kw_en) or any(k in zh for k in foot_kw_zh):
        tags.add("FOOT")

    # NSH（颈肩头），但排除背/腿/全身/理疗等
    nsh_pos_en = ["neck", "shoulder", "head"]
    nsh_pos_zh = ["颈", "肩", "头", "颈肩", "颈肩头"]
    nsh_neg_en = ["back", "leg", "whole", "full", "cupping", "remedial", "dry needling", "pregnancy", "children", "sciatica", "elbow", "hip"]
    nsh_neg_zh = ["背", "背部", "腿", "全身", "全", "拔罐", "理疗", "干针", "孕", "小儿", "坐骨", "肘", "髋"]

    has_pos = any(k in n for k in nsh_pos_en) or any(k in zh for k in nsh_pos_zh)
    has_neg = any(k in n for k in nsh_neg_en) or any(k in zh for k in nsh_neg_zh)
    if has_pos and not has_neg:
        tags.add("NSH")

    if not tags:
        tags.add("OTHER")
    return tags

def can_employee_do(emp: Dict, service: Dict) -> bool:
    role = emp.get("role","正式"); tags = service_tags(service["name"])
    if role == "正式": return True
    if role == "新员工-初级": return ("NSH" in tags) and ("FOOT" not in tags)
    if role == "新员工-中级": return ("NSH" in tags) or ("FOOT" in tags)
    return True

# ===== Core logic =====
def sorted_employees_for_rotation() -> List[Dict]:
    return sorted(st.session_state.employees, key=lambda e: (e["next_free"], e["check_in"], e["served_count"]))


def assign_customer(service: Dict, arrival: datetime, prefer_employee: Optional[str] = None) -> Optional[Dict]:
    if not st.session_state.employees: 
        return None
    emps = sorted_employees_for_rotation()
    if prefer_employee: 
        emps = sorted(emps, key=lambda e: 0 if e["name"] == prefer_employee else 1)
    # 能力过滤
    emps = [e for e in emps if can_employee_do(e, service)]
    if not emps: 
        return None

    # 如果是预约分配（prefer_employee 且 arrival 恰为其预约开始），忽略阻塞校验
    def is_exact_reservation(emp, start_dt):
        if not prefer_employee or emp["name"] != prefer_employee:
            return False
        # 存在一条预约，开始时间==arrival 且未完成
        for r in st.session_state.reservations:
            if r.get("status","pending") != "done" and r["employee"] == emp["name"] and r["start"] == start_dt:
                return True
        return False

    chosen = None
    chosen_start = None
    chosen_end = None
    for e in emps:
        start_time = max(arrival, e["next_free"])
        end_time = start_time + timedelta(minutes=service["minutes"])
        # 查该员工从 start_time 往后的最近预约开始，用于阻塞校验
        block = next_reservation_block(e["name"], start_time)
        # 如果会与预约冲突（开始前无法完成或开始时刻已被预约），则跳过；
        # 但若这是预约本身（is_exact_reservation），则放行。
        if block is not None:
            if is_exact_reservation(e, arrival):
                # 放行预约本身
                pass
            else:
                # 若新单会与预约重叠（end_time > block）或 start_time >= block，都视为冲突
                if end_time > block or start_time >= block:
                    continue
        # 到这儿表示 e 可用
        chosen = e
        chosen_start = start_time
        chosen_end = end_time
        break

    if chosen is None:
        return None

    record = {
        "customer_id": st.session_state._customer_seq,
        "service": service["name"],
        "minutes": service["minutes"],
        "employee": chosen["name"],
        "start": chosen_start,
        "end": chosen_end,
        "price": service["price"],
        "status": "进行中" if chosen_start <= now() < chosen_end else ("已完成" if chosen_end <= now() else "排队中"),
        "pay_cash": 0.0, "pay_transfer": 0.0, "pay_eftpos": 0.0, "pay_voucher": 0.0, "payment_note": ""
    }
    st.session_state._customer_seq += 1
    chosen["next_free"] = chosen_end
    chosen["served_count"] += 1
    for i, emp in enumerate(st.session_state.employees):
        if emp["name"] == chosen["name"]:
            st.session_state.employees[i] = chosen
            break
    st.session_state.assignments.append(record)
    save_state()
    return record


def try_flush_waiting():
    st.session_state.waiting.sort(key=lambda x: x["arrival"]); flushed, still = [], []
    for item in st.session_state.waiting:
        assigned = 0
        for _ in range(item["count"]):
            rec = assign_customer(item["service"], item["arrival"])
            if rec is None:
                still.append({"customer_id": item["customer_id"], "service": item["service"], "arrival": item["arrival"], "count": item["count"]-assigned}); break
            assigned += 1
        if assigned == item["count"]: flushed.append(item)
    st.session_state.waiting = still; save_state(); return flushed

def register_customers(service_name: str, arrival: datetime, count: int = 1):
    service = next((s for s in st.session_state.services if s["name"] == service_name), None)
    if not service: st.error("未找到该项目"); return
    for i in range(count):
        rec = assign_customer(service, arrival)
        if rec is None:
            st.session_state.waiting.append({"customer_id": st.session_state._customer_seq, "service": service, "arrival": arrival, "count": count-i})
            st.session_state._customer_seq += 1; save_state(); break

def refresh_status():
    changed = False
    for rec in st.session_state.assignments:
        prev = rec["status"]
        if rec["end"] <= now(): rec["status"] = "已完成"
        elif rec["start"] <= now() < rec["end"]: rec["status"] = "进行中"
        else: rec["status"] = "排队中"
        changed = changed or (prev != rec["status"])
    if changed: save_state()

def apply_due_reservations():
    changed = False; keep = []
    for r in sorted(st.session_state.reservations, key=lambda x: x["start"]):
        if r.get("status","pending") == "done": keep.append(r); continue
        if r["start"] <= now():
            service = next((s for s in st.session_state.services if s["name"] == r["service"]), None)
            if service is None: keep.append(r); continue
            rec = assign_customer(service, r["start"], prefer_employee=r["employee"])
            if rec is not None: r["status"] = "done"; changed = True; keep.append(r); continue
        keep.append(r)
    st.session_state.reservations = keep
    if changed: save_state()


def next_reservation_block(emp_name: str, ref_start: datetime) -> Optional[datetime]:
    """
    返回该员工在 ref_start 之后的最近一条“未执行预约”的开始时间；若没有则返回 None。
    """
    future = [r["start"] for r in st.session_state.reservations 
              if r.get("status","pending") != "done" and r["employee"] == emp_name and r["start"] >= ref_start]
    if not future:
        return None
    return min(future)


def build_timeline_blocks():
    """构建今日时间轴数据：包含未完成/进行中的服务+未执行预约。"""
    rows = []
    # 今日 00:00 与 23:59 边界（墨尔本）
    day_start = datetime.combine(now().date(), dtime(hour=0, minute=0, second=0), tzinfo=TZ)
    day_end   = datetime.combine(now().date(), dtime(hour=23, minute=59, second=59), tzinfo=TZ)

    # 现有分配（占用窗口）
    for r in st.session_state.assignments:
        # 只展示今日范围内的占用
        s = max(r["start"], day_start)
        e = min(r["end"], day_end)
        if e <= s: 
            continue
        rows.append({
            "员工": r["employee"],
            "类型": "服务",
            "标签": r["service"],
            "开始": s,
            "结束": e,
        })

    # 未来预约（pending）
    for rv in st.session_state.reservations:
        if rv.get("status","pending") == "done":
            continue
        # 查找对应项目分钟数
        svc = next((s for s in st.session_state.services if s["name"] == rv["service"]), None)
        minutes = int(svc["minutes"]) if svc and "minutes" in svc else 30
        s = rv["start"]
        e = s + timedelta(minutes=minutes)
        # 限定在今日范围
        if e < day_start or s > day_end:
            continue
        s = max(s, day_start)
        e = min(e, day_end)
        if e <= s:
            continue
        rows.append({
            "员工": rv["employee"],
            "类型": "预约",
            "标签": f'{rv["service"]}（{rv["customer"]}）',
            "开始": s,
            "结束": e,
        })

    if not rows:
        return pd.DataFrame(columns=["员工","类型","标签","开始","结束"])
    df = pd.DataFrame(rows)
    # 排序便于显示
    df = df.sort_values(["员工","开始","结束"])
    return df


def eligible_employees_for(service: Dict, at_time: datetime):
    """返回在给定时间点、对给定项目可接单的员工顺位列表（已考虑能力与预约阻塞）。"""
    if not st.session_state.employees:
        return []
    emps = sorted_employees_for_rotation()
    ok = []
    for e in emps:
        if not can_employee_do(e, service):
            continue
        start_time = max(at_time, e["next_free"])
        end_time = start_time + timedelta(minutes=service["minutes"])
        # 预约阻塞：若会撞上该员工未来 pending 预约，则跳过
        block = next_reservation_block(e["name"], start_time)
        if block is not None and (end_time > block or start_time >= block):
            continue
        ok.append({"员工": e["name"], "类型": e.get("role","正式"), "下一次空闲": start_time, "预计结束": end_time, "累计接待": e["served_count"]})
    # 排序：按照预计开始时间、签到、累计接待（与核心排序保持一致）
    ok = sorted(ok, key=lambda r: (r["下一次空闲"],))
    return ok

# ===== Utilities for deletions & recompute =====
def recompute_all_employees():
    by_emp = {}
    for e in st.session_state.employees:
        by_emp[e["name"]] = {"count": 0, "latest_end": e["check_in"]}
    for rec in st.session_state.assignments:
        name = rec["employee"]
        if name not in by_emp: by_emp[name] = {"count": 0, "latest_end": now()}
        by_emp[name]["count"] += 1
        if by_emp[name]["latest_end"] is None or rec["end"] > by_emp[name]["latest_end"]:
            by_emp[name]["latest_end"] = rec["end"]
    for e in st.session_state.employees:
        info = by_emp.get(e["name"], {"count": 0, "latest_end": e["check_in"]})
        e["served_count"] = info["count"]
        e["next_free"] = max(info["latest_end"] or e["check_in"], now())

def delete_assignments_by_ids(ids):
    ids = set(ids); st.session_state.assignments = [r for r in st.session_state.assignments if r["customer_id"] not in ids]
    recompute_all_employees(); save_state()

def delete_waiting_by_ids(ids):
    ids = set(ids); st.session_state.waiting = [w for w in st.session_state.waiting if w["customer_id"] not in ids]; save_state()

def delete_reservations_by_ids(ids):
    ids = set(ids); st.session_state.reservations = [r for r in st.session_state.reservations if r["id"] not in ids]; save_state()

def delete_employees_by_names(names):
    names = set(names); st.session_state.employees = [e for e in st.session_state.employees if e["name"] not in names]; save_state()

# ===== Sidebar =====
with st.sidebar:
    st.header("参数与设置"); st.caption("• 墨尔本时区；轮值=下一次空闲→签到→累计接待；新员工受项目限制"); st.divider()
    st.subheader("服务项目（可编辑）")
    with st.expander("管理项目（时长/价格）", expanded=False):
        df_services = pd.DataFrame(st.session_state.services)
        edited = st.data_editor(df_services, num_rows="dynamic", use_container_width=True, key="service_editor", column_config={"name":"项目名","minutes":"时长(分钟)","price":"价格($)"})
        if st.button("保存项目变更"):
            clean = []
            for _, r in edited.iterrows():
                if not r["name"] or pd.isna(r["minutes"]) or pd.isna(r["price"]): continue
                clean.append({"name": str(r["name"]), "minutes": int(r["minutes"]), "price": float(r["price"])})
            st.session_state.services = clean; save_state(); st.success("已保存服务项目。")
    st.subheader("数据导出")
    ensure_payment_fields()
    if st.session_state.assignments:
        df_export = pd.DataFrame([{"客户ID": rec["customer_id"], "项目": rec["service"], "时长(分钟)": rec["minutes"], "员工": rec["employee"], "开始时间": fmt(rec["start"]), "结束时间": fmt(rec["end"]), "价格($)": rec["price"], "状态": rec["status"], "现金($)": rec.get("pay_cash",0.0), "转账($)": rec.get("pay_transfer",0.0), "EFTPOS($)": rec.get("pay_eftpos",0.0), "券($)": rec.get("pay_voucher",0.0), "收款备注": rec.get("payment_note","")} for rec in st.session_state.assignments])
        st.download_button("下载今日记录 CSV", df_export.to_csv(index=False).encode("utf-8-sig"), file_name=f"records_{now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
    if st.button("清空今日数据（新一天）", type="primary"):
        st.session_state.assignments = []; st.session_state.waiting = []; st.session_state.employees = []; st.session_state.reservations = []; st.session_state._customer_seq = 1
        p = DATA_DIR / f"{today_key()}.json"
        if p.exists(): 
            try: p.unlink()
            except Exception: pass
        st.toast("已清空今日数据。")

# ===== Main =====
st.title("🧘 门店排班与轮值提醒系统（Streamlit 版）")
tab_emp, tab_cus, tab_board = st.tabs(["员工签到/状态", "登记顾客/自动分配", "看板与提醒"])

# -- 员工签到 --
with tab_emp:
    st.subheader("员工签到（先到先服务）")
    cols = st.columns(4)
    with cols[0]: emp_name = st.text_input("员工姓名", placeholder="例如：Pan / Ptr / Iris")
    with cols[1]: role = st.selectbox("员工类型", ["正式","新员工-初级","新员工-中级"], index=0)
    with cols[2]:
        in_mode = st.radio("签到时间", ["使用当前时间（墨尔本）","手动输入"], horizontal=True, index=0)
        if in_mode == "使用当前时间（墨尔本）":
            ci_time = now().time(); st.caption(f"当前时间：{ci_time.strftime('%H:%M:%S')}"); manual_ci_str = None
        else:
            manual_ci_str = st.text_input("手动输入签到时间（HH:MM 或 HH:MM:SS）", value=now().strftime("%H:%M")); ci_time = None
    with cols[3]:
        if st.button("签到/上班", type="primary"):
            if emp_name:
                if in_mode == "使用当前时间（墨尔本）": t = datetime.combine(now().date(), ci_time, tzinfo=TZ)
                else:
                    try: parts = manual_ci_str.strip().split(":"); hh, mm, ss = int(parts[0]), int(parts[1]), (int(parts[2]) if len(parts)==3 else 0); t = datetime.combine(now().date(), dtime(hour=hh, minute=mm, second=ss), tzinfo=TZ)
                    except Exception as e: st.error(f"时间格式错误：{e}"); t = None
                if t is not None:
                    name = emp_name.strip(); ex = next((e for e in st.session_state.employees if e["name"] == name), None)
                    if ex:
                        ex["check_in"] = t; ex["role"] = role
                        if ex["next_free"] < t: ex["next_free"] = t
                        st.success(f"{name} 签到时间已更新为 {t.strftime('%H:%M')}（{role}）")
                    else:
                        st.session_state.employees.append({"name": name, "check_in": t, "next_free": t, "served_count": 0, "role": role}); st.success(f"{name} 已签到（{role}）。")
                    st.session_state.employees = sorted(st.session_state.employees, key=lambda e: e["check_in"]); save_state(); try_flush_waiting()
            else:
                st.error("请输入员工姓名。")

    if st.session_state.employees:
        # 删除员工
        sel_emp = st.multiselect("选择要删除的员工（当日）", [e["name"] for e in st.session_state.employees], key="del_emps")
        if st.button("删除所选员工", disabled=not sel_emp): delete_employees_by_names(sel_emp); st.success(f"已删除：{', '.join(sel_emp)}")
        df_emp = pd.DataFrame([{"员工": e["name"], "类型": e.get("role","正式"), "签到": fmt_t(e["check_in"]), "下一次空闲": fmt_t(e["next_free"]), "累计接待": e["served_count"]} for e in sorted_employees_for_rotation()])
        st.dataframe(df_emp, use_container_width=True)
    else:
        st.info("暂无员工签到。")

# -- 顾客登记 + 预约 + 嵌入实时看板 --
with tab_cus:
    st.subheader("登记顾客（按轮值自动分配）")
    with st.expander("☎️ 老顾客预约（指定技师/时间/项目）", expanded=False):
        c1, c2, c3, c4 = st.columns([1.2,1,1,1])
        with c1: rv_name = st.text_input("顾客姓名/备注", key="rv_name")
        with c2: rv_service = st.selectbox("项目", [s["name"] for s in st.session_state.services], key="rv_service")
        with c3: rv_employee = st.selectbox("指定技师", [e["name"] for e in st.session_state.employees], key="rv_emp") if st.session_state.employees else st.selectbox("指定技师", ["暂无员工"], key="rv_emp_disabled")
        with c4: rv_time_str = st.text_input("预约开始（HH:MM 或 HH:MM:SS）", value=now().strftime("%H:%M"), key="rv_time")
        v1, v2 = st.columns([1,1])
        with v1:
            if st.button("添加预约", key="btn_add_resv") and st.session_state.employees:
                try:
                    parts = rv_time_str.strip().split(":"); hh, mm, ss = int(parts[0]), int(parts[1]), (int(parts[2]) if len(parts)==3 else 0)
                    start_dt = datetime.combine(now().date(), dtime(hour=hh, minute=mm, second=ss), tzinfo=TZ)
                    rid = (max([r["id"] for r in st.session_state.reservations], default=0) + 1)
                    st.session_state.reservations.append({"id": rid, "customer": rv_name or f"预约{rid}", "service": rv_service, "employee": rv_employee, "start": start_dt, "status": "pending"})
                    save_state(); st.success("已添加预约。")
                except Exception as e:
                    st.error(f"时间格式错误：{e}")
        with v2:
            if st.button("立即应用到期预约", key="btn_apply_resv"): apply_due_reservations(); st.success("已处理到期预约。")
        if st.session_state.reservations:
            df_resv = pd.DataFrame([{"预约ID": r["id"], "顾客": r["customer"], "项目": r["service"], "技师": r["employee"], "开始": fmt_t(r["start"]), "状态": r.get("status","pending")} for r in sorted(st.session_state.reservations, key=lambda x: x["start"])])
            st.dataframe(df_resv, use_container_width=True, height=220)
            del_ids = st.multiselect("选择要删除的预约", [r["id"] for r in st.session_state.reservations], key="del_resv_ids")
            if st.button("删除所选预约", disabled=not del_ids): delete_reservations_by_ids(del_ids); st.success("已删除所选预约。")

    cols = st.columns(4)
    services = [s["name"] for s in st.session_state.services]
    with cols[0]: service_chosen = st.selectbox("项目", services, index=0)
    with cols[1]:
        time_mode = st.radio("到店时间", ["使用当前时间（墨尔本）","手动输入"], horizontal=True, index=0)
        if time_mode == "使用当前时间（墨尔本）":
            arrival_time = now().time(); st.caption(f"当前时间：{arrival_time.strftime('%H:%M:%S')}"); manual_time_str = None
        else:
            manual_time_str = st.text_input("手动输入到店时间（HH:MM 或 HH:MM:SS）", value=now().strftime("%H:%M")); arrival_time = None
    with cols[2]: group_count = st.number_input("同时到店人数（相同项目）", min_value=1, max_value=20, value=1, step=1)
    with cols[3]:
        if st.button("登记并分配", type="primary"):
            if time_mode == "使用当前时间（墨尔本）": t = arrival_time
            else:
                try: parts = manual_time_str.strip().split(":"); hh, mm, ss = int(parts[0]), int(parts[1]), (int(parts[2]) if len(parts)==3 else 0); t = dtime(hour=hh, minute=mm, second=ss)
                except Exception as e: st.error(f"时间格式错误：{e}"); t = None
            if t is not None:
                arrival_dt = datetime.combine(now().date(), t, tzinfo=TZ); register_customers(service_chosen, arrival_dt, count=int(group_count)); st.success("已登记与分配（不足时将加入等待队）。")

    st.divider()
    st.markdown("#### 等待队列")
    if st.session_state.waiting:
        df_wait = pd.DataFrame([{"批次客户ID": w["customer_id"], "项目": w["service"]["name"], "人数": w["count"], "到店": fmt_t(w["arrival"])} for w in st.session_state.waiting])
        st.dataframe(df_wait, use_container_width=True)
        delw = st.multiselect("选择要删除的等待批次", [w["customer_id"] for w in st.session_state.waiting], key="del_wait_ids")
        b1, b2 = st.columns([1,1])
        with b1:
            if st.button("删除所选等待批次", disabled=not delw): delete_waiting_by_ids(delw); st.success("已删除所选等待批次。")
        with b2:
            if st.button("尝试为等待队列重新分配"): flushed = try_flush_waiting(); st.success(f"已重新分配 {sum(x['count'] for x in flushed)} 位顾客。" if flushed else "暂无可分配的员工空闲。")
    else:
        st.caption("当前没有等待中的顾客。")

    
# === 嵌入实时看板 ===
st.divider(); st.markdown("### ⏱️ 实时看板（快速查看）")
refresh_status(); apply_due_reservations()

# 计算预判时间（与当前登记控件保持一致）
_preview_time = None
try:
    if time_mode == "使用当前时间（墨尔本）":
        _preview_time = now()
    else:
        parts = manual_time_str.strip().split(":")
        hh, mm, ss = int(parts[0]), int(parts[1]), (int(parts[2]) if len(parts)==3 else 0)
        _preview_time = datetime.combine(now().date(), dtime(hour=hh, minute=mm, second=ss), tzinfo=TZ)
except Exception:
    _preview_time = now()

# 预判“可接此项目的顺位”
service_obj = next((s for s in st.session_state.services if s["name"] == service_chosen), None)
if st.session_state.employees and service_obj:
    eligible = eligible_employees_for(service_obj, _preview_time)
    if eligible:
        import pandas as _pd
        rows = []
        for idx, e in enumerate(eligible):
            rows.append({"顺位": "👉 下一位" if idx == 0 else idx + 1, "员工": e["员工"], "类型": e["类型"], "可开始": fmt_t(e["下一次空闲"]), "预计结束": fmt_t(e["预计结束"]), "累计接待": e["累计接待"]})
        st.dataframe(_pd.DataFrame(rows), use_container_width=True, height=220)
        # 提示下一位
        first = eligible[0]
        msg = f"可接此项目的下一位：{first['员工']}（{fmt_t(first['下一次空闲'])} 开始，至 {fmt_t(first['预计结束'])}）"
        st.success(msg)
    else:
        st.warning("当前没有符合能力且不与预约冲突的员工。")
else:
    st.caption("暂无员工签到或项目未找到。")

active = [r for r in st.session_state.assignments if r["status"] == "进行中"]
queued = [r for r in st.session_state.assignments if r["status"] == "排队中"]
if active:
    st.markdown("#### 进行中"); st.dataframe(pd.DataFrame([{"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"])} for r in sorted(active, key=lambda x: x["end"])]), use_container_width=True, height=180)
if queued:
    st.markdown("#### 排队中（已分配，未开始）"); st.dataframe(pd.DataFrame([{"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"])} for r in sorted(queued, key=lambda x: x["start"])]), use_container_width=True, height=180)
if st.session_state.waiting:
    st.markdown("#### 等待分配（未指派员工）"); st.dataframe(pd.DataFrame([{"批次客户ID": w["customer_id"], "项目": w["service"]["name"], "人数": w["count"], "到店": fmt_t(w["arrival"])} for w in sorted(st.session_state.waiting, key=lambda x: x["arrival"])]), use_container_width=True, height=180)

# -- 看板与提醒（完整版 + 收款编辑 + 删除） --
with tab_board:
    st.subheader("实时看板")
    refresh_status(); apply_due_reservations(); ensure_payment_fields()
    left, right = st.columns(2)
    with left:
        st.markdown("##### 进行中")
        active = [r for r in st.session_state.assignments if r["status"] == "进行中"]
        if active:
            df_act = pd.DataFrame([{"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"]), "剩余(分)": max(0, int((r["end"] - now()).total_seconds() // 60))} for r in sorted(active, key=lambda x: x["end"])])
            st.dataframe(df_act, use_container_width=True, height=280)
        else:
            st.caption("暂无进行中的服务。")
        st.markdown("##### 排队中（已分配，未开始）")
        queued = [r for r in st.session_state.assignments if r["status"] == "排队中"]
        if queued:
            df_q = pd.DataFrame([{"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"])} for r in sorted(queued, key=lambda x: x["start"])])
            st.dataframe(df_q, use_container_width=True, height=220)
        else:
            st.caption("暂无排队中的记录。")
        st.markdown("##### 等待分配（未指派员工）")
        if st.session_state.waiting:
            df_w = pd.DataFrame([{"批次客户ID": w["customer_id"], "项目": w["service"]["name"], "人数": w["count"], "到店": fmt_t(w["arrival"])} for w in sorted(st.session_state.waiting, key=lambda x: x["arrival"])])
            st.dataframe(df_w, use_container_width=True, height=220)
        else:
            st.caption("暂无等待分配的顾客。")
        st.markdown("##### 员工轮值队列（下一位 →）")
        if st.session_state.employees:
            rotation = sorted_employees_for_rotation(); rows = []
            for idx, e in enumerate(rotation):
                status = "空闲" if e["next_free"] <= now() else f"忙碌至 {fmt_t(e['next_free'])}"
                rows.append({"顺位": "👉 下一位" if idx == 0 else idx + 1, "员工": e["name"], "类型": e.get("role","正式"), "状态": status, "下一次空闲": fmt_t(e["next_free"]), "累计接待": e["served_count"]})
            df_rot = pd.DataFrame(rows); st.dataframe(df_rot, use_container_width=True, height=260)
            nxt = rotation[0]; mins = max(0, int((nxt["next_free"] - now()).total_seconds() // 60))
            st.success(f"下一位应接单员工：{nxt['name']}（可立即接待）" if mins==0 else f"下一位应接单员工：{nxt['name']}（预计 {mins} 分钟后空闲，{fmt_t(nxt['next_free'])}）")
        st.markdown("###### 顺位预判（按项目与时间考虑能力与预约）")
        svc_opt = st.selectbox("选择项目用于预判", [s["name"] for s in st.session_state.services], key="predict_service")
        t_str = st.text_input("到店时间（HH:MM 或 HH:MM:SS）", value=now().strftime("%H:%M"), key="predict_time")
        if st.button("生成预判顺位", key="btn_predict"):
            try:
                parts = t_str.strip().split(":"); hh, mm, ss = int(parts[0]), int(parts[1]), (int(parts[2]) if len(parts)==3 else 0)
                at_dt = datetime.combine(now().date(), dtime(hour=hh, minute=mm, second=ss), tzinfo=TZ)
                svc = next((s for s in st.session_state.services if s["name"] == svc_opt), None)
                if svc:
                    el = eligible_employees_for(svc, at_dt)
                    if el:
                        import pandas as _pd
                        rows = [{"顺位": "👉 下一位" if i==0 else i+1, "员工": e["员工"], "类型": e["类型"], "可开始": fmt_t(e["下一次空闲"]), "预计结束": fmt_t(e["预计结束"]), "累计接待": e["累计接待"]} for i, e in enumerate(el)]
                        st.dataframe(_pd.DataFrame(rows), use_container_width=True, height=220)
                    else:
                        st.warning("没有符合条件的员工。")
                else:
                    st.error("未找到该项目。")
            except Exception as _e:
                st.error(f"时间格式错误：{_e}")
    
        else:
            st.caption("暂无员工签到。")
    with right:
        st.markdown("##### 今日全部记录")
        if st.session_state.assignments:
            df_all = pd.DataFrame([{"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"]), "价格($)": r["price"], "状态": r["status"]} for r in sorted(st.session_state.assignments, key=lambda x: (x["start"], x["customer_id"]))])
            st.dataframe(df_all, use_container_width=True, height=300)
            # 总营收（按实收；如未填，则按标价计） + 收款编辑 + 员工汇总注释 + 删除
            ensure_payment_fields()
            editable = [r for r in st.session_state.assignments if r["status"] != "排队中"]
            realized_list = []
            for r in editable:
                cash = r.get("pay_cash",0.0); bank = r.get("pay_transfer",0.0); pos = r.get("pay_eftpos",0.0); vou = r.get("pay_voucher",0.0)
                realized = cash + bank + pos + vou
                if realized <= 0: realized = r["price"]
                realized_list.append(realized)
            st.metric("今日营收(已开始/已完成)", f"${sum(realized_list):,.2f}" if realized_list else "$0.00")
            if editable:
                df_pay = pd.DataFrame([{"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "价格($)": r["price"], "现金($)": r.get("pay_cash",0.0), "转账($)": r.get("pay_transfer",0.0), "EFTPOS($)": r.get("pay_eftpos",0.0), "券($)": r.get("pay_voucher",0.0), "备注": r.get("payment_note","")} for r in editable])
                st.markdown("###### 收款信息（可编辑）")
                edited = st.data_editor(df_pay, num_rows="fixed", use_container_width=True, key="payment_editor_full", column_config={"现金($)": st.column_config.NumberColumn(format="%.2f", min_value=0.0), "转账($)": st.column_config.NumberColumn(format="%.2f", min_value=0.0), "EFTPOS($)": st.column_config.NumberColumn(format="%.2f", min_value=0.0), "券($)": st.column_config.NumberColumn(format="%.2f", min_value=0.0), "备注": st.column_config.TextColumn()}, hide_index=True)
                id_to_rec = {r["customer_id"]: r for r in editable}
                for _, row in edited.iterrows():
                    rec = id_to_rec.get(row["客户ID"])
                    if rec:
                        rec["pay_cash"] = float(row["现金($)"]) if row["现金($)"] is not None else 0.0
                        rec["pay_transfer"] = float(row["转账($)"]) if row["转账($)"] is not None else 0.0
                        rec["pay_eftpos"] = float(row["EFTPOS($)"]) if row["EFTPOS($)"] is not None else 0.0
                        rec["pay_voucher"] = float(row["券($)"]) if row["券($)"] is not None else 0.0
                        rec["payment_note"] = str(row["备注"]) if row["备注"] is not None else ""
                save_state()
            rows = []
            for r in editable:
                cash = r.get("pay_cash",0.0); bank = r.get("pay_transfer",0.0); pos = r.get("pay_eftpos",0.0); vou = r.get("pay_voucher",0.0)
                realized = cash + bank + pos + vou
                if realized <= 0: realized = r["price"]
                rows.append({"employee": r["employee"], "realized": realized, "cash": cash, "bank": bank, "pos": pos, "voucher": vou})
            if rows:
                df_r = pd.DataFrame(rows); per_emp = df_r.groupby("employee")[["realized","cash","bank","pos","voucher"]].sum().reset_index().sort_values("realized", ascending=False)
                def note(row):
                    parts = []
                    if row["cash"] > 0: parts.append(f"现金${row['cash']:.2f}")
                    if row["bank"] > 0: parts.append(f"转账${row['bank']:.2f}")
                    if row["pos"] > 0: parts.append(f"EFTPOS${row['pos']:.2f}")
                    if row["voucher"] > 0: parts.append(f"券${row['voucher']:.2f}")
                    return "，".join(parts) if parts else "未登记收款（按标价计）"
                per_emp["收款注释"] = per_emp.apply(note, axis=1); per_emp.rename(columns={"employee":"员工","realized":"营业额($)"}, inplace=True)
                st.markdown("###### 员工营业额统计（今日，含收款注释）"); st.dataframe(per_emp[["员工","营业额($)","收款注释"]], use_container_width=True, height=260)
            # 删除误录的顾客记录
            delids = st.multiselect("选择要删除的记录（客户ID）", [r["customer_id"] for r in st.session_state.assignments], key="del_assign_ids_full")
            if st.button("删除所选记录", disabled=not delids): delete_assignments_by_ids(delids); st.success("已删除所选记录，并已重算员工轮值。")
        else:
            st.caption("今天还没有记录。")
    st.divider()
    st.markdown("### 📆 预约与占用时间轴（今日）")
    df_tl = build_timeline_blocks()
    if df_tl.empty:
        st.caption("今日暂无预约或占用时段。")
    else:
        # 选择员工过滤
        emp_opts = sorted(df_tl["员工"].unique().tolist())
        sel = st.multiselect("筛选员工", emp_opts, default=emp_opts, key="tl_emp_filter")
        v = df_tl[df_tl["员工"].isin(sel)] if sel else df_tl.head(0)
        if v.empty:
            st.caption("所选员工暂无数据。")
        else:
            # 使用 Altair 绘制甘特图
            chart = alt.Chart(v).mark_bar().encode(
                x=alt.X('开始:T', title='时间'),
                x2='结束:T',
                y=alt.Y('员工:N', sort=emp_opts, title='员工'),
                color=alt.Color('类型:N', legend=alt.Legend(title="类型")),
                tooltip=['员工','类型','标签','开始','结束']
            ).properties(height=max(160, 40*len(emp_opts)))
            st.altair_chart(chart, use_container_width=True)

