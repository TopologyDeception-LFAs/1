
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional

st.set_page_config(page_title="门店排班与轮值管理", layout="wide")

# ---------- Utilities ----------
def parse_time(t: datetime | str) -> datetime:
    if isinstance(t, datetime):
        return t
    return datetime.fromisoformat(t)

def fmt(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""

def fmt_t(dt: Optional[datetime]) -> str:
    return dt.strftime("%H:%M") if dt else ""

def now() -> datetime:
    return datetime.now()

TZ = ZoneInfo('Australia/Melbourne')

def now() -> datetime:
    return datetime.now(TZ)
    
# ---------- Session state init ----------
if "employees" not in st.session_state:
    st.session_state.employees: List[Dict] = []

if "services" not in st.session_state:
    # Preloaded services based on the price list image (each duration/price is a standalone option)
    st.session_state.services: List[Dict] = [
        # --- Deep Tissue Oil, Relaxation, Dry Massage ---
        {"name": "NS (20 mins)", "minutes": 20, "price": 40.0},
        {"name": "NS (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "NSH (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "NSH (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "BH (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "BH (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "L (30 mins)", "minutes": 30, "price": 50.0},
        {"name": "L (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "NSB (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "NSB (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSAH (45 mins)", "minutes": 45, "price": 75.0},
        {"name": "NSAH (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSBH (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "NSBH (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "BL (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "BL (60 mins)", "minutes": 60, "price": 100.0},
        {"name": "NSBAH (50 mins)", "minutes": 50, "price": 85.0},
        {"name": "NNSBAH (70 mins)", "minutes": 70, "price": 120.0},
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
    ]

if "assignments" not in st.session_state:
    st.session_state.assignments: List[Dict] = []
    st.session_state._customer_seq = 1

if "waiting" not in st.session_state:
    st.session_state.waiting: List[Dict] = []

# ---------- Core Scheduling Logic ----------
def sorted_employees_for_rotation() -> List[Dict]:
    return sorted(
        st.session_state.employees,
        key=lambda e: (e["next_free"], e["check_in"], e["served_count"]),
    )

def assign_customer(service: Dict, arrival: datetime) -> Optional[Dict]:
    if not st.session_state.employees:
        return None

    emps = sorted_employees_for_rotation()
    chosen = emps[0]
    start_time = max(arrival, chosen["next_free"])
    end_time = start_time + timedelta(minutes=service["minutes"])

    record = {
        "customer_id": st.session_state._customer_seq,
        "service": service["name"],
        "minutes": service["minutes"],
        "employee": chosen["name"],
        "start": start_time,
        "end": end_time,
        "price": service["price"],
        "status": "进行中" if start_time <= now() < end_time else ("已完成" if end_time <= now() else "排队中"),
    }
    st.session_state._customer_seq += 1

    chosen["next_free"] = end_time
    chosen["served_count"] += 1
    for i, e in enumerate(st.session_state.employees):
        if e["name"] == chosen["name"]:
            st.session_state.employees[i] = chosen
            break

    st.session_state.assignments.append(record)
    return record

def try_flush_waiting():
    st.session_state.waiting.sort(key=lambda x: x["arrival"])
    flushed = []
    still_waiting = []
    for item in st.session_state.waiting:
        assigned_any = 0
        for _ in range(item["count"]):
            rec = assign_customer(item["service"], item["arrival"])
            if rec is None:
                still_waiting.append({
                    "customer_id": item["customer_id"],
                    "service": item["service"],
                    "arrival": item["arrival"],
                    "count": item["count"] - assigned_any
                })
                break
            assigned_any += 1
        if assigned_any == item["count"]:
            flushed.append(item)
    st.session_state.waiting = still_waiting
    return flushed

def register_customers(service_name: str, arrival: datetime, count: int = 1):
    service = next((s for s in st.session_state.services if s["name"] == service_name), None)
    if service is None:
        st.error("未找到该项目")
        return
    for i in range(count):
        rec = assign_customer(service, arrival)
        if rec is None:
            st.session_state.waiting.append({
                "customer_id": st.session_state._customer_seq,
                "service": service,
                "arrival": arrival,
                "count": count - i,
            })
            st.session_state._customer_seq += 1
            break

def refresh_status():
    changed = False
    for rec in st.session_state.assignments:
        prev = rec["status"]
        if rec["end"] <= now():
            rec["status"] = "已完成"
        elif rec["start"] <= now() < rec["end"]:
            rec["status"] = "进行中"
        else:
            rec["status"] = "排队中"
        changed = changed or (prev != rec["status"])
    return changed

# ---------- Sidebar Controls ----------
with st.sidebar:
    st.header("Coral Chinese Message")
    #st.caption("• 默认上班时间：09:00；员工先到先服务。\n• 轮值顺序：按下一次空闲时间→签到时间→累计接待。")
    st.divider()

    st.subheader("服务项目（可编辑）")
    with st.expander("管理项目（时长/价格）", expanded=False):
        df_services = pd.DataFrame(st.session_state.services)
        edited = st.data_editor(
            df_services,
            num_rows="dynamic",
            use_container_width=True,
            key="service_editor",
            column_config={
                "name": "项目名",
                "minutes": "时长(分钟)",
                "price": "价格($)",
            },
        )
        if st.button("保存项目变更"):
            clean = []
            for _, row in edited.iterrows():
                if not row["name"] or pd.isna(row["minutes"]) or pd.isna(row["price"]):
                    continue
                clean.append({"name": str(row["name"]), "minutes": int(row["minutes"]), "price": float(row["price"])})
            st.session_state.services = clean
            st.success("已保存服务项目。")

    st.subheader("数据导出")
    if st.session_state.assignments:
        df_export = pd.DataFrame([
            {
                "客户ID": rec["customer_id"],
                "项目": rec["service"],
                "时长(分钟)": rec["minutes"],
                "员工": rec["employee"],
                "开始时间": fmt(rec["start"]),
                "结束时间": fmt(rec["end"]),
                "价格($)": rec["price"],
                "状态": rec["status"],
            }
            for rec in st.session_state.assignments
        ])
        st.download_button("下载今日记录 CSV", df_export.to_csv(index=False).encode("utf-8-sig"), file_name=f"records_{now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
    if st.button("清空今日数据（新一天）", type="primary"):
        # 新的一天：重置所有数据，包括员工签到与轮值顺序
        st.session_state.assignments = []
        st.session_state.waiting = []
        st.session_state.employees = []
        st.session_state._customer_seq = 1
        st.toast("已清空：员工、等待队列与当日记录均已重置。")

# ---------- Main Layout ----------
st.title("Coral Chinese Message")

tab_emp, tab_cus, tab_board = st.tabs(["员工签到/状态", "登记顾客/自动分配", "看板与提醒"])

with tab_emp:
    st.subheader("员工签到（先到先服务）")
    cols = st.columns(3)
    with cols[0]:
        emp_name = st.text_input("员工姓名", placeholder="例如：小张 / Lily")
    with cols[1]:
        check_in_time = st.time_input("签到时间", value=datetime.now().replace(hour=9, minute=0, second=0, microsecond=0).time(), step=60)
    with cols[2]:
        if st.button("签到/上班", type="primary"):
            if emp_name:
                t = datetime.combine(datetime.today().date(), check_in_time)
                st.session_state.employees.append({
                    "name": emp_name.strip(),
                    "check_in": t,
                    "next_free": t,
                    "served_count": 0,
                })
                st.session_state.employees = sorted(st.session_state.employees, key=lambda e: e["check_in"])
                st.success(f"{emp_name} 已签到。")
                try_flush_waiting()
            else:
                st.error("请输入员工姓名。")

    if st.session_state.employees:
        st.markdown("#### 员工列表")
        df_emp = pd.DataFrame([
            {
                "员工": e["name"],
                "签到": fmt_t(e["check_in"]),
                "下一次空闲": fmt_t(e["next_free"]),
                "累计接待": e["served_count"],
            }
            for e in sorted_employees_for_rotation()
        ])
        st.dataframe(df_emp, use_container_width=True)
    else:
        st.info("暂无员工签到。")

with tab_cus:
    st.subheader("登记顾客（按轮值自动分配）")
    cols = st.columns(4)
    all_service_names = [s["name"] for s in st.session_state.services]
    with cols[0]:
        service_chosen = st.selectbox("项目", all_service_names, index=0)
    with cols[1]:
        time_mode = st.radio("开始时间", ["使用当前时间", "手动输入"], horizontal=True, index=0)
        if time_mode == "使用当前时间":
            arrival_time = datetime.now().time()
            st.caption(f"当前时间：{arrival_time.strftime('%H:%M:%S')}")
            manual_time_str = None
        else:
            manual_time_str = st.text_input("手动输入到店时间（HH:MM 或 HH:MM:SS）", value=now().strftime("%H:%M"))
            arrival_time = None
    with cols[2]:
        group_count = st.number_input("同时到店人数（相同项目）", min_value=1, max_value=20, value=1, step=1)
    with cols[3]:
        if st.button("登记并分配", type="primary"):
            # 解析时间
            if time_mode == "使用当前时间":
                t = arrival_time
            else:
                try:
                    parts = manual_time_str.strip().split(":")
                    if len(parts) == 2:
                        hh, mm = int(parts[0]), int(parts[1])
                        ss = 0
                    elif len(parts) == 3:
                        hh, mm, ss = int(parts[0]), int(parts[1]), int(parts[2])
                    else:
                        raise ValueError("时间格式不正确")
                    from datetime import time as dtime
                    t = dtime(hour=hh, minute=mm, second=ss)
                except Exception as e:
                    st.error(f"时间格式错误，请按 HH:MM 或 HH:MM:SS 输入。例如 11:32 或 11:32:00。错误：{e}")
                    t = None
            if t is not None:
                arrival_dt = datetime.combine(datetime.today().date(), t)
                register_customers(service_chosen, arrival_dt, count=int(group_count))
                st.success("已登记与分配（不足时将加入等待队）。")
    

    st.divider()
    st.markdown("#### 等待队列")
    if st.session_state.waiting:
        df_wait = pd.DataFrame([
            {"批次客户ID": w["customer_id"], "项目": w["service"]["name"], "人数": w["count"], "到店": fmt_t(w["arrival"])}
            for w in st.session_state.waiting
        ])
        st.dataframe(df_wait, use_container_width=True)
        if st.button("尝试为等待队列重新分配"):
            flushed = try_flush_waiting()
            if flushed:
                st.success(f"已重新分配 {sum(x['count'] for x in flushed)} 位顾客。")
            else:
                st.info("暂无可分配的员工空闲。")
    else:
        st.caption("当前没有等待中的顾客。")

with tab_board:
    st.subheader("实时看板")
    refresh_status()

    left, right = st.columns(2)

    with left:
        st.markdown("##### 进行中")
        active = [r for r in st.session_state.assignments if r["status"] == "进行中"]
        if active:
            df_act = pd.DataFrame([
                {"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"]), "剩余(分)": max(0, int((r["end"] - now()).total_seconds() // 60))}
                for r in sorted(active, key=lambda x: x["end"])
            ])
            st.dataframe(df_act, use_container_width=True, height=280)
        else:
            st.caption("暂无进行中的服务。")

        # 新增：排队中/等待队列展示
        st.markdown("##### 排队中（已分配，未开始）")
        queued = [r for r in st.session_state.assignments if r["status"] == "排队中"]
        if queued:
            df_q = pd.DataFrame([
                {"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"])}
                for r in sorted(queued, key=lambda x: x["start"])
            ])
            st.dataframe(df_q, use_container_width=True, height=220)
        else:
            st.caption("暂无排队中的记录。")

        st.markdown("##### 等待分配（未指派员工）")
        if st.session_state.waiting:
            df_w = pd.DataFrame([
                {"批次客户ID": w["customer_id"], "项目": w["service"]["name"], "人数": w["count"], "到店": fmt_t(w["arrival"])}
                for w in sorted(st.session_state.waiting, key=lambda x: x["arrival"])
            ])
            st.dataframe(df_w, use_container_width=True, height=220)
        else:
            st.caption("暂无等待分配的顾客。")

        # 新增：员工轮值队列（下一位 →）
        st.markdown("##### 员工轮值队列（下一位 →）")
        if st.session_state.employees:
            rotation = sorted_employees_for_rotation()
            rows = []
            for idx, e in enumerate(rotation):
                status = "空闲" if e["next_free"] <= now() else f"忙碌至 {fmt_t(e['next_free'])}"
                rows.append({
                    "顺位": "👉 下一位" if idx == 0 else idx + 1,
                    "员工": e["name"],
                    "状态": status,
                    "下一次空闲": fmt_t(e["next_free"]),
                    "累计接待": e["served_count"],
                })
            import pandas as pd
            df_rot = pd.DataFrame(rows)
            st.dataframe(df_rot, use_container_width=True, height=260)
            # 贴士：给出下一位员工的预计等待时间
            nxt = rotation[0]
            mins = max(0, int((nxt["next_free"] - now()).total_seconds() // 60))
            if mins == 0:
                st.success(f"下一位应接单员工：{nxt['name']}（可立即接待）")
            else:
                st.info(f"下一位应接单员工：{nxt['name']}（预计 {mins} 分钟后空闲，{fmt_t(nxt['next_free'])}）")
        else:
            st.caption("暂无员工签到。")

        st.markdown("##### 即将空闲提醒（按结束时间）")
        coming_free = sorted(st.session_state.assignments, key=lambda r: r["end"])
        coming_free = [r for r in coming_free if r["end"] > now()]
        if coming_free:
            nxt = coming_free[:5]
            for r in nxt:
                mins = int((r["end"] - now()).total_seconds() // 60)
                st.info(f"员工 {r['employee']} 将在 {mins} 分钟后空闲（到 {fmt_t(r['end'])} 结束）。")
        else:
            st.caption("暂无即将空闲的提醒。")

    with right:
        st.markdown("##### 今日全部记录")
        if st.session_state.assignments:
            df_all = pd.DataFrame([
                {"客户ID": r["customer_id"], "员工": r["employee"], "项目": r["service"], "开始": fmt_t(r["start"]), "结束": fmt_t(r["end"]), "价格($)": r["price"], "状态": r["status"]}
                for r in sorted(st.session_state.assignments, key=lambda x: (x["start"], x["customer_id"]))
            ])
            st.dataframe(df_all, use_container_width=True, height=360)
            total_revenue = sum(r["price"] for r in st.session_state.assignments if r["status"] != "排队中")
            st.metric("今日营收(已开始/已完成)", f"${total_revenue:,.2f}")
            # 每位员工当前营业额（不含排队中）
            df_rev = pd.DataFrame([r for r in st.session_state.assignments if r["status"] != "排队中"])
            if not df_rev.empty:
                per_emp = df_rev.groupby("employee")["price"].sum().reset_index()
                per_emp.columns = ["员工", "营业额($)"]
                per_emp = per_emp.sort_values("营业额($)", ascending=False)
                st.markdown("###### 员工营业额统计（今日）")
                st.dataframe(per_emp, use_container_width=True, height=240)

        else:
            st.caption("今天还没有记录。")

st.divider()
with st.expander("📘 使用说明（简要）", expanded=False):
    st.markdown('''
**核心规则**
- 员工按签到先后进入轮值；分配时按 **下一次空闲时间 → 签到时间 → 累计接待** 排序。
- 顾客到店登记后，系统自动分配员工：
  - 如有空闲员工，立刻开工，计算开始/结束时间与价格；
  - 如无人空闲，则进入等待队列，待有人空闲再分配（可手动“尝试重新分配”）。
- 价格与时长来源于“服务项目”列表，可在侧边栏编辑保存。

**示例**
- 颈肩背 45 分钟，价格 $75：如果开始时间为 11:32，则结束时间为 12:17（45 分钟后）。
- 同时来了两位或以上顾客（相同项目），按当前轮到的员工顺序依次分配。

**建议**
- 每天营业前先为所有员工完成“签到”；默认上班时间为 09:00。
- 使用“实时看板”查看进行中的服务与即将空闲的员工，便于安排等候顾客。

**导出与清空**
- 侧边栏可下载今日 CSV 记录，包含客户、员工、时间与价格信息。
- “清空今日数据”会保留签到与轮值顺序，但重置接待记录与等待队列。
''')
