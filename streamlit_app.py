
from __future__ import annotations
import json, calendar
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
from db import init_db, fetch_all, fetch_one, execute
from services import CHECK_RULES,criteria_text,judge_value,inspection_overall,create_defect_from_inspection,delivery_urgency,monthly_demand_map,due_tasks,extract_text_tesseract,best_effort_autofill
from ui import inject_css,metric,section_title

st.set_page_config(page_title="QA Workbench",page_icon="🛡️",layout="wide",initial_sidebar_state="collapsed")
init_db(); inject_css()

if "authenticated" not in st.session_state: st.session_state.authenticated=False
if "page" not in st.session_state: st.session_state.page="대시보드"
if "settings_mode" not in st.session_state: st.session_state.settings_mode=False
if "ocr_values" not in st.session_state: st.session_state.ocr_values={r["key"]:"" for r in CHECK_RULES}

def get_setting(k,d=""):
    r=fetch_one("SELECT value FROM settings WHERE key=?",(k,))
    return r["value"] if r else d
def save_setting(k,v): execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(k,v))

def login_screen():
    st.markdown("""
    <div class="login-bg"><div class="login-shell">
      <div class="login-left"><b>QA WORKBENCH</b><h1>품질보증<br>업무 통합 관리</h1><div>검사 · 불량 · 일정 · 납품 · ERP/BOM</div></div>
      <div class="login-right"><span class="login-badge">QA WORKBENCH</span><div class="login-title">품질보증 업무관리</div><div class="login-sub">비밀번호를 입력하면 바로 시작할 수 있어요.</div></div>
    </div></div>""",unsafe_allow_html=True)
    a,b,c=st.columns([1.85,1,1.85])
    with b:
        if st.session_state.settings_mode:
            nm=st.text_input("이름",value=get_setting("user_name","사용자"))
            p1=st.text_input("새 비밀번호",type="password")
            p2=st.text_input("비밀번호 확인",type="password")
            if st.button("설정 저장",type="primary",use_container_width=True):
                if p1 and p1!=p2: st.error("비밀번호가 서로 다릅니다.")
                else:
                    save_setting("user_name",nm.strip() or "사용자")
                    if p1: save_setting("app_password",p1)
                    st.session_state.settings_mode=False; st.rerun()
            if st.button("로그인으로 돌아가기",use_container_width=True):
                st.session_state.settings_mode=False; st.rerun()
        else:
            pw=st.text_input("비밀번호",type="password")
            if st.button("시작하기",type="primary",use_container_width=True):
                if pw==get_setting("app_password","0000"):
                    st.session_state.authenticated=True; st.rerun()
                else: st.error("비밀번호가 맞지 않습니다.")
            if st.button("사용자 설정",use_container_width=True):
                st.session_state.settings_mode=True; st.rerun()
            st.caption("초기 비밀번호: 0000")

if not st.session_state.authenticated:
    login_screen(); st.stop()

name=get_setting("user_name","사용자")
st.markdown(f"""<div class="qa-topbar"><div class="qa-brand">QA Workbench</div><div class="qa-search">⌕　품번, 품명, 불량내용 등을 검색...</div><div class="qa-muted">{name} · 품질보증 QA</div></div>""",unsafe_allow_html=True)
left,main=st.columns([.145,.855],gap="medium")
with left:
    st.markdown("""<div class="qa-side-card"><div class="qa-side-logo"><div class="qa-logo-box">Q</div><div class="qa-side-title">QA<br>Workbench</div></div></div>""",unsafe_allow_html=True)
    st.markdown('<div class="nav-wrap">',unsafe_allow_html=True)
    for label,target in [("⌂ 대시보드","대시보드"),("▣ 검사관리","검사관리"),("△ 불량관리","불량관리"),("▦ 일정 · 할일","일정 · 할일"),("■ 납품일정","납품일정"),("◇ ERP / BOM","ERP / BOM")]:
        if st.button(label,key=f"nav_{target}",use_container_width=True):
            st.session_state.page=target; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="qa-user">{name}<br>품질보증 · QA</div>',unsafe_allow_html=True)
    if st.button("⚙ 사용자 설정",use_container_width=True):
        st.session_state.page="사용자 설정"; st.rerun()
    if st.button("↪ 로그아웃",use_container_width=True):
        st.session_state.authenticated=False; st.rerun()

with main:
    page=st.session_state.page
    for t in due_tasks()[:3]:
        st.toast(f'⏰ {t["title"]} · {t["due_date"]} {t["due_time"]}')
        execute("UPDATE tasks SET alarm_notified=1 WHERE id=?",(t["id"],))

    if page=="사용자 설정":
        section_title("사용자 설정","이름과 앱 비밀번호를 변경합니다.")
        nm=st.text_input("이름",value=get_setting("user_name","사용자"))
        old=st.text_input("현재 비밀번호",type="password")
        p1=st.text_input("새 비밀번호",type="password")
        p2=st.text_input("새 비밀번호 확인",type="password")
        if st.button("설정 저장",type="primary"):
            if old!=get_setting("app_password","0000"): st.error("현재 비밀번호가 맞지 않습니다.")
            elif p1 and p1!=p2: st.error("새 비밀번호가 서로 다릅니다.")
            else:
                save_setting("user_name",nm.strip() or "사용자")
                if p1: save_setting("app_password",p1)
                st.success("저장했습니다.")
        st.stop()

    elif page=="대시보드":
        section_title("품질 대시보드")
        ins=fetch_all("SELECT * FROM inspections")
        total=len(ins); ok=sum(x["result"]=="합격" for x in ins); ng=total-ok
        open_def=(fetch_one("SELECT COUNT(*) c FROM defects WHERE status!='완료'") or {"c":0})["c"]
        c1,c2,c3,c4=st.columns(4)
        with c1: metric("총 검사",f"{total}건","이번 달 검사 건수")
        with c2: metric("양품",f"{ok}건","합격 판정")
        with c3: metric("불량",f"{ng}건","불합격 판정")
        with c4: metric("미종결",f"{open_def}건","조치 진행 중")
        l,r=st.columns([3.1,1.3],gap="medium")
        with l:
            st.markdown("### 업무 달력")
            td=date.today()
            y=st.selectbox("연도",range(td.year-1,td.year+3),index=1,key="dy")
            m=st.selectbox("월",range(1,13),index=td.month-1,key="dm")
            events={}
            for t in fetch_all("SELECT * FROM tasks"):
                if t["due_date"].startswith(f"{y:04d}-{m:02d}"):
                    events.setdefault(t["due_date"],[]).append(f'⏰ {t["due_time"] or ""} [{t["category"]}] {t["title"]}')
            for d in fetch_all("SELECT * FROM deliveries"):
                if d["due_date"].startswith(f"{y:04d}-{m:02d}"):
                    events.setdefault(d["due_date"],[]).append(f'📦 [{d["item_code"]}] {d["item_name"]} · {d["process"]}')
            for week in calendar.Calendar().monthdayscalendar(y,m):
                cols=st.columns(7)
                for i,day in enumerate(week):
                    with cols[i]:
                        if day==0: st.markdown("&nbsp;",unsafe_allow_html=True)
                        else:
                            ds=f"{y:04d}-{m:02d}-{day:02d}"
                            body="<br>".join(events.get(ds,[])[:3])
                            st.markdown(f'<div class="calendar-cell"><div class="calendar-day">{day}</div>{body}</div>',unsafe_allow_html=True)
        with r:
            st.markdown("### 최근 불량 / 조치 현황")
            st.dataframe(pd.DataFrame(fetch_all("SELECT defect_date,item_code,item_name,issue,status FROM defects ORDER BY id DESC LIMIT 6")),use_container_width=True,hide_index=True)
            st.markdown("### 다가오는 일정 · 할일")
            st.dataframe(pd.DataFrame(fetch_all("SELECT due_date,due_time,category,title,status FROM tasks WHERE status!='완료' ORDER BY due_date,due_time LIMIT 7")),use_container_width=True,hide_index=True)

    elif page=="검사관리":
        section_title("검사관리","스캔 체크시트의 측정값을 확인하고 자동 합·불 판정")
        tab1,tab2=st.tabs(["검사 이력","검사 등록"])
        with tab1:
            rows=fetch_all("SELECT id,inspection_date,inspection_type,item_code,item_name,supplier,lot,qty,sample_qty,result,note FROM inspections ORDER BY id DESC")
            if rows:
                df=pd.DataFrame(rows)
                def sty(r):
                    c="#eaf8ee" if r["result"]=="합격" else "#fdebec"
                    return [f"background-color:{c}"]*len(r)
                st.dataframe(df.style.apply(sty,axis=1),use_container_width=True,hide_index=True)
        with tab2:
            a,b,c=st.columns(3)
            d=a.date_input("검사일",date.today()); typ=b.selectbox("검사구분",["입고검사","공정검사","출하검사","기타"]); code=c.text_input("품번")
            a,b,c=st.columns(3)
            item=a.text_input("품명"); supplier=b.text_input("업체"); lot=c.text_input("LOT")
            a,b=st.columns(2); qty=a.number_input("입고/생산수량",0.0); sample=b.number_input("검사수량",0.0)
            up=st.file_uploader("체크시트 이미지",type=["png","jpg","jpeg"])
            if up is not None:
                st.image(up,width=380)
                if st.button("OCR 자동 인식",type="primary"):
                    txt=extract_text_tesseract(up)
                    st.session_state.ocr_values.update(best_effort_autofill(txt))
                    st.success("OCR 결과를 아래에서 확인/수정해 주세요." if txt else "OCR이 읽지 못했습니다. 값을 직접 입력해 주세요.")
            details=[]
            st.markdown("#### 인식 결과 확인 / 수정")
            for rule in CHECK_RULES:
                c1,c2,c3,c4=st.columns([2,2,2,1])
                c1.write(rule["label"]); c2.write(criteria_text(rule))
                val=c3.text_input("측정값",value=st.session_state.ocr_values.get(rule["key"],""),key=f'ocr_{rule["key"]}',label_visibility="collapsed")
                st.session_state.ocr_values[rule["key"]]=val
                verdict=judge_value(rule,val); c4.write(verdict)
                details.append({"label":rule["label"],"criteria":criteria_text(rule),"value":val,"verdict":verdict})
            overall=inspection_overall(details); st.info(f"최종 판정: **{overall}**")
            note=st.text_input("특이사항")
            if st.button("검사 기록 저장",type="primary",use_container_width=True):
                iid=execute("""INSERT INTO inspections(inspection_date,inspection_type,item_code,item_name,supplier,lot,qty,sample_qty,result,note,details_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(str(d),typ,code,item,supplier,lot,qty,sample,overall,note,json.dumps(details,ensure_ascii=False)))
                if overall=="불합격":
                    create_defect_from_inspection(iid,code,item,sample,details); st.warning("불량관리에도 자동 등록했습니다.")
                else: st.success("저장했습니다.")

    elif page=="불량관리":
        section_title("불량관리","검사 NG 자동연계 및 조치 이력 추적")
        rows=fetch_all("SELECT * FROM defects ORDER BY id DESC")
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        with st.expander("불량 수동 등록"):
            d=st.date_input("발생일",date.today()); code=st.text_input("품번",key="dc"); item=st.text_input("품명",key="dn"); issue=st.text_input("불량현상"); q=st.number_input("수량",0.0,key="dq")
            if st.button("불량 등록"):
                execute("INSERT INTO defects(defect_date,source,item_code,item_name,issue,qty,status) VALUES(?,?,?,?,?,?,?)",(str(d),"수동등록",code,item,issue,q,"접수")); st.rerun()
        if rows:
            sid=st.selectbox("조치할 불량", [r["id"] for r in rows]); rec=fetch_one("SELECT * FROM defects WHERE id=?",(sid,))
            status=st.selectbox("상태",["접수","원인분석","조치중","확인대기","완료"],index=["접수","원인분석","조치중","확인대기","완료"].index(rec["status"]) if rec["status"] in ["접수","원인분석","조치중","확인대기","완료"] else 0)
            owner=st.text_input("담당/부서",value=rec["owner"] or ""); due=st.text_input("조치기한",value=rec["due_date"] or ""); action=st.text_area("조치내용",value=rec["action"] or "")
            if st.button("조치사항 저장",type="primary"):
                execute("UPDATE defects SET status=?,owner=?,due_date=?,action=? WHERE id=?",(status,owner,due,action,sid)); st.success("저장했습니다.")

    elif page=="일정 · 할일":
        section_title("일정 · 할일","날짜·시간별 업무 등록 및 알림")
        rows=fetch_all("SELECT * FROM tasks ORDER BY due_date,due_time")
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        with st.form("tf",clear_on_submit=True):
            a,b,c=st.columns(3)
            d=a.date_input("날짜",date.today()); tm=b.time_input("시간",datetime.now().replace(second=0,microsecond=0).time()); cat=c.selectbox("구분",["검사","불량조치","회신대기","문서","교정","납품","회의","기타"])
            title=st.text_input("업무내용"); note=st.text_input("메모"); alarm=st.checkbox("설정 시간이 되면 알림",True)
            if st.form_submit_button("할일 등록",type="primary") and title:
                execute("INSERT INTO tasks(due_date,due_time,category,title,status,note,alarm_enabled,alarm_notified) VALUES(?,?,?,?,?,?,?,0)",(str(d),tm.strftime("%H:%M"),cat,title,"진행",note,1 if alarm else 0)); st.rerun()

    elif page=="납품일정":
        section_title("납품일정","제품별 납기·공정 진행 상태 통합 관리")
        rows=fetch_all("SELECT * FROM deliveries ORDER BY due_date")
        if rows:
            df=pd.DataFrame(rows)
            def sty(r):
                _,c=delivery_urgency(str(r["due_date"]))
                return [f"background-color:{c}"]*len(r)
            st.dataframe(df.style.apply(sty,axis=1),use_container_width=True,hide_index=True)
        with st.expander("납품일정 등록"):
            with st.form("df",clear_on_submit=True):
                a,b,c=st.columns(3)
                due=a.date_input("납품일",date.today()+timedelta(days=30)); cust=b.text_input("고객사"); proj=c.text_input("프로젝트")
                a,b,c=st.columns(3)
                code=a.text_input("품번"); item=b.text_input("품명"); qty=c.number_input("수량",0.0)
                process=st.selectbox("초기공정",["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"])
                if st.form_submit_button("등록",type="primary"):
                    execute("INSERT INTO deliveries(due_date,customer,project,item_code,item_name,qty,process,progress,status) VALUES(?,?,?,?,?,?,?,?,?)",(str(due),cust,proj,code,item,qty,process,0,"진행중")); st.rerun()
        if rows:
            did=st.selectbox("변경할 일정",[r["id"] for r in rows]); rec=fetch_one("SELECT * FROM deliveries WHERE id=?",(did,))
            a,b,c=st.columns(3)
            nd=a.date_input("변경 납기",datetime.strptime(rec["due_date"],"%Y-%m-%d").date())
            plist=["자재준비","1차전원검사","외주(코팅)","2차전원검사","ESS시험","출하검사 대기","출하검사","납품 대기","납품완료"]
            pr=b.selectbox("현재공정",plist,index=plist.index(rec["process"]) if rec["process"] in plist else 0); pg=c.slider("진행률",0,100,int(rec["progress"] or 0))
            if st.button("변경 저장"):
                prev=rec["previous_due"] or rec["due_date"]
                execute("UPDATE deliveries SET previous_due=?,due_date=?,process=?,progress=?,status=? WHERE id=?",(prev,str(nd),pr,pg,"완료" if pr=="납품완료" else "진행중",did)); st.rerun()

    elif page=="ERP / BOM":
        section_title("ERP / BOM 관리","품목·재고 → BOM → 생산계획별 자재소요량 관리")
        t1,t2,t3=st.tabs(["품목 / 재고 관리","BOM 관리","생산계획 / 자재소요"])
        with t1:
            items=fetch_all("SELECT * FROM erp_items ORDER BY code"); demand=monthly_demand_map(); disp=[]
            for x in items:
                need=float(demand.get(x["code"],0)); bal=float(x["stock"])-need-float(x["safety_stock"])
                disp.append({"품목코드":x["code"],"품목명":x["name"],"구분":x["item_type"],"단위":x["unit"],"현재고":x["stock"],"안전재고":x["safety_stock"],"30일 예상소요":need,"30일 재고상태":("여유 " if bal>=0 else "부족 ")+str(abs(bal))})
            if disp:
                ddf=pd.DataFrame(disp)
                def s(r): return [f'background-color:{"#eaf8ee" if str(r["30일 재고상태"]).startswith("여유") else "#fdebec"}']*len(r)
                st.dataframe(ddf.style.apply(s,axis=1),use_container_width=True,hide_index=True)
        with t2:
            st.dataframe(pd.DataFrame(fetch_all("SELECT * FROM bom ORDER BY product_code,material_code")),use_container_width=True,hide_index=True)
        with t3:
            st.dataframe(pd.DataFrame(fetch_all("SELECT * FROM production_plans ORDER BY due_date")),use_container_width=True,hide_index=True)
