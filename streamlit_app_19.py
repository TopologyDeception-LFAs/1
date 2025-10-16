import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta, time as dtime
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo
import altair as alt
import re

st.set_page_config(page_title="Coral Chinese Massage排班与轮值提醒系统", layout="wide")

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
        # --- Deep Tissue Oil, Relaxation, Dry Massage ---
        {"name": "NS (0 mins)", "minutes": 0, "price": 0.0},
        {"name": "NS (1 mins)", "minutes": 1, "price": 45.0},
        {"name": "NS (20 mins)", "minutes": 20, "price": 40.0},
        {"name": "NS (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "NSHe (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "NSHe (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "BHi (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "BHi (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "L (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "L (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "NSB (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "NSB (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSAHa (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "NSAHa (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSBHe (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "NSBHe (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "BL (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "BL (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSBAHa (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "NSBAHa (70 mins)", "minutes": 70, "price": 120.0},
        {"name": "NSBL (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "NSBL (70 mins)", "minutes": 70, "price": 120.0},
        {"name": "WB (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "WB (90 mins)", "minutes": 90, "price": 150.0},

        # --- Foot Massage & Packages ---
        {"name": "F(R) (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "F(R) (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSF (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "NSBF (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSBLF (70 mins)", "minutes": 70, "price": 120.0},
        {"name": "WBF (90 mins)", "minutes": 90, "price": 150.0},

        # --- Special Treatment ---
        {"name": "Pregnancy massage (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "Pregnancy massage (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "Children massage (20 mins)", "minutes": 20, "price": 40.0},
        {"name": "Children massage (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "Sciatica/Frozen Shoulder/Tennis Elbow/Golf Elbow (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "Sciatica/Frozen Shoulder/Tennis Elbow/Golf Elbow (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "Cupping Therapy with herbal oil (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "Ear Candling & Face Massage (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "Neck, Shoulders & Back + Cupping (50 mins)", "minutes": 50, "price": 85.0},

        # --- Dry Needling Therapy ---
        {"name": "Dry Needling (First Session)", "minutes": 0, "price": 80.0},
        {"name": "Dry Needling (Second+ Session)", "minutes": 0, "price": 70.0},
        {"name": "Dry Needling + 40 mins Remedial massage", "minutes": 40, "price": 130.0},

        # --- Remedial Massage (Health Fund Rebate) ---
        {"name": "Remedial Massage (30 mins)", "minutes": 30, "price": 60.0},
        {"name": "Remedial Massage (45 mins)", "minutes": 45, "price": 85.0},
        {"name": "Remedial Massage (60 mins)", "minutes": 60, "price": 110.0},
        {"name": "Remedial Massage (90 mins)", "minutes": 90, "price": 160.0},
    ])
    st.session_state.assignments = st.session_state.get("assignments", [])
    st.session_state.waiting = st.session_state.get("waiting", [])
    st.session_state.reservations = st.session_state.get("reservations", [])
    st.session_state._customer_seq = st.session_state.get("_customer_seq", 1)
    if load_state(): st.toast("已恢复今日数据 ✅")
    st.session_state.loaded_today = True

# 记录“刚才这次登记”生成的记录ID，方便撤销
if "last_created" not in st.session_state:
    st.session_state.last_created = {"assigned": [], "waiting": []}


def ensure_payment_fields():
    for rec in st.session_state.assignments:
        for k in ("pay_cash","pay_transfer","pay_eftpos","pay_voucher","payment_note"):
            if k not in rec: rec[k] = 0.0 if k!="payment_note" else ""

# ===== Capability mapping (English abbreviations aware) =====
def service_tags(name: str):
    raw = (name or "").strip()
    n = raw.lower()
    u = raw.upper()
    tags = set()
    foot = ("foot" in n or "feet" in n or "reflexology" in n or "F(" in u or u.startswith("F(") or " NSF" in f" {u}" or " NSBF" in f" {u}" or " NSBLF" in f" {u}" or " WBF" in f" {u}" or " NSHEF" in f" {u}" or u.endswith("F"))
    if foot: tags.add("FOOT")
    back = ("back" in n) or (" NSB" in f" {u}") or (" BL" in f" {u}") or ("BHI" in u)
    leg  = ("leg"  in n) or (" BL" in f" {u}") or (" NSBL" in f" {u}")
    whole = ("whole" in n) or (" WB" in f" {u}") or u.startswith("WB")
    if back: tags.add("BACK")
    if leg: tags.add("LEG")
    if whole: tags.add("WHOLE")
    special_kw = ["remedial", "dry needling", "pregnancy", "children", "sciatica", "elbow", "hip", "cupping", "ear candling"]
    if any(k in n for k in special_kw): tags.add("SPECIAL")
    ns_like = u.startswith("NS") or ("neck" in n) or ("shoulder" in n) or ("head" in n)
    if ns_like and not (foot or back or leg or whole or any(k in n for k in special_kw)):
        tags.add("NSH")
    if not tags: tags.add("OTHER")
    return tags

def can_employee_do(emp: Dict, service: Dict) -> bool:
    role = emp.get("role","正式"); tags = service_tags(service["name"])
    has_forbidden = any(t in tags for t in ("BACK","LEG","WHOLE","SPECIAL"))
    if role == "正式": return True
    if role == "新员工-初级":
        return ("NSH" in tags) and not any(t in tags for t in ("FOOT","BACK","LEG","WHOLE","SPECIAL"))
    if role == "新员工-中级":
        if has_forbidden: return False
        if "FOOT" in tags: return True
        return "NSH" in tags
    return True

# ===== Core logic =====
def sorted_employees_for_rotation() -> List[Dict]:
    return sorted(st.session_state.employees, key=lambda e: (e["next_free"], e["check_in"], e["served_count"]))

def next_reservation_block(emp_name: str, ref_start: datetime) -> Optional[datetime]:
    future = [r["start"] for r in st.session_state.reservations 
              if r.get("status","pending") != "done" and r["employee"] == emp_name and r["start"] >= ref_start]
    if not future: return None
    return min(future)

def next_assignment_block(emp_name: str, ref_start: datetime) -> Optional[datetime]:
    future = [a["start"] for a in st.session_state.assignments 
              if a["employee"] == emp_name and a["start"] >= ref_start]
    return min(future) if future else None

def has_conflict(emp_name: str, start_time: datetime, end_time: datetime) -> Optional[str]:
    rsv = next_reservation_block(emp_name, start_time)
    if rsv is not None and (end_time > rsv or start_time >= rsv):
        return f"与预约 {rsv.strftime('%H:%M')} 冲突"
    nxt = next_assignment_block(emp_name, start_time)
    if nxt is not None and (end_time > nxt or start_time >= nxt):
        return f"与后续分配 {nxt.strftime('%H:%M')} 冲突"
    return None

def assign_customer(service: Dict, arrival: datetime, prefer_employee: Optional[str] = None) -> Optional[Dict]:
    if not st.session_state.employees: return None
    emps = sorted_employees_for_rotation()
    if prefer_employee: emps = sorted(emps, key=lambda e: 0 if e["name"] == prefer_employee else 1)
    emps = [e for e in emps if can_employee_do(e, service)]
    if not emps: return None
    def is_exact_reservation(emp, start_dt):
        if not prefer_employee or emp["name"] != prefer_employee: return False
        for r in st.session_state.reservations:
            if r.get("status","pending") != "done" and r["employee"] == emp["name"] and r["start"] == start_dt:
                return True
        return False
    chosen = None; chosen_start=None; chosen_end=None
    for e in emps:
        start_time = max(arrival, e["next_free"])
        end_time = start_time + timedelta(minutes=service["minutes"])
        block_msg = has_conflict(e["name"], start_time, end_time)
        if block_msg and not is_exact_reservation(e, arrival):
            continue
        chosen, chosen_start, chosen_end = e, start_time, end_time
        break
    if chosen is None: return None
    record = {"customer_id": st.session_state._customer_seq, "service": service["name"], "minutes": service["minutes"], "employee": chosen["name"], "start": chosen_start, "end": chosen_end, "price": service["price"], "status": "进行中" if chosen_start <= now() < chosen_end else ("已完成" if chosen_end <= now() else "排队中"), "pay_cash": 0.0, "pay_transfer": 0.0, "pay_eftpos": 0.0, "pay_voucher": 0.0, "payment_note": ""}
    st.session_state._customer_seq += 1
    chosen["next_free"] = chosen_end; chosen["served_count"] += 1
    for i, emp in enumerate(st.session_state.employees):
        if emp["name"] == chosen["name"]:
            st.session_state.employees[i] = chosen; break
    st.session_state.assignments.append(record); save_state(); return record

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

"""
def register_customers(service_name: str, arrival: datetime, count: int = 1):
    service = next((s for s in st.session_state.services if s["name"] == service_name), None)
    if not service: st.error("未找到该项目"); return
    for i in range(count):
        rec = assign_customer(service, arrival)
        if rec is None:
            st.session_state.waiting.append({"customer_id": st.session_state._customer_seq, "service": service, "arrival": arrival, "count": count-i})
            st.session_state._customer_seq += 1; save_state(); break
"""

def register_customers(service_name: str, arrival: datetime, count: int = 1):
    """登记来客并尝试分配；返回本次新建的ID列表，用于撤销。"""
    created = {"assigned": [], "waiting": []}
    service = next((s for s in st.session_state.services if s["name"] == service_name), None)
    if not service:
        st.error("未找到该项目")
        return created

    for i in range(count):
        rec = assign_customer(service, arrival)
        if rec is None:
            # 剩余人数合并为同一等待批次
            st.session_state.waiting.append({
                "customer_id": st.session_state._customer_seq,
                "service": service,
                "arrival": arrival,
                "count": count - i
            })
            created["waiting"].append(st.session_state._customer_seq)
            st.session_state._customer_seq += 1
            save_state()
            break
        else:
            created["assigned"].append(rec["customer_id"])
    return created


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

# ===== Add-on / Extension utilities =====
def extend_or_add_on(record_id: int, mode: str, extra_minutes: int, service_name: Optional[str] = None, price_override: Optional[float] = None) -> Optional[str]:
    rec = next((r for r in st.session_state.assignments if r["customer_id"] == record_id), None)
    if not rec: return "未找到该记录"
    emp = rec["employee"]
    base_end = rec["end"]
    if mode == "extend":
        new_end = base_end + timedelta(minutes=extra_minutes)
        msg = has_conflict(emp, base_end, new_end)
        if msg: return msg
        rec["end"] = new_end
        if price_override is not None:
            rec["price"] = float(price_override)
        else:
            per_min = rec["price"] / max(rec["minutes"], 1)
            rec["price"] = round(rec["price"] + per_min * extra_minutes, 2)
        rec["minutes"] += extra_minutes
        for e in st.session_state.employees:
            if e["name"] == emp and e["next_free"] < new_end: e["next_free"] = new_end
        save_state(); return None
    else:
        if service_name:
            svc = next((s for s in st.session_state.services if s["name"] == service_name), None)
            if not svc: return "未找到追加的项目"
            start_time = base_end; end_time = start_time + timedelta(minutes=svc["minutes"])
            msg = has_conflict(emp, start_time, end_time)
            if msg: return msg
            new_rec = {"customer_id": st.session_state._customer_seq, "service": svc["name"], "minutes": svc["minutes"], "employee": emp, "start": start_time, "end": end_time, "price": svc["price"], "status": "排队中" if start_time > now() else ("进行中" if end_time > now() else "已完成"), "pay_cash": 0.0, "pay_transfer": 0.0, "pay_eftpos": 0.0, "pay_voucher": 0.0, "payment_note": "追加项目"}
            st.session_state._customer_seq += 1; st.session_state.assignments.append(new_rec)
            for e in st.session_state.employees:
                if e["name"] == emp:
                    if e["next_free"] < end_time: e["next_free"] = end_time
                    e["served_count"] += 1
                    break
            save_state(); return None
        else:
            minutes = int(extra_minutes)
            start_time = base_end; end_time = start_time + timedelta(minutes=minutes)
            msg = has_conflict(emp, start_time, end_time)
            if msg: return msg
            per_min = rec["price"] / max(rec["minutes"], 1)
            price = float(price_override) if price_override is not None else round(per_min * minutes, 2)
            new_rec = {"customer_id": st.session_state._customer_seq, "service": f"Add-on (+{minutes} mins)", "minutes": minutes, "employee": emp, "start": start_time, "end": end_time, "price": price, "status": "排队中" if start_time > now() else ("进行中" if end_time > now() else "已完成"), "pay_cash": 0.0, "pay_transfer": 0.0, "pay_eftpos": 0.0, "pay_voucher": 0.0, "payment_note": "加时"}
            st.session_state._customer_seq += 1; st.session_state.assignments.append(new_rec)
            for e in st.session_state.employees:
                if e["name"] == emp:
                    if e["next_free"] < end_time: e["next_free"] = end_time
                    e["served_count"] += 1
                    break
            save_state(); return None

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
    st.header("Coral Chinese Massage"); st.divider()
    st.subheader("服务项目（可编辑）")
    with st.expander("管理项目（时长/价格）", expanded=False):
        df_services = pd.DataFrame(st.session_state.services)
        preview = df_services.copy()
        preview["tags"] = preview["name"].apply(lambda x: ",".join(sorted(list(service_tags(x)))))
        st.caption("右侧 tags 为系统识别结果（NSH/FOOT/BACK/LEG/WHOLE/SPECIAL/OTHER）")
        edited = st.data_editor(preview, num_rows="dynamic", use_container_width=True, key="service_editor", column_config={"name":"项目名","minutes":"时长(分钟)","price":"价格($)","tags":"识别标签(只读)"}, disabled=["tags"])
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
st.title("Coral Chinese Massage排班与轮值提醒系统")
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

    
    """
    with cols[3]:
        if st.button("登记并分配", type="primary"):
            if time_mode == "使用当前时间（墨尔本）":
                t = arrival_time
            else:
                try:
                    parts = manual_time_str.strip().split(":")
                    hh, mm, ss = int(parts[0]), int(parts[1]), (int(parts[2]) if len(parts)==3 else 0)
                    t = dtime(hour=hh, minute=mm, second=ss)
                except Exception as e:
                    st.error(f"时间格式错误：{e}")
                    t = None
            if t is not None:
                arrival_dt = datetime.combine(now().date(), t, tzinfo=TZ)
                created = register_customers(service_chosen, arrival_dt, count=int(group_count))
                st.session_state.last_created = created  # 保存“刚才这次”的ID们
                # 友好提示
                a = len(created["assigned"]); w = len(created["waiting"])
                msg = "已登记与分配"
                if w > 0: msg += f"（{w} 批次进入等待队列）"
                st.success(msg)

    # --- 刚才这次登记：一键撤销 ---
    recent = st.session_state.get("last_created", {"assigned": [], "waiting": []})
    if (recent["assigned"] or recent["waiting"]):
        with st.expander("🧯 撤销刚才这次登记（误录快捷更正）", expanded=True):
            st.caption(
                f"已创建：已分配 {len(recent['assigned'])} 条，等待队列 {len(recent['waiting'])} 批。"
                " 点击下方按钮可一次性删除这些记录，然后重新填写正确信息。"
            )
            c1, c2 = st.columns([1,1])
            with c1:
                if st.button("撤销刚才这次登记", type="secondary"):
                    if recent["assigned"]:
                        delete_assignments_by_ids(recent["assigned"])
                    if recent["waiting"]:
                        delete_waiting_by_ids(recent["waiting"])
                    st.session_state.last_created = {"assigned": [], "waiting": []}
                    st.success("已撤销刚才这次登记。现在可以重新填写。")
            with c2:
                if st.button("清除撤销标记（保留记录不删除）"):
                    st.session_state.last_created = {"assigned": [], "waiting": []}
                    st.info("已清除撤销标记。")

    """
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

def eligible_employees_for(service: Dict, at_time: datetime):
    if not st.session_state.employees: return []
    emps = sorted_employees_for_rotation(); ok = []
    for e in emps:
        if not can_employee_do(e, service): continue
        start_time = max(at_time, e["next_free"]); end_time = start_time + timedelta(minutes=service["minutes"])
        msg = has_conflict(e["name"], start_time, end_time)
        if msg: continue
        ok.append({"员工": e["name"], "类型": e.get("role","正式"), "下一次空闲": start_time, "预计结束": end_time, "累计接待": e["served_count"]})
    ok = sorted(ok, key=lambda r: (r["下一次空闲"],))
    return ok

service_obj = next((s for s in st.session_state.services if s["name"] == service_chosen), None)
if st.session_state.employees and service_obj:
    eligible = eligible_employees_for(service_obj, _preview_time)
    if eligible:
        import pandas as _pd
        rows = [{"顺位": "👉 下一位" if idx == 0 else idx + 1, "员工": e["员工"], "类型": e["类型"], "可开始": fmt_t(e["下一次空闲"]), "预计结束": fmt_t(e["预计结束"]), "累计接待": e["累计接待"]} for idx, e in enumerate(eligible)]
        st.dataframe(_pd.DataFrame(rows), use_container_width=True, height=220)
        first = eligible[0]; st.success(f"可接此项目的下一位：{first['员工']}（{fmt_t(first['下一次空闲'])} 开始，至 {fmt_t(first['预计结束'])}）")
    else:
        st.warning("当前没有符合能力且不与预约/后续任务冲突的员工。")
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

# -- 看板与提醒（完整版 + 收款编辑 + 删除 + 加时/追加） --
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
                    el = []
                    for e in sorted_employees_for_rotation():
                        if not can_employee_do(e, svc): 
                            continue
                        stt = max(at_dt, e["next_free"]); edt = stt + timedelta(minutes=svc["minutes"])
                        if not has_conflict(e["name"], stt, edt):
                            el.append({"员工": e["name"], "类型": e.get("role","正式"), "可开始": stt, "预计结束": edt, "累计接待": e["served_count"]})
                    if el:
                        import pandas as _pd
                        rows = [{"顺位": "👉 下一位" if i==0 else i+1, "员工": r["员工"], "类型": r["类型"], "可开始": fmt_t(r["可开始"]), "预计结束": fmt_t(r["预计结束"]), "累计接待": r["累计接待"]} for i, r in enumerate(el)]
                        st.dataframe(_pd.DataFrame(rows), use_container_width=True, height=220)
                    else:
                        st.warning("没有符合条件的员工。")
                else:
                    st.error("未找到该项目。")
            except Exception as _e:
                st.error(f"时间格式错误：{_e}")
    with right:
        st.markdown("##### 今日全部记录")
        if st.session_state.assignments:
            df_all = pd.DataFrame([{"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"]), "价格($)": r["price"], "状态": r["status"]} for r in sorted(st.session_state.assignments, key=lambda x: (x["start"], x["customer_id"]))])
            st.dataframe(df_all, use_container_width=True, height=300)
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

            # 员工营业额统计（含收款注释）
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
                #per_emp["收款注释"] = per_emp.apply(note, axis=1)
                per_emp.rename(columns={"employee":"员工","realized":"营业额($)"}, inplace=True)
                st.markdown("###### 员工营业额统计（今日）")
                st.dataframe(per_emp[["员工","营业额($)"]], use_container_width=True, height=260)
                #st.dataframe(per_emp[["员工","营业额($)","收款注释"]], use_container_width=True, height=260)  

            # 误录删除 / 加时·追加（保留一份在看板页，主操作位在登记页）
            st.markdown("###### 误录删除 / 加时 · 追加项目")
            colA, colB = st.columns(2)
            with colA:
                delids = st.multiselect("选择要删除的记录（客户ID）", [r["customer_id"] for r in st.session_state.assignments], key="del_assign_ids_full")
                if st.button("删除所选记录", disabled=not delids): delete_assignments_by_ids(delids); st.success("已删除所选记录，并已重算员工轮值。")
            with colB:
                target_id = st.selectbox("选择要加时/追加的记录（客户ID）", [r["customer_id"] for r in st.session_state.assignments], key="target_rec_id")
                mode = st.radio("追加方式", ["延长当前服务", "另起一单（紧接着）"], horizontal=True, key="addon_mode")
                extra_minutes = st.number_input("加时/追加时长（分钟）", min_value=5, max_value=180, step=5, value=10, key="addon_minutes")
                as_new_service = None
                if mode == "另起一单（紧接着）":
                    as_new_service = st.selectbox("选择追加的项目（可选）", ["仅加时（无项目名）"] + [s["name"] for s in st.session_state.services], key="addon_service_sel")
                price_override = st.text_input("自定义价格（可选，留空则按每分钟单价或项目价）", value="", key="addon_price")
                if st.button("应用加时/追加", key="btn_apply_addon"):
                    try:
                        pid = int(target_id)
                        minutes = int(extra_minutes)
                        override = float(price_override) if price_override.strip() else None
                        if mode == "延长当前服务":
                            err = extend_or_add_on(pid, "extend", minutes, price_override=override)
                        else:
                            svc_name = None if (not as_new_service or as_new_service=="仅加时（无项目名）") else as_new_service
                            err = extend_or_add_on(pid, "add", minutes, service_name=svc_name, price_override=override)
                        if err: st.error(f"无法追加：{err}")
                        else: st.success("已完成加时/追加。")
                    except Exception as e:
                        st.error(f"操作失败：{e}")
        else:
            st.caption("今天还没有记录。")
    st.divider()
    st.markdown("### 📆 预约与占用时间轴（今日）")
    def build_timeline_blocks():
        rows = []
        day_start = datetime.combine(now().date(), dtime(hour=0, minute=0, second=0), tzinfo=TZ)
        day_end   = datetime.combine(now().date(), dtime(hour=23, minute=59, second=59), tzinfo=TZ)
        for r in st.session_state.assignments:
            s = max(r["start"], day_start); e = min(r["end"], day_end)
            if e > s: rows.append({"员工": r["employee"], "类型": "服务", "标签": r["service"], "开始": s, "结束": e})
        for rv in st.session_state.reservations:
            if rv.get("status","pending") == "done": continue
            svc = next((s for s in st.session_state.services if s["name"] == rv["service"]), None)
            minutes = int(svc["minutes"]) if svc and "minutes" in svc else 30
            s = rv["start"]; e = s + timedelta(minutes=minutes)
            if e < day_start or s > day_end: continue
            s = max(s, day_start); e = min(e, day_end)
            if e > s: rows.append({"员工": rv["employee"], "类型": "预约", "标签": f'{rv["service"]}（{rv["customer"]}）', "开始": s, "结束": e})
        return pd.DataFrame(rows, columns=["员工","类型","标签","开始","结束"])

    df_tl = build_timeline_blocks()
    if df_tl.empty:
        st.caption("今日暂无预约或占用时段。")
    else:
        emp_opts = sorted(df_tl["员工"].unique().tolist())
        sel = st.multiselect("筛选员工", emp_opts, default=emp_opts, key="tl_emp_filter")
        v = df_tl[df_tl["员工"].isin(sel)] if sel else df_tl.head(0)
        if v.empty:
            st.caption("所选员工暂无数据。")
        else:
            chart = alt.Chart(v).mark_bar().encode(
                x=alt.X('开始:T', title='时间'),
                x2='结束:T',
                y=alt.Y('员工:N', sort=emp_opts, title='员工'),
                color=alt.Color('类型:N', legend=alt.Legend(title="类型")),
                tooltip=['员工','类型','标签','开始','结束']
            ).properties(height=max(160, 40*len(emp_opts)))
            st.altair_chart(chart, use_container_width=True)

st.divider()
with st.expander("📘 使用说明（简要）", expanded=False):
    st.markdown('''
**核心规则**
- 员工按签到先后进入轮值；分配时按 **下一次空闲时间 → 签到时间 → 累计接待** 排序。
- 自动分配会考虑：**员工能力（NS/NSHe/Foot）** + **未来预约与已排任务的占档冲突**。
- 新员工-初级：只可 NS / NSHe；新员工-中级：NS / NSHe / 脚(F/NSF/NSHeF)；其它(含背/腿/全身/特殊治疗)仅正式可做。

**加时与追加项目**
- 在“看板与提醒 → 今日全部记录”中选择一条记录：
  - **延长当前服务**：直接把该单的结束时间后移，同时按原“每分钟单价”追加价格（也可自定义单价）。
  - **另起一单（紧接着）**：在该单结束时刻新增一条“加时X分钟”或选择任意项目的追加单。
- 系统会检查与该员工未来的**预约与后续分配**是否冲突，若冲突会提示并阻止。

**导出与清空**
- 侧边栏可下载今日 CSV 记录，包含客户、员工、时间与价格信息。
- “清空今日数据”会重置当日数据（包括签到），用于新的一天。
''')
