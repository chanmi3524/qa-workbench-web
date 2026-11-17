
from __future__ import annotations
import streamlit as st

def inject_css():
    st.markdown("""
    <style>
    html,body{background:#eef3f8;}
    .stApp{background:#f3f6fa;min-width:1360px!important;}
    [data-testid="stAppViewContainer"]{min-width:1360px!important;overflow-x:auto!important;}
    .block-container{padding:.6rem .9rem 1.2rem!important;max-width:none!important;min-width:1320px!important;}
    [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;}
    #MainMenu{visibility:hidden;} footer{visibility:hidden;}
    header[data-testid="stHeader"]{height:.2rem;background:transparent;}
    .qa-topbar{background:#fff;border:1px solid #dbe3ec;border-radius:6px;padding:13px 18px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;}
    .qa-brand{font-size:27px;font-weight:800;color:#112a46;}
    .qa-search{color:#78889b;background:#f4f7fb;border:1px solid #e5eaf0;border-radius:4px;padding:9px 16px;width:58%;font-size:13px;}
    .qa-side-card{background:#17304f;border-radius:6px;padding:14px 10px;min-height:850px;}
    .qa-side-logo{display:flex;gap:10px;align-items:center;border-bottom:1px solid rgba(255,255,255,.12);padding-bottom:14px;}
    .qa-logo-box{width:34px;height:34px;background:#2f80ed;color:white;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:20px;}
    .qa-side-title{color:white;font-size:15px;font-weight:800;line-height:1.1}
    .nav-wrap div[data-testid="stButton"]>button{width:100%;justify-content:flex-start;background:#17304f;color:#dbe7f5;border:0;padding:11px 12px;min-height:42px;font-size:14px;}
    .nav-wrap div[data-testid="stButton"]>button:hover{background:#285a93;color:white;}
    .qa-user{margin-top:15px;padding:14px 7px 0;border-top:1px solid rgba(255,255,255,.12);color:#dbe7f5;font-size:12px;}
    .metric-card{background:white;border:1px solid #dbe3ec;border-radius:4px;padding:14px 16px;min-height:102px;}
    .metric-label{font-size:12px;color:#708195}.metric-value{font-size:29px;font-weight:800;color:#102a43;margin:5px 0}.metric-caption{font-size:11px;color:#8797a9}
    .qa-section-title{font-size:18px;font-weight:800;color:#17304f;margin-bottom:8px}.qa-muted{font-size:12px;color:#718096;margin-bottom:10px}
    .login-bg{min-width:1240px;min-height:790px;display:flex;align-items:center;justify-content:center;}
    .login-shell{width:980px;display:grid;grid-template-columns:1.45fr .75fr;background:#fff;border:1px solid #dbe3ec;box-shadow:0 18px 45px rgba(27,53,84,.12);}
    .login-left{min-height:580px;background:linear-gradient(135deg,#17304f 0%,#285a93 58%,#eef5fb 58%);padding:52px;color:white;}
    .login-left h1{margin-top:165px;font-size:42px;line-height:1.12}.login-right{padding:70px 42px}
    .login-badge{display:inline-block;background:#17304f;color:#fff;padding:7px 11px;font-size:11px;font-weight:800;margin-bottom:18px}.login-title{font-size:30px;font-weight:800;color:#17304f}.login-sub{color:#78889b;font-size:13px;margin-top:6px}
    .calendar-cell{background:#fff;border:1px solid #cdd6df;min-height:110px;padding:8px;font-size:12px}.calendar-day{font-weight:800;font-size:15px;margin-bottom:5px}
    @media(max-width:700px){.stApp,[data-testid="stAppViewContainer"]{min-width:1360px!important}.block-container{min-width:1320px!important}}
    </style>
    """, unsafe_allow_html=True)

def metric(label,value,caption=""):
    st.markdown(f"""<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-caption">{caption}</div></div>""",unsafe_allow_html=True)

def section_title(text,sub=None):
    st.markdown(f'<div class="qa-section-title">{text}</div>',unsafe_allow_html=True)
    if sub: st.markdown(f'<div class="qa-muted">{sub}</div>',unsafe_allow_html=True)
