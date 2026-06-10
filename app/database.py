import os
import shutil
import sqlite3
from datetime import datetime


class Singleton(type):
    """单例元类"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabaseManager(metaclass=Singleton):
    """数据库管理器——单例模式，管理 SQLite 连接、迁移与 CRUD"""

    TARGET_SCHEMA_VERSION = 3
    DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    DB_PATH = os.path.join(DB_DIR, "lifebutler.db")

    def __init__(self):
        os.makedirs(self.DB_DIR, exist_ok=True)
        # Tests use LIFEBUTLER_DB_PATH so they can exercise migrations without
        # touching the user's real data/lifebutler.db file.
        db_path = os.environ.get("LIFEBUTLER_DB_PATH", self.DB_PATH)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        existed = os.path.exists(db_path)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.init_tables()
        self._migrate(existed)

    def init_tables(self):
        """初始化最新结构；旧库的约束差异由迁移函数修正。"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('income','expense')),
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                date TEXT NOT NULL,
                note TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                month TEXT NOT NULL,
                UNIQUE(category, month)
            );

            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('high','medium','low')),
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done')),
                created_at TEXT NOT NULL,
                quadrant TEXT NOT NULL DEFAULT 'q2',
                today_date TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS health_weight (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                weight REAL NOT NULL CHECK(weight > 0),
                height REAL NOT NULL CHECK(height > 0),
                bmi REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS health_exercise (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                duration INTEGER NOT NULL CHECK(duration > 0)
            );

            CREATE TABLE IF NOT EXISTS memos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '',
                is_pinned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                planned_minutes INTEGER NOT NULL CHECK(planned_minutes > 0),
                actual_minutes INTEGER NOT NULL CHECK(actual_minutes >= 0),
                status TEXT NOT NULL CHECK(status IN ('completed','stopped')),
                note TEXT DEFAULT '',
                FOREIGN KEY(task_id) REFERENCES todos(id) ON DELETE SET NULL
            );
        """)
        self.conn.commit()

    def _migrate(self, existed: bool):
        # init_tables() creates the latest tables for brand-new installs, but it
        # cannot change an existing table's columns or unique constraints.
        # Versioned migrations below handle those old-database upgrades safely.
        version = self._schema_version()
        if version == 0 and not existed:
            self._set_schema_version(self.TARGET_SCHEMA_VERSION)
            return
        if version == 0:
            version = 1
            self._backup_before_migration()
        elif version < self.TARGET_SCHEMA_VERSION:
            self._backup_before_migration()

        if version < 2:
            self._migrate_to_v2()
            version = 2
        if version < 3:
            self._migrate_to_v3()
            version = 3
        if version != self.TARGET_SCHEMA_VERSION:
            self._set_schema_version(self.TARGET_SCHEMA_VERSION)

    def _schema_version(self) -> int:
        row = self.conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def _set_schema_version(self, version: int):
        self.conn.execute(
            "INSERT INTO schema_meta (key,value) VALUES ('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(version),),
        )
        self.conn.commit()

    def _backup_before_migration(self):
        if not os.path.exists(self.db_path):
            return ""
        backup_name = f"lifebutler_backup_before_migration_{datetime.now():%Y%m%d_%H%M%S}.db"
        backup_path = os.path.join(os.path.dirname(self.db_path), backup_name)
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def _columns(self, table: str) -> set:
        return {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}

    def _migrate_to_v2(self):
        # v2 introduces the "today quadrant" task model and pomodoro history.
        # Columns are added defensively because old local databases may come
        # from slightly different development snapshots.
        columns = self._columns("todos")
        now = datetime.now().isoformat()
        self.conn.execute("BEGIN")
        try:
            if "quadrant" not in columns:
                self.conn.execute("ALTER TABLE todos ADD COLUMN quadrant TEXT NOT NULL DEFAULT 'q2'")
            if "today_date" not in columns:
                self.conn.execute("ALTER TABLE todos ADD COLUMN today_date TEXT DEFAULT ''")
            if "updated_at" not in columns:
                self.conn.execute("ALTER TABLE todos ADD COLUMN updated_at TEXT")
                self.conn.execute("UPDATE todos SET updated_at=COALESCE(created_at, ?)", (now,))
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    planned_minutes INTEGER NOT NULL CHECK(planned_minutes > 0),
                    actual_minutes INTEGER NOT NULL CHECK(actual_minutes >= 0),
                    status TEXT NOT NULL CHECK(status IN ('completed','stopped')),
                    note TEXT DEFAULT '',
                    FOREIGN KEY(task_id) REFERENCES todos(id) ON DELETE SET NULL
                )
            """)
            self.conn.execute(
                "INSERT INTO schema_meta (key,value) VALUES ('schema_version','2') "
                "ON CONFLICT(key) DO UPDATE SET value='2'"
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _migrate_to_v3(self):
        # SQLite cannot drop/replace a UNIQUE constraint in place, so budgets
        # are rebuilt to move from UNIQUE(category) to UNIQUE(category, month).
        self.conn.execute("BEGIN")
        try:
            self.conn.execute("ALTER TABLE budgets RENAME TO budgets_old_migration")
            self.conn.execute("""
                CREATE TABLE budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    month TEXT NOT NULL,
                    UNIQUE(category, month)
                )
            """)
            self.conn.execute("""
                INSERT INTO budgets (category, amount, month)
                SELECT category, MAX(amount), month
                FROM budgets_old_migration
                WHERE TRIM(category) != '' AND amount > 0 AND TRIM(month) != ''
                GROUP BY category, month
            """)
            self.conn.execute("DROP TABLE budgets_old_migration")
            self.conn.execute(
                "INSERT INTO schema_meta (key,value) VALUES ('schema_version','3') "
                "ON CONFLICT(key) DO UPDATE SET value='3'"
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def execute_query(self, sql: str, params: tuple = ()) -> list:
        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def execute(self, sql: str, params: tuple = ()):
        cursor = self.conn.execute(sql, params)
        self.conn.commit()
        return cursor.lastrowid

    def backup_data(self):
        backup_name = f"lifebutler_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
        backup_path = os.path.join(os.path.dirname(self.db_path), backup_name)
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def close(self):
        self.conn.close()

    # ==================== 记账模块 ====================

    def add_record(self, rec_type: str, category: str, amount: float, date: str, note: str = ""):
        return self.execute(
            "INSERT INTO records (type,category,amount,date,note) VALUES (?,?,?,?,?)",
            (rec_type, category.strip(), amount, date, note),
        )

    def update_record(self, rid: int, rec_type: str, category: str, amount: float, date: str, note: str):
        self.execute(
            "UPDATE records SET type=?,category=?,amount=?,date=?,note=? WHERE id=?",
            (rec_type, category.strip(), amount, date, note, rid),
        )

    def delete_record(self, rid: int):
        self.execute("DELETE FROM records WHERE id=?", (rid,))

    def get_records(self, year: int = 0, month: int = 0) -> list:
        if year and month:
            prefix = f"{year:04d}-{month:02d}"
            return self.execute_query(
                "SELECT * FROM records WHERE date LIKE ? ORDER BY date DESC, id DESC",
                (f"{prefix}%",),
            )
        return self.execute_query("SELECT * FROM records ORDER BY date DESC, id DESC")

    def get_monthly_stats(self, year: int, month: int) -> dict:
        prefix = f"{year:04d}-{month:02d}"
        rows = self.execute_query(
            "SELECT type, category, SUM(amount) as total FROM records WHERE date LIKE ? GROUP BY type, category",
            (f"{prefix}%",),
        )
        stats = {"income": {}, "expense": {}, "income_total": 0.0, "expense_total": 0.0}
        for row in rows:
            rec_type = row["type"]
            amount = row["total"]
            stats[rec_type][row["category"]] = amount
            stats[f"{rec_type}_total"] += amount
        return stats

    # ==================== 待办模块 ====================

    def add_todo(self, title: str, priority: str, due_date: str, quadrant: str = "q2", today_date: str = ""):
        now = datetime.now().isoformat()
        return self.execute(
            "INSERT INTO todos (title,priority,due_date,status,created_at,quadrant,today_date,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (title.strip(), priority, due_date, "pending", now, quadrant, today_date, now),
        )

    def update_todo(self, tid: int, title: str, priority: str, due_date: str, status: str, quadrant: str = "q2", today_date: str = ""):
        self.execute(
            "UPDATE todos SET title=?,priority=?,due_date=?,status=?,quadrant=?,today_date=?,updated_at=? WHERE id=?",
            (title.strip(), priority, due_date, status, quadrant, today_date, datetime.now().isoformat(), tid),
        )

    def delete_todo(self, tid: int):
        self.execute("DELETE FROM todos WHERE id=?", (tid,))

    def toggle_todo(self, tid: int):
        row = self.execute_query("SELECT status FROM todos WHERE id=?", (tid,))
        if row:
            new_status = "done" if row[0]["status"] == "pending" else "pending"
            self.execute(
                "UPDATE todos SET status=?, updated_at=? WHERE id=?",
                (new_status, datetime.now().isoformat(), tid),
            )

    def get_todo(self, tid: int) -> dict | None:
        rows = self.execute_query("SELECT * FROM todos WHERE id=?", (tid,))
        return rows[0] if rows else None

    def get_todos(self, status_filter: str = "all") -> list:
        if status_filter == "all":
            return self.execute_query("SELECT * FROM todos ORDER BY created_at DESC")
        return self.execute_query(
            "SELECT * FROM todos WHERE status=? ORDER BY created_at DESC", (status_filter,)
        )

    def mark_todo_today(self, tid: int, quadrant: str, today_date: str):
        self.execute(
            "UPDATE todos SET quadrant=?, today_date=?, updated_at=? WHERE id=?",
            (quadrant, today_date, datetime.now().isoformat(), tid),
        )

    def get_today_todos(self, today_date: str) -> list:
        # today_date <= today_date intentionally rolls unfinished tasks forward
        # without mutating their original today_date or due_date.
        return self.execute_query(
            "SELECT * FROM todos WHERE status='pending' AND today_date IS NOT NULL "
            "AND today_date != '' AND today_date <= ? ORDER BY quadrant ASC, updated_at DESC",
            (today_date,),
        )

    # ==================== 番茄钟模块 ====================

    def add_pomodoro_session(self, task_id: int | None, started_at: str, ended_at: str, planned_minutes: int, actual_minutes: int, status: str, note: str = ""):
        return self.execute(
            "INSERT INTO pomodoro_sessions (task_id,started_at,ended_at,planned_minutes,actual_minutes,status,note) "
            "VALUES (?,?,?,?,?,?,?)",
            (task_id, started_at, ended_at, planned_minutes, actual_minutes, status, note),
        )

    def get_pomodoro_stats_for_tasks(self, task_ids: list[int], date: str) -> dict:
        # The UI's "番茄/分钟" numbers count completed focus sessions only;
        # manually stopped sessions remain in history but do not count as done.
        if not task_ids:
            return {}
        placeholders = ",".join("?" for _ in task_ids)
        rows = self.execute_query(
            f"SELECT task_id, COUNT(*) as count, SUM(actual_minutes) as minutes "
            f"FROM pomodoro_sessions WHERE task_id IN ({placeholders}) "
            "AND status='completed' AND started_at LIKE ? GROUP BY task_id",
            tuple(task_ids) + (f"{date}%",),
        )
        return {row["task_id"]: {"count": row["count"], "minutes": row["minutes"] or 0} for row in rows}

    def get_pomodoro_sessions(self, task_id: int | None = None) -> list:
        if task_id:
            return self.execute_query(
                "SELECT * FROM pomodoro_sessions WHERE task_id=? ORDER BY started_at DESC",
                (task_id,),
            )
        return self.execute_query("SELECT * FROM pomodoro_sessions ORDER BY started_at DESC")

    # ==================== 健康模块 ====================

    def add_weight_record(self, date: str, weight: float, height: float):
        bmi = round(weight / ((height / 100) ** 2), 1)
        self.execute(
            "INSERT INTO health_weight (date,weight,height,bmi) VALUES (?,?,?,?) "
            "ON CONFLICT(date) DO UPDATE SET weight=excluded.weight,height=excluded.height,bmi=excluded.bmi",
            (date, weight, height, bmi),
        )

    def delete_weight_record(self, date: str):
        self.execute("DELETE FROM health_weight WHERE date=?", (date,))

    def get_weight_records(self, limit: int = 30) -> list:
        return self.execute_query(
            "SELECT * FROM health_weight ORDER BY date DESC LIMIT ?", (limit,)
        )

    def add_exercise(self, date: str, ex_type: str, duration: int):
        return self.execute(
            "INSERT INTO health_exercise (date,type,duration) VALUES (?,?,?)",
            (date, ex_type, duration),
        )

    def update_exercise(self, ex_id: int, date: str, ex_type: str, duration: int):
        self.execute(
            "UPDATE health_exercise SET date=?, type=?, duration=? WHERE id=?",
            (date, ex_type, duration, ex_id),
        )

    def delete_exercise(self, ex_id: int):
        self.execute("DELETE FROM health_exercise WHERE id=?", (ex_id,))

    def get_exercise_records(self, limit: int = 30) -> list:
        return self.execute_query(
            "SELECT * FROM health_exercise ORDER BY date DESC, id DESC LIMIT ?", (limit,)
        )

    def get_weekly_report(self) -> dict:
        rows = self.execute_query(
            "SELECT type, SUM(duration) as total FROM health_exercise "
            "WHERE date >= date('now','-7 days') GROUP BY type"
        )
        return {row["type"]: row["total"] for row in rows}

    # ==================== 备忘录模块 ====================

    def add_memo(self, title: str, content: str, category: str, tags: str):
        now = datetime.now().isoformat()
        return self.execute(
            "INSERT INTO memos (title,content,category,tags,is_pinned,created_at,updated_at) "
            "VALUES (?,?,?,?,0,?,?)",
            (title.strip(), content, category.strip() or "general", tags, now, now),
        )

    def update_memo(self, mid: int, title: str, content: str, category: str, tags: str, is_pinned: int):
        now = datetime.now().isoformat()
        self.execute(
            "UPDATE memos SET title=?,content=?,category=?,tags=?,is_pinned=?,updated_at=? WHERE id=?",
            (title.strip(), content, category.strip() or "general", tags, is_pinned, now, mid),
        )

    def delete_memo(self, mid: int):
        self.execute("DELETE FROM memos WHERE id=?", (mid,))

    def toggle_pin(self, mid: int):
        row = self.execute_query("SELECT is_pinned FROM memos WHERE id=?", (mid,))
        if row:
            new_pin = 0 if row[0]["is_pinned"] else 1
            self.execute(
                "UPDATE memos SET is_pinned=?, updated_at=? WHERE id=?",
                (new_pin, datetime.now().isoformat(), mid),
            )

    def get_memos(self, category: str = "") -> list:
        if category:
            return self.execute_query(
                "SELECT * FROM memos WHERE category=? ORDER BY is_pinned DESC, updated_at DESC",
                (category,),
            )
        return self.execute_query("SELECT * FROM memos ORDER BY is_pinned DESC, updated_at DESC")

    def search_memos(self, keyword: str) -> list:
        return self.execute_query(
            "SELECT * FROM memos WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? "
            "ORDER BY is_pinned DESC, updated_at DESC",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
        )
