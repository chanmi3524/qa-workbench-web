
from __future__ import annotations
import sqlite3
import os
import hashlib
import hmac
from pathlib import Path
from datetime import date, timedelta, datetime

DB_PATH = Path(__file__).resolve().parent / "qa_workbench.db"

def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def _columns(cur, table):
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}

def _add_column(cur, table, definition):
    name = definition.split()[0]
    if name not in _columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

def init_db():
    con = connect()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER,
        username TEXT,
        display_name TEXT,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT,
        summary TEXT NOT NULL
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

    # Safe migrations: existing DBs are preserved.
    _add_column(cur, "tasks", "visibility TEXT DEFAULT 'public'")
    _add_column(cur, "tasks", "owner_user_id INTEGER")
    _add_column(cur, "tasks", "owner_name TEXT DEFAULT ''")
    _add_column(cur, "tasks", "created_at TEXT DEFAULT ''")
    _add_column(cur, "tasks", "updated_at TEXT DEFAULT ''")

    for table in ("deliveries", "inspections", "defects", "erp_items", "production_plans"):
        _add_column(cur, table, "created_by TEXT DEFAULT ''")
        _add_column(cur, table, "updated_by TEXT DEFAULT ''")

    # Legacy tasks become shared/public.
    cur.execute("UPDATE tasks SET visibility='public' WHERE visibility IS NULL OR visibility=''")

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
        cur.executemany(
            "INSERT INTO erp_items(code,name,item_type,unit,stock,safety_stock) VALUES(?,?,?,?,?,?)",
            items
        )
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
            [
                ("K1A2",10,str(today+timedelta(days=14)),"계획"),
                ("K1A2",5,str(today+timedelta(days=28)),"계획"),
            ],
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

def _hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 150_000)
    return f"{salt.hex()}${digest.hex()}"

def create_user(username, display_name, password):
    username = username.strip().lower()
    display_name = display_name.strip()
    if not username or not display_name or len(password) < 4:
        raise ValueError("아이디/이름을 입력하고 비밀번호는 4자 이상으로 설정해 주세요.")
    con = connect()
    cur = con.cursor()
    count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    role = "admin" if count == 0 else "user"
    try:
        cur.execute(
            "INSERT INTO users(username,display_name,password_hash,role,active,created_at) VALUES(?,?,?,?,1,?)",
            (username, display_name, _hash_password(password), role, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        uid = cur.lastrowid
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise ValueError("이미 사용 중인 아이디입니다.")
    con.close()
    return get_user(uid)

def verify_user(username, password):
    user = fetch_one("SELECT * FROM users WHERE username=? AND active=1", (username.strip().lower(),))
    if not user:
        return None
    try:
        salt_hex, expected_hex = user["password_hash"].split("$", 1)
        actual = _hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        if hmac.compare_digest(actual, expected_hex):
            return user
    except Exception:
        pass
    return None

def get_user(user_id):
    return fetch_one("SELECT id,username,display_name,role,active,created_at FROM users WHERE id=?", (user_id,))

def change_password(user_id, old_password, new_password):
    user = fetch_one("SELECT * FROM users WHERE id=? AND active=1", (user_id,))
    if not user or not verify_user(user["username"], old_password):
        raise ValueError("현재 비밀번호가 맞지 않습니다.")
    if len(new_password) < 4:
        raise ValueError("새 비밀번호는 4자 이상으로 설정해 주세요.")
    execute("UPDATE users SET password_hash=? WHERE id=?", (_hash_password(new_password), user_id))

def update_display_name(user_id, display_name):
    display_name = display_name.strip()
    if not display_name:
        raise ValueError("이름을 입력해 주세요.")
    execute("UPDATE users SET display_name=? WHERE id=?", (display_name, user_id))

def log_action(user, action, entity_type, entity_id, summary):
    execute(
        """INSERT INTO audit_log(
            created_at,user_id,username,display_name,action,entity_type,entity_id,summary
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user.get("id"), user.get("username"), user.get("display_name"),
            action, entity_type, str(entity_id) if entity_id is not None else "", summary
        )
    )
