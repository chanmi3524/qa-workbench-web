
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import date, timedelta

DB_PATH = Path(__file__).resolve().parent / "qa_workbench.db"

def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = connect()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    );
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        due_date TEXT NOT NULL,
        due_time TEXT,
        category TEXT,
        title TEXT NOT NULL,
        status TEXT DEFAULT '진행',
        note TEXT DEFAULT '',
        alarm_enabled INTEGER DEFAULT 1,
        alarm_notified INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS deliveries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        due_date TEXT NOT NULL,
        previous_due TEXT DEFAULT '',
        customer TEXT DEFAULT '',
        project TEXT DEFAULT '',
        item_code TEXT DEFAULT '',
        item_name TEXT DEFAULT '',
        qty REAL DEFAULT 0,
        process TEXT DEFAULT '자재준비',
        progress INTEGER DEFAULT 0,
        status TEXT DEFAULT '진행중',
        note TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS inspections(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspection_date TEXT NOT NULL,
        inspection_type TEXT DEFAULT '입고검사',
        item_code TEXT DEFAULT '',
        item_name TEXT DEFAULT '',
        supplier TEXT DEFAULT '',
        lot TEXT DEFAULT '',
        qty REAL DEFAULT 0,
        sample_qty REAL DEFAULT 0,
        result TEXT DEFAULT '합격',
        note TEXT DEFAULT '',
        details_json TEXT DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS defects(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        defect_date TEXT NOT NULL,
        source TEXT DEFAULT '수동등록',
        item_code TEXT DEFAULT '',
        item_name TEXT DEFAULT '',
        issue TEXT DEFAULT '',
        qty REAL DEFAULT 0,
        status TEXT DEFAULT '접수',
        owner TEXT DEFAULT '',
        due_date TEXT DEFAULT '',
        action TEXT DEFAULT '',
        source_inspection_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS erp_items(
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        item_type TEXT DEFAULT '원자재',
        unit TEXT DEFAULT 'EA',
        stock REAL DEFAULT 0,
        safety_stock REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS bom(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL,
        material_code TEXT NOT NULL,
        qty REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS production_plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL,
        qty REAL NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT DEFAULT '계획'
    );
    """)
    cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('user_name','사용자')")
    cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('app_password','0000')")

    if cur.execute("SELECT COUNT(*) FROM erp_items").fetchone()[0] == 0:
        items = [
            ("K1A2","K1A2 제어기","완제품","EA",3,2),
            ("PCB-K1A2","K1A2 PCB ASSY","반제품","EA",18,5),
            ("CASE-K1A2","알루미늄 케이스","부자재","EA",12,5),
            ("PAD-K1A2","방열패드","부자재","EA",20,10),
            ("BOLT-M3","M3 체결볼트","부자재","EA",60,30),
            ("CONN-12P","12P 커넥터","원자재","EA",8,5),
            ("HARNESS-K1A2","K1A2 하네스","반제품","EA",9,4),
        ]
        cur.executemany("INSERT INTO erp_items VALUES(?,?,?,?,?,?)", items)
        cur.executemany(
            "INSERT INTO bom(product_code,material_code,qty) VALUES(?,?,?)",
            [
                ("K1A2","PCB-K1A2",1),("K1A2","CASE-K1A2",1),
                ("K1A2","PAD-K1A2",2),("K1A2","BOLT-M3",8),
                ("K1A2","CONN-12P",2),("K1A2","HARNESS-K1A2",1),
            ],
        )
        today = date.today()
        cur.executemany(
            "INSERT INTO production_plans(product_code,qty,due_date,status) VALUES(?,?,?,?)",
            [("K1A2",10,str(today+timedelta(days=14)),"계획"),
             ("K1A2",5,str(today+timedelta(days=28)),"계획")]
        )
    con.commit()
    con.close()

def fetch_all(sql, params=()):
    con = connect()
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]

def fetch_one(sql, params=()):
    con = connect()
    r = con.execute(sql, params).fetchone()
    con.close()
    return dict(r) if r else None

def execute(sql, params=()):
    con = connect()
    cur = con.execute(sql, params)
    con.commit()
    rid = cur.lastrowid
    con.close()
    return rid
