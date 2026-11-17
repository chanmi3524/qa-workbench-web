
from __future__ import annotations
import streamlit as st

def inject_css():
    st.markdown("""
    <style>
      .stApp {background:#f6f8fb;}
      [data-testid="stSidebar"] {background:#17304f;}
      [data-testid="stSidebar"] * {color:white;}
      .block-container {padding-top:1.2rem; padding-bottom:2rem; max-width:1450px;}
      .qa-title {font-size:30px;font-weight:800;color:#132a44;margin-bottom:2px}
      .qa-sub {color:#718096;margin-bottom:16px}
      .card {background:white;border:1px solid #e3e8ef;border-radius:12px;padding:16px;}
      .metric-card {background:white;border:1px solid #e3e8ef;border-radius:12px;padding:16px 18px;}
      .metric-label {font-size:13px;color:#667085;}
      .metric-value {font-size:30px;font-weight:800;color:#102a43;}
      .ok {background:#EAF8EE;padding:8px;border-radius:8px;}
      .warn {background:#FFF7D6;padding:8px;border-radius:8px;}
      .ng {background:#FDEBEC;padding:8px;border-radius:8px;}
      div[data-testid="stDataFrame"] {background:white;border-radius:10px;}
    </style>
    """, unsafe_allow_html=True)

def title(text, sub=None):
    st.markdown(f'<div class="qa-title">{text}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="qa-sub">{sub}</div>', unsafe_allow_html=True)

def metric(label, value, caption=""):
    st.markdown(
        f"""<div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{caption}</div>
        </div>""",
        unsafe_allow_html=True,
    )
