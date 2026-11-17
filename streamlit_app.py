import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from __future__ import annotations
import json
import calendar
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st

from db import init_db, fetch_all, fetch_one, execute
from services import (
    CHECK_RULES, criteria_text, judge_value, inspection_overall,
    create_defect_from_inspection, delivery_urgency, monthly_demand_map,
    due_tasks, extract_text_tesseract, best_effort_autofill
)
from ui import inject_css, title, metric

st.set_page_config(
    page_title="QA Workbench",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()
inject_css()

# Session defaults
if "ocr_values" not in st.session_state:
    st.session_state.ocr_values = {r["key"]:"" for r in CHECK_RULES}
if "ocr_text" not in st.session_state:
    st.session_state.ocr_text = ""

# Sidebar
st.sidebar.markdown("## 🛡️ QA Workbench")
st.sidebar.caption("품질보증 업무 통합 관리")
page = st.sidebar.radio(
    "메뉴",
    ["대시보드","검사관리","불량관리","일정 · 할일","납품일정","ERP / BOM"],
)
st.sidebar.divider()
user = fetch_one("SELECT value FROM settings WHERE key='user_name'")
name = st.sidebar.text_input("사용자", value=(user or {}).get("value","사용자"))
if st.sidebar.button("사용자 저장", use_container_width=True):
    execute("INSERT OR REPLACE INTO settings(key,value) VALUES('user_name',?)",(name,))
    st.sidebar.success("저장했습니다.")

# Due task reminders (web page must be open/refreshed)
for task in due_tasks()[:3]:
    st.toast(
        f'⏰ {task["title"]} · {task["due_date"]} {task["due_time"]}',
        icon="⏰",
    )
    execute("UPDATE tasks SET alarm_notified=1 WHERE id=?", (task["id"],))

def df(rows, cols=None):
    if not rows:
        return pd.DataFrame(columns=cols or [])
    return pd.DataFrame(rows)

def row_style_delivery(row):
    _, c = delivery_urgency(str(row.get("납품일","")))
    return [f"background-color: {c}"] * len(row)

# ---------------- Dashboard ----------------
if page == "대시보드":
    title("QA Workbench", f"{name}님의 품질보증 업무 현황")

    inspections = fetch_all("SELECT * FROM inspections")
    total = len(inspections)
    ok = sum(1 for x in inspections if x["result"] == "합격")
    ng = sum(1 for x in inspections if x["result"] != "합격")
    open_defects = fetch_one("SELECT COUNT(*) AS c FROM defects WHERE status != '완료'")["c"]

    c1,c2,c3,c4 = st.columns(4)
    with c1: metric("총 검사", f"{total}건", "누적 검사 건수")
    with c2: metric("양품", f"{ok}건", "합격 판정")
    with c3: metric("불량", f"{ng}건", "불합격 판정")
    with c4: metric("미종결", f"{open_defects}건", "조치 진행 중")

    left, right = st.columns([3.2, 1.25], gap="large")

    with left:
        st.subheader("업무 달력")
        today = date.today()
        year = st.selectbox("연도", range(today.year-1, today.year+3), index=1, key="dash_y")
        month = st.selectbox("월", range(1,13), index=today.month-1, key="dash_m")
        tasks = fetch_all("SELECT * FROM tasks")
        deliveries = fetch_all("SELECT * FROM deliveries")

        events = {}
        for t in tasks:
            if t["due_date"].startswith(f"{year:04d}-{month:02d}"):
                events.setdefault(t["due_date"], []).append(
                    f'⏰ {t["due_time"] or ""} [{t["category"]}] {t["title"]}'
                )
        for d in deliveries:
            if d["due_date"].startswith(f"{year:04d}-{month:02d}"):
                events.setdefault(d["due_date"], []).append(
                    f'📦 [{d["item_code"]}] {d["item_name"]} · {d["process"]}'
                )

        cal = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.markdown("&nbsp;", unsafe_allow_html=True)
                    else:
                        ds = f"{year:04d}-{month:02d}-{day:02d}"
                        body = "<br>".join(events.get(ds, [])[:3])
                        st.markdown(
                            f"""<div class="card" style="min-height:115px">
                            <b>{day}</b><br><span style="font-size:12px">{body}</span>
                            </div>""",
                            unsafe_allow_html=True,
                        )

    with right:
        st.subheader("최근 불량 / 조치 현황")
        defects = fetch_all("""
            SELECT defect_date,item_code,item_name,issue,status
            FROM defects ORDER BY id DESC LIMIT 6
        """)
        st.dataframe(df(defects), use_container_width=True, hide_index=True)

        st.subheader("다가오는 일정 · 할일")
        upcoming = fetch_all("""
            SELECT due_date,due_time,category,title,status
            FROM tasks
            WHERE status != '완료'
            ORDER BY due_date,due_time LIMIT 7
        """)
        st.dataframe(df(upcoming), use_container_width=True, hide_index=True)

# ---------------- Inspection ----------------
elif page == "검사관리":
    title("검사관리", "스캔 체크시트의 측정값을 확인하고 자동 합·불 판정")

    tab1, tab2 = st.tabs(["검사 이력","검사 등록"])

    with tab1:
        rows = fetch_all("""
            SELECT inspection_date,inspection_type,item_code,item_name,supplier,lot,
                   qty,sample_qty,result,note,id
            FROM inspections ORDER BY id DESC
        """)
        data = df(rows)
        if not data.empty:
            data = data.rename(columns={
                "inspection_date":"검사일","inspection_type":"검사구분",
                "item_code":"품번","item_name":"품명","supplier":"업체","lot":"LOT",
                "qty":"입고/생산수량","sample_qty":"검사수량","result":"판정",
                "note":"특이사항","id":"ID"
            })
            def color_result(r):
                c = "#EAF8EE" if r["판정"]=="합격" else "#FDEBEC"
                return [f"background-color:{c}"]*len(r)
            st.dataframe(data.style.apply(color_result, axis=1), use_container_width=True, hide_index=True)

            inspect_id = st.selectbox("상세 검사 선택", [None] + data["ID"].tolist())
            if inspect_id:
                rec = fetch_one("SELECT * FROM inspections WHERE id=?", (inspect_id,))
                details = json.loads(rec.get("details_json") or "[]")
                st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True)

    with tab2:
        a,b,c = st.columns(3)
        inspection_date = a.date_input("검사일", value=date.today())
        inspection_type = b.selectbox("검사구분", ["입고검사","공정검사","출하검사","수입검사","기타"])
        item_code = c.text_input("품번")

        a,b,c = st.columns(3)
        item_name = a.text_input("품명")
        supplier = b.text_input("업체")
        lot = c.text_input("LOT")

        a,b = st.columns(2)
        qty = a.number_input("입고/생산수량", min_value=0.0, step=1.0)
        sample_qty = b.number_input("검사수량", min_value=0.0, step=1.0)

        uploaded = st.file_uploader("체크시트 스캔 이미지", type=["png","jpg","jpeg"])
        if uploaded is not None:
            st.image(uploaded, caption="업로드한 체크시트", width=420)
            if st.button("OCR 자동 인식", type="primary"):
                text = extract_text_tesseract(uploaded)
                st.session_state.ocr_text = text
                auto = best_effort_autofill(text)
                st.session_state.ocr_values.update(auto)
                if text:
                    st.success("OCR을 실행했습니다. 아래 값은 반드시 확인 후 수정해 주세요.")
                else:
                    st.warning("온라인 OCR이 값을 읽지 못했습니다. 아래 측정값을 직접 입력해 주세요.")

        st.markdown("#### 인식 결과 확인 / 수정")
        details = []
        for rule in CHECK_RULES:
            cols = st.columns([2.2,2,2,1.2])
            cols[0].write(rule["label"])
            cols[1].write(criteria_text(rule))
            key = f'ocr_{rule["key"]}'
            default = st.session_state.ocr_values.get(rule["key"], "")
            val = cols[2].text_input(
                "측정값",
                value=str(default),
                key=key,
                label_visibility="collapsed",
            )
            st.session_state.ocr_values[rule["key"]] = val
            verdict = judge_value(rule, val)
            cols[3].write(verdict)
            details.append({
                "검사항목":rule["label"],
                "기준":criteria_text(rule),
                "측정값":val,
                "판정":verdict,
                "label":rule["label"],
                "criteria":criteria_text(rule),
                "value":val,
                "verdict":verdict,
            })

        overall = inspection_overall(details)
        st.info(f"최종 판정: **{overall}**")

        note = st.text_input("특이사항")
        if st.button("검사 기록 저장", type="primary", use_container_width=True):
            iid = execute("""
                INSERT INTO inspections(
                    inspection_date,inspection_type,item_code,item_name,supplier,lot,
                    qty,sample_qty,result,note,details_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                str(inspection_date),inspection_type,item_code,item_name,supplier,lot,
                qty,sample_qty,overall,note,json.dumps(details,ensure_ascii=False)
            ))
            if overall == "불합격":
                create_defect_from_inspection(iid,item_code,item_name,sample_qty,details)
                st.warning("불합격 검사로 저장되어 불량관리에도 자동 등록했습니다.")
            else:
                st.success("검사 기록을 저장했습니다.")

# ---------------- Defect ----------------
elif page == "불량관리":
    title("불량관리", "검사 NG 자동연계 및 조치 이력 추적")
    rows = fetch_all("SELECT * FROM defects ORDER BY id DESC")
    data = df(rows)
    if not data.empty:
        show = data.rename(columns={
            "defect_date":"발생일","source":"등록구분","item_code":"품번",
            "item_name":"품명","issue":"불량현상","qty":"수량","status":"상태",
            "owner":"담당/부서","due_date":"조치기한","action":"조치내용",
            "source_inspection_id":"원본검사ID","id":"ID"
        })
        st.dataframe(show, use_container_width=True, hide_index=True)

    with st.expander("불량 수동 등록", expanded=False):
        a,b,c = st.columns(3)
        ddate = a.date_input("발생일", value=date.today())
        code = b.text_input("품번", key="def_code")
        name2 = c.text_input("품명", key="def_name")
        issue = st.text_input("불량현상")
        qty2 = st.number_input("수량", min_value=0.0, step=1.0, key="def_qty")
        if st.button("불량 등록"):
            execute("""
                INSERT INTO defects(defect_date,source,item_code,item_name,issue,qty,status)
                VALUES(?,?,?,?,?,?,?)
            """,(str(ddate),"수동등록",code,name2,issue,qty2,"접수"))
            st.success("등록했습니다.")
            st.rerun()

    if rows:
        selected = st.selectbox("조치할 불량 선택", [r["id"] for r in rows])
        rec = fetch_one("SELECT * FROM defects WHERE id=?", (selected,))
        a,b,c = st.columns(3)
        status = a.selectbox("상태", ["접수","원인분석","조치중","확인대기","완료"],
                             index=["접수","원인분석","조치중","확인대기","완료"].index(rec["status"]) if rec["status"] in ["접수","원인분석","조치중","확인대기","완료"] else 0)
        owner = b.text_input("담당/부서", value=rec["owner"] or "")
        due = c.text_input("조치기한", value=rec["due_date"] or "")
        action = st.text_area("조치내용", value=rec["action"] or "")
        if st.button("조치사항 저장", type="primary"):
            execute("UPDATE defects SET status=?,owner=?,due_date=?,action=? WHERE id=?",
                    (status,owner,due,action,selected))
            st.success("저장했습니다.")

        if rec.get("source_inspection_id"):
            insp = fetch_one("SELECT * FROM inspections WHERE id=?", (rec["source_inspection_id"],))
            if insp:
                with st.expander("원본 검사 이력 보기"):
                    st.write(f'검사일: {insp["inspection_date"]} / 판정: {insp["result"]}')
                    st.dataframe(pd.DataFrame(json.loads(insp["details_json"] or "[]")), use_container_width=True, hide_index=True)

# ---------------- Tasks ----------------
elif page == "일정 · 할일":
    title("일정 · 할일", "날짜·시간별 업무 등록 및 웹 알림")
    rows = fetch_all("SELECT * FROM tasks ORDER BY due_date,due_time")
    if rows:
        st.dataframe(df(rows), use_container_width=True, hide_index=True)

    with st.form("task_form", clear_on_submit=True):
        a,b,c = st.columns(3)
        d = a.date_input("날짜", value=date.today())
        tm = b.time_input("시간", value=datetime.now().replace(second=0,microsecond=0).time())
        cat = c.selectbox("구분", ["검사","불량조치","회신대기","문서","교정","납품","회의","기타"])
        task_title = st.text_input("업무내용")
        note = st.text_input("메모")
        alarm = st.checkbox("설정 시간이 되면 알림", value=True)
        submit = st.form_submit_button("할일 등록", type="primary")
        if submit and task_title:
            execute("""
                INSERT INTO tasks(due_date,due_time,category,title,status,note,alarm_enabled,alarm_notified)
                VALUES(?,?,?,?,?,?,?,0)
            """,(str(d),tm.strftime("%H:%M"),cat,task_title,"진행",note,1 if alarm else 0))
            st.success("등록했습니다.")
            st.rerun()

    if rows:
        tid = st.selectbox("완료 처리할 할일", [r["id"] for r in rows])
        if st.button("완료 처리"):
            execute("UPDATE tasks SET status='완료' WHERE id=?", (tid,))
            st.rerun()

    st.caption("※ 웹 알림은 페이지가 열려 있거나 새로고침될 때 확인됩니다. 브라우저가 닫힌 상태에서 푸시 알림을 보내려면 별도 알림 서비스가 필요합니다.")

# ---------------- Delivery ----------------
elif page == "납품일정":
    title("납품일정", "제품별 납기·공정 진행 상태 통합 관리")
    rows = fetch_all("SELECT * FROM deliveries ORDER BY due_date")
    if rows:
        data = pd.DataFrame(rows).rename(columns={
            "due_date":"납품일","previous_due":"이전납기","customer":"고객사",
            "project":"프로젝트","item_code":"품번","item_name":"품명",
            "qty":"수량","process":"현재공정","progress":"진행률","status":"상태","note":"비고","id":"ID"
        })
        st.dataframe(data.style.apply(row_style_delivery, axis=1), use_container_width=True, hide_index=True)

    with st.expander("납품일정 등록", expanded=False):
        with st.form("delivery_form", clear_on_submit=True):
            a,b,c = st.columns(3)
            due = a.date_input("납품일", value=date.today()+timedelta(days=30))
            customer = b.text_input("고객사")
            project = c.text_input("프로젝트")
            a,b,c = st.columns(3)
            code = a.text_input("품번")
            item = b.text_input("품명")
            qty = c.number_input("수량", min_value=0.0, step=1.0)
            process = st.selectbox("초기공정", ["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"])
            if st.form_submit_button("등록", type="primary"):
                execute("""
                    INSERT INTO deliveries(due_date,customer,project,item_code,item_name,qty,process,progress,status)
                    VALUES(?,?,?,?,?,?,?,?,?)
                """,(str(due),customer,project,code,item,qty,process,0,"진행중"))
                st.success("등록했습니다.")
                st.rerun()

    if rows:
        did = st.selectbox("변경할 일정", [r["id"] for r in rows])
        rec = fetch_one("SELECT * FROM deliveries WHERE id=?", (did,))
        a,b,c = st.columns(3)
        new_due = a.date_input("변경 납기", value=datetime.strptime(rec["due_date"],"%Y-%m-%d").date(), key="chg_due")
        new_process = b.selectbox("현재공정", ["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"],
                                  index=0 if rec["process"] not in ["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"] else ["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"].index(rec["process"]))
        prog = c.slider("진행률",0,100,int(rec["progress"] or 0))
        if st.button("변경 저장"):
            prev = rec["previous_due"] or rec["due_date"]
            execute("UPDATE deliveries SET previous_due=?,due_date=?,process=?,progress=?,status=? WHERE id=?",
                    (prev,str(new_due),new_process,prog,"완료" if new_process=="납품완료" else "진행중",did))
            st.success("변경했습니다.")
            st.rerun()

# ---------------- ERP ----------------
elif page == "ERP / BOM":
    title("ERP / BOM 관리", "품목·재고 → BOM → 생산계획별 자재소요량을 한 번에 관리")

    tabs = st.tabs(["품목 / 재고 관리","BOM 관리","생산계획 / 자재소요"])

    with tabs[0]:
        items = fetch_all("SELECT * FROM erp_items ORDER BY code")
        demand = monthly_demand_map()
        display = []
        for x in items:
            stock = float(x["stock"] or 0)
            safety = float(x["safety_stock"] or 0)
            need = float(demand.get(x["code"],0))
            bal = stock - (need+safety)
            display.append({
                "품목코드":x["code"],"품목명":x["name"],"구분":x["item_type"],
                "단위":x["unit"],"현재고":stock,"안전재고":safety,
                "30일 예상소요":need,
                "30일 재고상태":f'여유 {bal:g}{x["unit"]}' if bal >= 0 else f'부족 {abs(bal):g}{x["unit"]}'
            })
        dat = pd.DataFrame(display)
        if not dat.empty:
            def color_stock(r):
                c = "#EAF8EE" if str(r["30일 재고상태"]).startswith("여유") else "#FDEBEC"
                return [f"background-color:{c}"]*len(r)
            st.dataframe(dat.style.apply(color_stock,axis=1), use_container_width=True, hide_index=True)

        with st.form("item_form", clear_on_submit=True):
            a,b,c = st.columns(3)
            code = a.text_input("품목코드")
            nm = b.text_input("품목명")
            typ = c.selectbox("구분", ["원자재","부자재","반제품","완제품","기타"])
            a,b,c = st.columns(3)
            unit = a.text_input("단위", value="EA")
            stock = b.number_input("현재고",min_value=0.0)
            safety = c.number_input("안전재고",min_value=0.0)
            if st.form_submit_button("품목 저장") and code and nm:
                execute("""
                    INSERT OR REPLACE INTO erp_items(code,name,item_type,unit,stock,safety_stock)
                    VALUES(?,?,?,?,?,?)
                """,(code,nm,typ,unit,stock,safety))
                st.rerun()

    with tabs[1]:
        bom = fetch_all("""
            SELECT b.id,b.product_code,p.name AS product_name,
                   b.material_code,m.name AS material_name,b.qty
            FROM bom b
            LEFT JOIN erp_items p ON p.code=b.product_code
            LEFT JOIN erp_items m ON m.code=b.material_code
            ORDER BY b.product_code,b.material_code
        """)
        st.dataframe(df(bom), use_container_width=True, hide_index=True)

        items = fetch_all("SELECT code,name FROM erp_items ORDER BY code")
        codes = [x["code"] for x in items]
        with st.form("bom_form", clear_on_submit=True):
            a,b,c = st.columns(3)
            product = a.selectbox("제품", codes)
            material = b.selectbox("자재", codes)
            per = c.number_input("제품 1개당 소요량",min_value=0.0,step=1.0)
            if st.form_submit_button("BOM 추가") and product and material and per>0:
                execute("INSERT INTO bom(product_code,material_code,qty) VALUES(?,?,?)",
                        (product,material,per))
                st.rerun()

    with tabs[2]:
        plans = fetch_all("SELECT * FROM production_plans ORDER BY due_date")
        st.dataframe(df(plans), use_container_width=True, hide_index=True)
        items = fetch_all("SELECT code,name FROM erp_items ORDER BY code")
        codes = [x["code"] for x in items]
        with st.form("plan_form", clear_on_submit=True):
            a,b,c = st.columns(3)
            product = a.selectbox("생산제품", codes)
            qty = b.number_input("생산수량",min_value=0.0,step=1.0)
            due = c.date_input("납기", value=date.today()+timedelta(days=30))
            if st.form_submit_button("생산계획 등록") and product and qty>0:
                execute("""
                    INSERT INTO production_plans(product_code,qty,due_date,status)
                    VALUES(?,?,?,?)
                """,(product,qty,str(due),"계획"))
                st.rerun()

        st.markdown("#### 30일 자재소요 요약")
        dm = monthly_demand_map()
        items_full = {x["code"]:x for x in fetch_all("SELECT * FROM erp_items")}
        req = []
        for code, need in dm.items():
            it = items_full.get(code, {"name":"","stock":0,"safety_stock":0,"unit":"EA"})
            stock = float(it.get("stock",0) or 0)
            safe = float(it.get("safety_stock",0) or 0)
            bal = stock - need - safe
            req.append({
                "품목코드":code,"품목명":it.get("name",""),"30일 필요":need,
                "현재고":stock,"안전재고":safe,
                "예상잔고":stock-need,
                "판정":"여유" if bal>=0 else f"부족 {abs(bal):g}{it.get('unit','EA')}"
            })
        if req:
            st.dataframe(pd.DataFrame(req),use_container_width=True,hide_index=True)
