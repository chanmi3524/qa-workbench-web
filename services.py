
from __future__ import annotations
from datetime import date, timedelta, datetime
import json
import re
from db import fetch_all, fetch_one, execute

CHECK_RULES = [
    {"key":"current_28v","label":"28V 소비전류","kind":"range","min":0.060,"max":0.070,"unit":"A"},
    {"key":"current_6v5","label":"6.5V 소비전류","kind":"range","min":0.330,"max":0.360,"unit":"A"},
    {"key":"ratio","label":"28V / 6.5V","kind":"range","min":3.82,"max":4.30,"unit":""},
    {"key":"polarity","label":"전원 위치 확인","kind":"text_ok","unit":""},
    {"key":"tp2","label":"TP2 28V","kind":"range","min":26.6,"max":29.4,"unit":"V"},
    {"key":"tp3","label":"TP3 5V","kind":"range","min":4.75,"max":5.25,"unit":"V"},
    {"key":"tp10","label":"TP10 5V","kind":"range","min":4.75,"max":5.25,"unit":"V"},
    {"key":"tp8","label":"TP8 3.3V","kind":"range","min":3.135,"max":3.465,"unit":"V"},
    {"key":"tp7","label":"TP7 1.97V","kind":"range","min":1.872,"max":2.068,"unit":"V"},
    {"key":"set_28v","label":"28V 1A 설정","kind":"text_ok","unit":""},
    {"key":"tp27","label":"R196 / TP27","kind":"range","min":1.310,"max":1.313,"unit":"V"},
    {"key":"tp28","label":"R197 / TP28","kind":"range","min":1.630,"max":1.633,"unit":"V"},
    {"key":"tp29","label":"R198 / TP29","kind":"range","min":1.852,"max":1.854,"unit":"V"},
]

def criteria_text(rule):
    if rule["kind"] == "range":
        return f'{rule["min"]} ~ {rule["max"]} {rule.get("unit","")}'.strip()
    return "양호"

def judge_value(rule, raw):
    s = str(raw or "").strip()
    if not s:
        return "미입력"
    if rule["kind"] == "text_ok":
        compact = s.lower().replace(" ","")
        return "합격" if ("양호" in s or "ok" in compact or "정상" in s) else "확인필요"
    try:
        v = float(s)
    except Exception:
        return "확인필요"
    return "합격" if rule["min"] <= v <= rule["max"] else "불합격"

def inspection_overall(details):
    verdicts = [d["verdict"] for d in details]
    return "불합격" if "불합격" in verdicts or "확인필요" in verdicts else "합격"

def create_defect_from_inspection(inspection_id, item_code, item_name, qty, details):
    ng = [d for d in details if d.get("verdict") in ("불합격","확인필요")]
    if not ng:
        return None
    existing = fetch_one(
        "SELECT id FROM defects WHERE source='검사자동연계' AND source_inspection_id=?",
        (inspection_id,)
    )
    if existing:
        return existing["id"]

    labels = [d["label"] for d in ng]
    issue = "자동검사 NG: " + ", ".join(labels[:5])
    action = " | ".join(
        f'{d["label"]} 측정 {d["value"]} / 기준 {d["criteria"]} / {d["verdict"]}'
        for d in ng
    )
    return execute("""
        INSERT INTO defects(
            defect_date,source,item_code,item_name,issue,qty,status,action,source_inspection_id
        ) VALUES(?,?,?,?,?,?,?,?,?)
    """, (
        date.today().isoformat(),"검사자동연계",item_code,item_name,issue,qty,
        "접수",action,inspection_id
    ))

def delivery_urgency(due_date):
    try:
        due = datetime.strptime(due_date, "%Y-%m-%d").date()
    except Exception:
        return ("기타", "#EEF2F6")
    days = (due - date.today()).days
    if days < 15:
        return (f"{days}일", "#FDEBEC")
    if days <= 30:
        return (f"{days}일", "#FFF7D6")
    return (f"{days}일", "#EAF8EE")

def monthly_demand_map():
    today = date.today()
    end = today + timedelta(days=30)
    demand = {}
    plans = fetch_all("""
        SELECT * FROM production_plans
        WHERE status != '생산완료'
    """)
    bom = fetch_all("SELECT * FROM bom")
    for p in plans:
        try:
            due = datetime.strptime(p["due_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if not (today <= due <= end):
            continue
        qty = float(p["qty"] or 0)
        product = p["product_code"]
        demand[product] = demand.get(product, 0) + qty
        for b in bom:
            if b["product_code"] == product:
                code = b["material_code"]
                demand[code] = demand.get(code, 0) + qty * float(b["qty"] or 0)
    return demand

def due_tasks():
    now = datetime.now()
    rows = fetch_all("SELECT * FROM tasks WHERE status != '완료' AND alarm_enabled=1")
    due = []
    for r in rows:
        if not r.get("due_time"):
            continue
        try:
            dt = datetime.strptime(r["due_date"]+" "+r["due_time"], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if dt <= now and not r.get("alarm_notified"):
            due.append(r)
    return due

def extract_text_tesseract(uploaded_file):
    """Best-effort server OCR. Handwriting recognition may require manual correction."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(uploaded_file).convert("RGB")
        return pytesseract.image_to_string(img, lang="eng+kor")
    except Exception:
        return ""

def numeric_candidates(text):
    text = (text or "").replace(",", ".").replace("O","0").replace("o","0")
    return re.findall(r"[-+]?(?:\d+\.\d+|\d+)", text)

def best_effort_autofill(text):
    """Very conservative OCR autofill: only fill clear sequential numeric candidates."""
    nums = numeric_candidates(text)
    out = {r["key"]:"" for r in CHECK_RULES}
    numeric_rules = [r for r in CHECK_RULES if r["kind"] == "range"]
    for rule, token in zip(numeric_rules, nums):
        out[rule["key"]] = token
    if "양호" in (text or ""):
        for r in CHECK_RULES:
            if r["kind"] == "text_ok":
                out[r["key"]] = "양호"
    return out
