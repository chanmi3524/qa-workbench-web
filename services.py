
from __future__ import annotations
from datetime import date, datetime, timedelta
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
        return "합격" if ("양호" in s or "정상" in s or "ok" in s.lower()) else "확인필요"
    try:
        v = float(s)
    except Exception:
        return "확인필요"
    return "합격" if rule["min"] <= v <= rule["max"] else "불합격"

def inspection_overall(details):
    verdicts = [d["verdict"] for d in details]
    return "불합격" if any(v in ("불합격","확인필요") for v in verdicts) else "합격"

def create_defect_from_inspection(inspection_id, item_code, item_name, qty, details, created_by=""):
    ng = [d for d in details if d.get("verdict") in ("불합격","확인필요")]
    if not ng:
        return None
    existing = fetch_one("SELECT id FROM defects WHERE source_inspection_id=?", (inspection_id,))
    if existing:
        return existing["id"]
    issue = "자동검사 NG: " + ", ".join(d["label"] for d in ng[:4])
    action = " | ".join(f'{d["label"]}: {d["value"]} / {d["criteria"]}' for d in ng)
    return execute("""INSERT INTO defects(
        defect_date,source,item_code,item_name,issue,qty,status,action,source_inspection_id,created_by,updated_by
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
    (date.today().isoformat(),"검사자동연계",item_code,item_name,issue,qty,"접수",action,inspection_id,created_by,created_by))

def delivery_urgency(due_date):
    try:
        due = datetime.strptime(due_date,"%Y-%m-%d").date()
        days = (due-date.today()).days
    except Exception:
        return ("기타","#eef2f6")
    if days < 15: return (f"{days}일","#fdebec")
    if days <= 30: return (f"{days}일","#fff7d6")
    return (f"{days}일","#eaf8ee")

def monthly_demand_map():
    today = date.today()
    end = today + timedelta(days=30)
    demand = {}
    plans = fetch_all("SELECT * FROM production_plans WHERE status!='생산완료'")
    bom = fetch_all("SELECT * FROM bom")
    for p in plans:
        try:
            due = datetime.strptime(p["due_date"],"%Y-%m-%d").date()
        except Exception:
            continue
        if not(today <= due <= end):
            continue
        q = float(p["qty"] or 0)
        demand[p["product_code"]] = demand.get(p["product_code"],0)+q
        for b in bom:
            if b["product_code"] == p["product_code"]:
                demand[b["material_code"]] = demand.get(b["material_code"],0) + q*float(b["qty"])
    return demand

def due_tasks(user_id):
    now = datetime.now()
    rows = fetch_all(
        """SELECT * FROM tasks
           WHERE status!='완료' AND alarm_enabled=1
             AND (visibility='public' OR owner_user_id=?)
        """,
        (user_id,)
    )
    out = []
    for r in rows:
        if not r.get("due_time") or r.get("alarm_notified"):
            continue
        try:
            dt = datetime.strptime(r["due_date"]+" "+r["due_time"],"%Y-%m-%d %H:%M")
        except Exception:
            continue
        if dt <= now:
            out.append(r)
    return out

def extract_text_tesseract(uploaded_file):
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(uploaded_file).convert("RGB"), lang="eng+kor")
    except Exception:
        return ""

def best_effort_autofill(text):
    nums = re.findall(r"[-+]?(?:\d+\.\d+|\d+)", (text or "").replace(",","."))
    out = {r["key"]:"" for r in CHECK_RULES}
    numeric_rules = [r for r in CHECK_RULES if r["kind"]=="range"]
    for r, token in zip(numeric_rules, nums):
        out[r["key"]] = token
    if "양호" in (text or ""):
        for r in CHECK_RULES:
            if r["kind"]=="text_ok":
                out[r["key"]] = "양호"
    return out
