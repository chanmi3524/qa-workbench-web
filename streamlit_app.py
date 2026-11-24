
from __future__ import annotations
import json, calendar
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st

from db import (
    init_db, fetch_all, fetch_one, execute,
    create_user, verify_user, change_password, update_display_name, log_action
)
from services import (
    CHECK_RULES, criteria_text, judge_value, inspection_overall,
    create_defect_from_inspection, delivery_urgency, monthly_demand_map,
    due_tasks, extract_text_tesseract, best_effort_autofill
)
from ui import inject_css, metric, section_title

st.set_page_config(
    page_title="QA Workbench",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()
inject_css()

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "대시보드"
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"
if "ocr_values" not in st.session_state:
    st.session_state.ocr_values = {r["key"]:"" for r in CHECK_RULES}

def current_user():
    return st.session_state.user

def actor_name():
    return current_user()["display_name"]

def audit(action, entity_type, entity_id, summary):
    log_action(current_user(), action, entity_type, entity_id, summary)

def visible_tasks_sql(extra=""):
    return f"""
        SELECT * FROM tasks
        WHERE (visibility='public' OR owner_user_id=?)
        {extra}
    """

# ---------- AUTH ----------
if current_user() is None:
    st.markdown("""
    <style>
    section[data-testid="stSidebar"]{display:none!important;}
    .block-container{min-width:1100px!important;max-width:1100px!important;margin:auto!important;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="login-heading">
        <div class="login-logo">Q</div>
        <div class="login-title">QA Workbench</div>
        <div class="login-sub">사용자별 품질보증 업무 통합 관리</div>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1.25,1,1.25])
    with center:
        with st.container(border=True):
            if st.session_state.auth_mode == "login":
                st.markdown("### 로그인")
                username = st.text_input("아이디")
                password = st.text_input("비밀번호", type="password")
                if st.button("로그인", type="primary", use_container_width=True):
                    user = verify_user(username, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.page = "대시보드"
                        log_action(user, "로그인", "사용자", user["id"], "QA Workbench 로그인")
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 맞지 않습니다.")
                if st.button("새 계정 만들기", use_container_width=True):
                    st.session_state.auth_mode = "register"
                    st.rerun()
                st.caption("처음 사용하는 사람은 ‘새 계정 만들기’에서 등록하면 됩니다.")
            else:
                st.markdown("### 새 계정 만들기")
                username = st.text_input("아이디", key="reg_user")
                display = st.text_input("이름", key="reg_name")
                p1 = st.text_input("비밀번호", type="password", key="reg_pw1")
                p2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
                if st.button("계정 생성", type="primary", use_container_width=True):
                    if p1 != p2:
                        st.error("비밀번호가 서로 다릅니다.")
                    else:
                        try:
                            user = create_user(username, display, p1)
                            log_action(user, "계정 생성", "사용자", user["id"], f'{user["display_name"]} 계정 생성')
                            st.session_state.user = user
                            st.session_state.page = "대시보드"
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                if st.button("로그인으로 돌아가기", use_container_width=True):
                    st.session_state.auth_mode = "login"
                    st.rerun()
    st.stop()

user = current_user()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
      <div class="sidebar-logo">Q</div>
      <div class="sidebar-title">QA<br>Workbench</div>
    </div>
    """, unsafe_allow_html=True)

    nav = [
        ("⌂  대시보드","대시보드"),
        ("▣  검사관리","검사관리"),
        ("△  불량관리","불량관리"),
        ("▦  일정 · 할일","일정 · 할일"),
        ("■  납품일정","납품일정"),
        ("◇  ERP / BOM","ERP / BOM"),
        ("☷  활동 이력","활동 이력"),
    ]
    for label, target in nav:
        if st.button(label, key=f"nav_{target}", use_container_width=True):
            st.session_state.page = target
            st.rerun()

    st.markdown(
        f'<div class="sidebar-user">{user["display_name"]}<br>@{user["username"]} · {user["role"]}</div>',
        unsafe_allow_html=True
    )

    if st.button("⚙  사용자 설정", use_container_width=True):
        st.session_state.page = "사용자 설정"
        st.rerun()
    if st.button("↪  로그아웃", use_container_width=True):
        audit("로그아웃", "사용자", user["id"], "QA Workbench 로그아웃")
        st.session_state.user = None
        st.rerun()

# ---------- TOP BAR ----------
st.markdown(f"""
<div class="qa-topbar">
  <div class="qa-brand">QA Workbench</div>
  <div class="qa-search">⌕　품번, 품명, 불량내용 등을 검색...</div>
  <div class="qa-user-top">{user["display_name"]} · @{user["username"]}</div>
</div>
""", unsafe_allow_html=True)

page = st.session_state.page

for task in due_tasks(user["id"])[:3]:
    scope = "개인" if task.get("visibility") == "private" else "공용"
    st.toast(f'⏰ [{scope}] {task["title"]} · {task["due_date"]} {task["due_time"]}')
    execute("UPDATE tasks SET alarm_notified=1 WHERE id=?", (task["id"],))

# ---------- SETTINGS ----------
if page == "사용자 설정":
    section_title("사용자 설정","내 이름과 비밀번호를 변경합니다.")
    c1, c2 = st.columns([1,1.5])
    with c1:
        with st.container(border=True):
            new_name = st.text_input("표시 이름", value=user["display_name"])
            old_pw = st.text_input("현재 비밀번호", type="password")
            p1 = st.text_input("새 비밀번호", type="password")
            p2 = st.text_input("새 비밀번호 확인", type="password")

            if st.button("이름 변경", use_container_width=True):
                try:
                    before = user["display_name"]
                    update_display_name(user["id"], new_name)
                    user["display_name"] = new_name.strip()
                    st.session_state.user = user
                    audit("수정", "사용자", user["id"], f"표시 이름 변경: {before} → {new_name.strip()}")
                    st.success("이름을 변경했습니다.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

            if st.button("비밀번호 변경", type="primary", use_container_width=True):
                if p1 != p2:
                    st.error("새 비밀번호가 서로 다릅니다.")
                else:
                    try:
                        change_password(user["id"], old_pw, p1)
                        audit("수정", "사용자", user["id"], "비밀번호 변경")
                        st.success("비밀번호를 변경했습니다.")
                    except ValueError as e:
                        st.error(str(e))
    st.stop()

# ---------- DASHBOARD ----------
elif page == "대시보드":
    section_title("품질 대시보드")
    inspections = fetch_all("SELECT * FROM inspections")
    total = len(inspections)
    ok = sum(1 for x in inspections if x["result"] == "합격")
    ng = total - ok
    open_def = (fetch_one("SELECT COUNT(*) c FROM defects WHERE status!='완료'") or {"c":0})["c"]

    c1,c2,c3,c4 = st.columns(4)
    with c1: metric("총 검사",f"{total}건","누적 검사 건수")
    with c2: metric("양품",f"{ok}건","합격 판정")
    with c3: metric("불량",f"{ng}건","불합격 판정")
    with c4: metric("미종결",f"{open_def}건","조치 진행 중")

    left,right = st.columns([3.25,1.15], gap="medium")
    with left:
        st.markdown("### 업무 달력")
        f1,f2,f3 = st.columns([1.1,1.1,1.5])
        td = date.today()
        with f1:
            year = st.selectbox("연도", range(td.year-1,td.year+3), index=1, key="dy")
        with f2:
            month = st.selectbox("월", range(1,13), index=td.month-1, key="dm")
        with f3:
            cal_filter = st.selectbox("일정 표시", ["공용 + 내 개인","공용만","내 개인만"])

        task_rows = fetch_all(
            visible_tasks_sql("AND status!='삭제' ORDER BY due_date,due_time"),
            (user["id"],)
        )
        if cal_filter == "공용만":
            task_rows = [t for t in task_rows if t.get("visibility") == "public"]
        elif cal_filter == "내 개인만":
            task_rows = [t for t in task_rows if t.get("visibility") == "private" and t.get("owner_user_id") == user["id"]]

        events = {}
        for t in task_rows:
            if t["due_date"].startswith(f"{year:04d}-{month:02d}"):
                icon = "👤" if t.get("visibility") == "private" else "🌐"
                events.setdefault(t["due_date"],[]).append(
                    f'{icon} {t["due_time"] or ""} [{t["category"]}] {t["title"]}'
                )
        if cal_filter != "내 개인만":
            for d in fetch_all("SELECT * FROM deliveries"):
                if d["due_date"].startswith(f"{year:04d}-{month:02d}"):
                    events.setdefault(d["due_date"],[]).append(
                        f'📦 [{d["item_code"]}] {d["item_name"]} · {d["process"]}'
                    )

        heads = st.columns(7)
        for i,h in enumerate(["월","화","수","목","금","토","일"]):
            heads[i].markdown(f"**{h}**")
        for week in calendar.Calendar().monthdayscalendar(year,month):
            cols = st.columns(7)
            for i,day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.markdown('<div class="calendar-cell"></div>', unsafe_allow_html=True)
                    else:
                        ds = f"{year:04d}-{month:02d}-{day:02d}"
                        body = "<br>".join(events.get(ds,[])[:4])
                        st.markdown(
                            f'<div class="calendar-cell"><div class="calendar-day">{day}</div>{body}</div>',
                            unsafe_allow_html=True
                        )

    with right:
        st.markdown("### 최근 불량 / 조치 현황")
        st.dataframe(pd.DataFrame(fetch_all("""
            SELECT defect_date,item_code,item_name,issue,status
            FROM defects ORDER BY id DESC LIMIT 6
        """)), use_container_width=True, hide_index=True, height=250)

        st.markdown("### 다가오는 일정 · 할일")
        upcoming = fetch_all(
            visible_tasks_sql("AND status!='완료' ORDER BY due_date,due_time LIMIT 8"),
            (user["id"],)
        )
        up_display = []
        for t in upcoming:
            up_display.append({
                "기한": f'{t["due_date"]} {t.get("due_time") or ""}',
                "범위": "개인" if t.get("visibility") == "private" else "공용",
                "내용": t["title"],
                "상태": t["status"],
            })
        st.dataframe(pd.DataFrame(up_display), use_container_width=True, hide_index=True, height=220)

        st.markdown("### 최근 활동")
        recent = fetch_all("""
            SELECT created_at,display_name,action,summary
            FROM audit_log ORDER BY id DESC LIMIT 5
        """)
        st.dataframe(pd.DataFrame(recent), use_container_width=True, hide_index=True, height=190)

# ---------- INSPECTION ----------
elif page == "검사관리":
    section_title("검사관리","스캔 체크시트의 측정값을 확인하고 자동 합·불 판정")
    tab1,tab2 = st.tabs(["검사 이력","검사 등록"])

    with tab1:
        rows = fetch_all("""
            SELECT id,inspection_date,inspection_type,item_code,item_name,supplier,lot,
                   qty,sample_qty,result,note,created_by,updated_by
            FROM inspections ORDER BY id DESC
        """)
        if rows:
            df = pd.DataFrame(rows)
            def sty(r):
                c = "#eaf8ee" if r["result"] == "합격" else "#fdebec"
                return [f"background-color:{c}"]*len(r)
            st.dataframe(df.style.apply(sty,axis=1), use_container_width=True, hide_index=True)

    with tab2:
        a,b,c = st.columns(3)
        d = a.date_input("검사일", date.today())
        typ = b.selectbox("검사구분", ["입고검사","공정검사","출하검사","기타"])
        code = c.text_input("품번")
        a,b,c = st.columns(3)
        item = a.text_input("품명")
        supplier = b.text_input("업체")
        lot = c.text_input("LOT")
        a,b = st.columns(2)
        qty = a.number_input("입고/생산수량", 0.0)
        sample = b.number_input("검사수량", 0.0)

        up = st.file_uploader("체크시트 이미지", type=["png","jpg","jpeg"])
        if up is not None:
            st.image(up, width=380)
            if st.button("OCR 자동 인식", type="primary"):
                txt = extract_text_tesseract(up)
                st.session_state.ocr_values.update(best_effort_autofill(txt))
                st.success("OCR 결과를 아래에서 확인/수정해 주세요." if txt else "OCR이 읽지 못했습니다. 값을 직접 입력해 주세요.")

        details = []
        st.markdown("#### 인식 결과 확인 / 수정")
        for rule in CHECK_RULES:
            c1,c2,c3,c4 = st.columns([2,2,2,1])
            c1.write(rule["label"])
            c2.write(criteria_text(rule))
            val = c3.text_input(
                "측정값",
                value=st.session_state.ocr_values.get(rule["key"],""),
                key=f'ocr_{rule["key"]}',
                label_visibility="collapsed"
            )
            st.session_state.ocr_values[rule["key"]] = val
            verdict = judge_value(rule,val)
            c4.write(verdict)
            details.append({
                "label":rule["label"],"criteria":criteria_text(rule),
                "value":val,"verdict":verdict
            })

        overall = inspection_overall(details)
        st.info(f"최종 판정: **{overall}**")
        note = st.text_input("특이사항")
        if st.button("검사 기록 저장", type="primary", use_container_width=True):
            iid = execute("""INSERT INTO inspections(
                inspection_date,inspection_type,item_code,item_name,supplier,lot,
                qty,sample_qty,result,note,details_json,created_by,updated_by
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(d),typ,code,item,supplier,lot,qty,sample,overall,note,
                json.dumps(details,ensure_ascii=False), actor_name(), actor_name()
            ))
            audit("추가", "검사", iid, f"{code or item or '검사'} · {overall} 등록")
            if overall == "불합격":
                defect_id = create_defect_from_inspection(
                    iid, code, item, sample, details, created_by=actor_name()
                )
                if defect_id:
                    audit("자동 추가", "불량", defect_id, f"검사 #{iid} 불합격 자동 연계")
                st.warning("불량관리에도 자동 등록했습니다.")
            else:
                st.success("저장했습니다.")

# ---------- DEFECT ----------
elif page == "불량관리":
    section_title("불량관리","검사 NG 자동연계 및 조치 이력 추적")
    rows = fetch_all("SELECT * FROM defects ORDER BY id DESC")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("불량 수동 등록"):
        d = st.date_input("발생일", date.today())
        a,b,c = st.columns(3)
        code = a.text_input("품번", key="dc")
        item = b.text_input("품명", key="dn")
        q = c.number_input("수량", 0.0, key="dq")
        issue = st.text_input("불량현상")
        if st.button("불량 등록"):
            did = execute("""INSERT INTO defects(
                defect_date,source,item_code,item_name,issue,qty,status,created_by,updated_by
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (str(d),"수동등록",code,item,issue,q,"접수",actor_name(),actor_name()))
            audit("추가", "불량", did, f"{code or item or '불량'} · {issue}")
            st.rerun()

    if rows:
        sid = st.selectbox("조치할 불량", [r["id"] for r in rows])
        rec = fetch_one("SELECT * FROM defects WHERE id=?", (sid,))
        a,b,c = st.columns(3)
        statuses = ["접수","원인분석","조치중","확인대기","완료"]
        status = a.selectbox(
            "상태", statuses,
            index=statuses.index(rec["status"]) if rec["status"] in statuses else 0
        )
        owner = b.text_input("담당/부서", value=rec["owner"] or "")
        due = c.text_input("조치기한", value=rec["due_date"] or "")
        action = st.text_area("조치내용", value=rec["action"] or "")
        if st.button("조치사항 저장", type="primary"):
            before = rec["status"]
            execute(
                "UPDATE defects SET status=?,owner=?,due_date=?,action=?,updated_by=? WHERE id=?",
                (status,owner,due,action,actor_name(),sid)
            )
            audit("수정", "불량", sid, f"상태 {before} → {status} / 조치내용 수정")
            st.success("저장했습니다.")

# ---------- TASK ----------
elif page == "일정 · 할일":
    section_title("일정 · 할일","공용 일정과 나만 보는 개인 일정을 구분해 관리합니다.")

    task_filter = st.radio(
        "보기",
        ["공용 + 내 개인","공용만","내 개인만"],
        horizontal=True
    )
    rows = fetch_all(
        visible_tasks_sql("ORDER BY due_date,due_time"),
        (user["id"],)
    )
    if task_filter == "공용만":
        rows = [r for r in rows if r.get("visibility") == "public"]
    elif task_filter == "내 개인만":
        rows = [r for r in rows if r.get("visibility") == "private" and r.get("owner_user_id") == user["id"]]

    display = []
    for r in rows:
        display.append({
            "ID":r["id"],
            "날짜":r["due_date"],
            "시간":r.get("due_time") or "",
            "범위":"개인" if r.get("visibility") == "private" else "공용",
            "작성자":r.get("owner_name") or "기존 일정",
            "구분":r.get("category") or "",
            "업무내용":r["title"],
            "상태":r["status"],
            "메모":r.get("note") or "",
        })
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)

    with st.expander("새 일정 등록", expanded=True):
        with st.form("task_form", clear_on_submit=True):
            a,b,c = st.columns(3)
            d = a.date_input("날짜", date.today())
            tm = b.time_input("시간", datetime.now().replace(second=0,microsecond=0).time())
            cat = c.selectbox("구분", ["검사","불량조치","회신대기","문서","교정","납품","회의","기타"])
            title = st.text_input("업무내용")
            note = st.text_input("메모")
            a,b = st.columns(2)
            visibility_label = a.selectbox(
                "공개 범위",
                ["공용 - 로그인한 모든 사람이 봄","개인 - 나만 봄"]
            )
            alarm = b.checkbox("설정 시간이 되면 알림", True)
            if st.form_submit_button("일정 등록", type="primary") and title:
                visibility = "private" if visibility_label.startswith("개인") else "public"
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tid = execute("""INSERT INTO tasks(
                    due_date,due_time,category,title,status,note,alarm_enabled,alarm_notified,
                    visibility,owner_user_id,owner_name,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(d),tm.strftime("%H:%M"),cat,title,"진행",note,
                    1 if alarm else 0,0,visibility,user["id"],actor_name(),now,now
                ))
                scope = "개인" if visibility == "private" else "공용"
                audit("추가", "일정", tid, f"[{scope}] {str(d)} {tm.strftime('%H:%M')} · {title}")
                st.rerun()

    own_rows = [r for r in rows if r.get("owner_user_id") == user["id"]]
    public_rows = [r for r in rows if r.get("visibility") == "public"]
    manageable = {r["id"]:r for r in (own_rows + public_rows)}
    if manageable:
        st.markdown("#### 일정 수정 / 완료 / 삭제")
        selected_id = st.selectbox(
            "대상 일정",
            list(manageable.keys()),
            format_func=lambda x: f'#{x} · {manageable[x]["due_date"]} · {manageable[x]["title"]}'
        )
        rec = manageable[selected_id]
        a,b,c = st.columns(3)
        new_title = a.text_input("업무내용 수정", value=rec["title"])
        new_status = b.selectbox(
            "상태", ["진행","완료"],
            index=1 if rec["status"] == "완료" else 0
        )
        new_scope_label = c.selectbox(
            "공개 범위",
            ["공용","개인"],
            index=1 if rec.get("visibility") == "private" else 0
        )
        new_note = st.text_input("메모 수정", value=rec.get("note") or "")
        c1,c2 = st.columns(2)
        if c1.button("일정 수정 저장", type="primary", use_container_width=True):
            new_visibility = "private" if new_scope_label == "개인" else "public"
            # Public tasks can be edited by users; private tasks can only be edited by owner.
            if rec.get("visibility") == "private" and rec.get("owner_user_id") != user["id"]:
                st.error("다른 사용자의 개인 일정은 수정할 수 없습니다.")
            else:
                execute(
                    """UPDATE tasks SET title=?,status=?,visibility=?,note=?,updated_at=? WHERE id=?""",
                    (
                        new_title,new_status,new_visibility,new_note,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),selected_id
                    )
                )
                audit(
                    "수정","일정",selected_id,
                    f'{rec["title"]} → {new_title} / 상태 {rec["status"]} → {new_status} / 범위 {new_scope_label}'
                )
                st.rerun()

        if c2.button("일정 삭제", use_container_width=True):
            if rec.get("visibility") == "private" and rec.get("owner_user_id") != user["id"]:
                st.error("다른 사용자의 개인 일정은 삭제할 수 없습니다.")
            else:
                summary = f'{rec["due_date"]} {rec.get("due_time") or ""} · {rec["title"]}'
                execute("DELETE FROM tasks WHERE id=?", (selected_id,))
                audit("삭제","일정",selected_id,summary)
                st.rerun()

# ---------- DELIVERY ----------
elif page == "납품일정":
    section_title("납품일정","제품별 납기·공정 진행 상태 통합 관리")
    rows = fetch_all("SELECT * FROM deliveries ORDER BY due_date")
    if rows:
        df = pd.DataFrame(rows)
        def sty(r):
            _,c = delivery_urgency(str(r["due_date"]))
            return [f"background-color:{c}"]*len(r)
        st.dataframe(df.style.apply(sty,axis=1), use_container_width=True, hide_index=True)

    with st.expander("납품일정 등록"):
        with st.form("delivery_form", clear_on_submit=True):
            a,b,c = st.columns(3)
            due = a.date_input("납품일", date.today()+timedelta(days=30))
            cust = b.text_input("고객사")
            proj = c.text_input("프로젝트")
            a,b,c = st.columns(3)
            code = a.text_input("품번")
            item = b.text_input("품명")
            qty = c.number_input("수량", 0.0)
            plist = ["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"]
            process = st.selectbox("초기공정", plist)
            if st.form_submit_button("등록", type="primary"):
                did = execute("""INSERT INTO deliveries(
                    due_date,customer,project,item_code,item_name,qty,process,progress,status,created_by,updated_by
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (str(due),cust,proj,code,item,qty,process,0,"진행중",actor_name(),actor_name()))
                audit("추가","납품일정",did,f"{code or item} · 납기 {due} · {qty}EA")
                st.rerun()

    if rows:
        did = st.selectbox("변경할 일정", [r["id"] for r in rows])
        rec = fetch_one("SELECT * FROM deliveries WHERE id=?", (did,))
        a,b,c = st.columns(3)
        nd = a.date_input("변경 납기", datetime.strptime(rec["due_date"],"%Y-%m-%d").date())
        plist = ["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"]
        pr = b.selectbox("현재공정", plist, index=plist.index(rec["process"]) if rec["process"] in plist else 0)
        pg = c.slider("진행률",0,100,int(rec["progress"] or 0))
        if st.button("변경 저장"):
            old_due = rec["due_date"]
            old_process = rec["process"]
            prev = rec["previous_due"] or rec["due_date"]
            execute("""UPDATE deliveries
                       SET previous_due=?,due_date=?,process=?,progress=?,status=?,updated_by=?
                       WHERE id=?""",
                    (prev,str(nd),pr,pg,"완료" if pr=="납품완료" else "진행중",actor_name(),did))
            audit(
                "수정","납품일정",did,
                f"{rec['item_code'] or rec['item_name']} · 납기 {old_due} → {nd} / 공정 {old_process} → {pr}"
            )
            st.rerun()

# ---------- ERP ----------
elif page == "ERP / BOM":
    section_title("ERP / BOM 관리","품목·재고 → BOM → 생산계획별 자재소요량 관리")
    t1,t2,t3 = st.tabs(["품목 / 재고 관리","BOM 관리","생산계획 / 자재소요"])

    with t1:
        items = fetch_all("SELECT * FROM erp_items ORDER BY code")
        demand = monthly_demand_map()
        disp = []
        for x in items:
            need = float(demand.get(x["code"],0))
            bal = float(x["stock"])-need-float(x["safety_stock"])
            disp.append({
                "품목코드":x["code"],"품목명":x["name"],"구분":x["item_type"],
                "단위":x["unit"],"현재고":x["stock"],"안전재고":x["safety_stock"],
                "30일 예상소요":need,
                "30일 재고상태":("여유 " if bal>=0 else "부족 ")+str(abs(bal))
            })
        if disp:
            ddf = pd.DataFrame(disp)
            def style_stock(r):
                c = "#eaf8ee" if str(r["30일 재고상태"]).startswith("여유") else "#fdebec"
                return [f"background-color:{c}"]*len(r)
            st.dataframe(ddf.style.apply(style_stock,axis=1), use_container_width=True, hide_index=True)

    with t2:
        st.dataframe(
            pd.DataFrame(fetch_all("SELECT * FROM bom ORDER BY product_code,material_code")),
            use_container_width=True, hide_index=True
        )

    with t3:
        st.dataframe(
            pd.DataFrame(fetch_all("SELECT * FROM production_plans ORDER BY due_date")),
            use_container_width=True, hide_index=True
        )

# ---------- AUDIT LOG ----------
elif page == "활동 이력":
    section_title("활동 이력","누가, 언제, 무엇을 추가·수정·삭제했는지 확인합니다.")
    c1,c2,c3 = st.columns([1.2,1.2,2])
    with c1:
        who = st.selectbox("사용자", ["전체","내 이력"])
    with c2:
        action_filter = st.selectbox("동작", ["전체","추가","자동 추가","수정","삭제","로그인","로그아웃","계정 생성"])
    with c3:
        keyword = st.text_input("내용 검색")

    rows = fetch_all("""
        SELECT id,created_at,display_name,username,action,entity_type,entity_id,summary
        FROM audit_log ORDER BY id DESC
    """)
    if who == "내 이력":
        rows = [r for r in rows if r.get("user_id") == user["id"] or r.get("username") == user["username"]]
    if action_filter != "전체":
        rows = [r for r in rows if r["action"] == action_filter]
    if keyword.strip():
        k = keyword.strip().lower()
        rows = [r for r in rows if k in (r.get("summary") or "").lower() or k in (r.get("entity_type") or "").lower()]

    display = [{
        "일시":r["created_at"],
        "사용자":f'{r["display_name"]} (@{r["username"]})',
        "동작":r["action"],
        "구분":r["entity_type"],
        "대상ID":r["entity_id"],
        "내용":r["summary"],
    } for r in rows]
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True, height=650)
