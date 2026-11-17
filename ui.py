
from __future__ import annotations
import streamlit as st

def inject_css():
    st.markdown("""
    <style>
    html, body {
        background: #f3f6fa;
    }

    /* 전체 PC 캔버스 고정 */
    .stApp {
        background: #f3f6fa;
        min-width: 1280px !important;
    }
    [data-testid="stAppViewContainer"] {
        min-width: 1280px !important;
        overflow-x: auto !important;
    }
    .block-container {
        max-width: none !important;
        min-width: 1060px !important;
        padding-top: 0.7rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 1.3rem !important;
    }
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
    }

    /* Streamlit 기본 여백/메뉴 정리 */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] {
        background: transparent;
        height: 0.35rem;
    }

    /* 실제 사이드바 */
    section[data-testid="stSidebar"] {
        width: 185px !important;
        min-width: 185px !important;
        max-width: 185px !important;
        background: #17304f !important;
        border-right: 0 !important;
    }
    section[data-testid="stSidebar"] > div {
        width: 185px !important;
        background: #17304f !important;
        padding-top: 14px !important;
    }
    section[data-testid="stSidebar"] * {
        color: #eaf1f8;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
        width: 100% !important;
        justify-content: flex-start !important;
        background: transparent !important;
        color: #eaf1f8 !important;
        border: 0 !important;
        border-radius: 2px !important;
        min-height: 43px !important;
        padding: 8px 12px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background: #2b5f99 !important;
        color: white !important;
    }

    .sidebar-brand {
        display:flex;
        align-items:center;
        gap:10px;
        padding:4px 4px 17px 4px;
        margin-bottom:10px;
        border-bottom:1px solid rgba(255,255,255,.13);
    }
    .sidebar-logo {
        width:34px; height:34px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:#2f80ed;
        color:white;
        font-size:20px;
        font-weight:800;
    }
    .sidebar-title {
        color:white;
        font-size:14px;
        font-weight:800;
        line-height:1.12;
    }
    .sidebar-user {
        color:#cbd8e7;
        font-size:11px;
        padding:12px 9px 5px 9px;
        margin-top:18px;
        border-top:1px solid rgba(255,255,255,.13);
    }

    /* 상단 */
    .qa-topbar {
        display:flex;
        align-items:center;
        justify-content:space-between;
        background:white;
        border:1px solid #dde5ee;
        min-height:58px;
        padding:0 18px;
        margin-bottom:12px;
    }
    .qa-brand {
        color:#102a43;
        font-size:27px;
        font-weight:800;
        letter-spacing:-0.5px;
    }
    .qa-search {
        width:58%;
        background:#f4f7fb;
        border:1px solid #e5ebf1;
        color:#6f8092;
        padding:9px 14px;
        font-size:12px;
    }
    .qa-user-top {
        color:#718096;
        font-size:12px;
    }

    .section-title {
        color:#17304f;
        font-size:18px;
        font-weight:800;
        margin:5px 0 10px;
    }
    .section-sub {
        color:#718096;
        font-size:12px;
        margin-top:-5px;
        margin-bottom:12px;
    }

    /* 카드 */
    .metric-card {
        background:white;
        border:1px solid #dbe3ec;
        min-height:105px;
        padding:14px 17px;
    }
    .metric-label { font-size:12px; color:#718096; }
    .metric-value { font-size:29px; font-weight:800; color:#102a43; margin:4px 0; }
    .metric-caption { font-size:11px; color:#8a98a8; }

    .calendar-cell {
        background:white;
        border:1px solid #cbd5df;
        min-height:104px;
        padding:7px;
        font-size:11px;
        color:#172b43;
    }
    .calendar-day {
        font-size:15px;
        font-weight:800;
        margin-bottom:5px;
    }

    /* 로그인 */
    .login-heading {
        text-align:center;
        margin-top:7vh;
        margin-bottom:18px;
    }
    .login-logo {
        display:inline-flex;
        width:48px;
        height:48px;
        align-items:center;
        justify-content:center;
        background:#2f80ed;
        color:white;
        font-size:26px;
        font-weight:800;
        margin-bottom:16px;
    }
    .login-title {
        font-size:34px;
        font-weight:800;
        color:#17304f;
        margin-bottom:4px;
    }
    .login-sub {
        color:#718096;
        font-size:13px;
    }
    .login-card {
        background:white;
        border:1px solid #dbe3ec;
        padding:0;
        box-shadow:0 12px 35px rgba(30,55,85,.08);
    }

    /* 모바일에서도 PC 레이아웃 유지 */
    @media (max-width: 700px) {
        .stApp,
        [data-testid="stAppViewContainer"] {
            min-width:1280px !important;
        }
        .block-container {
            min-width:1060px !important;
        }
        section[data-testid="stSidebar"] {
            display:block !important;
            transform:none !important;
            visibility:visible !important;
            width:185px !important;
            min-width:185px !important;
        }
        section[data-testid="stSidebar"] > div {
            width:185px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

def metric(label, value, caption=""):
    st.markdown(
        f"""<div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-caption">{caption}</div>
        </div>""",
        unsafe_allow_html=True
    )

def section_title(text, sub=None):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="section-sub">{sub}</div>', unsafe_allow_html=True)
