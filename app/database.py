import os
import shutil
import sqlite3
import sys
from datetime import date, datetime


class Singleton(type):
    """单例元类"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabaseManager(metaclass=Singleton):
    """数据库管理器——单例模式，管理 SQLite 连接、迁移与 CRUD"""

    TARGET_SCHEMA_VERSION = 5
    DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    DB_PATH = os.path.join(DB_DIR, "lifebutler.db")

    def __init__(self):
        # Tests use LIFEBUTLER_DB_PATH so they can exercise migrations without
        # touching the user's real data/lifebutler.db file.
        db_path = os.environ.get("LIFEBUTLER_DB_PATH", self._default_db_path())
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        existed = os.path.exists(db_path)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.init_tables()
        self._migrate(existed)

    @classmethod
    def _default_db_path(cls) -> str:
        if not getattr(sys, "frozen", False):
            return cls.DB_PATH
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support/LifeButler")
        elif sys.platform.startswith("win"):
            base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "LifeButler")
        else:
            base = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "LifeButler")
        return os.path.join(base, "data", "lifebutler.db")

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

            CREATE TABLE IF NOT EXISTS objectives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                period TEXT NOT NULL DEFAULT 'quarter',
                year INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                weight INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK(period IN ('month','quarter','year')),
                CHECK(status IN ('active','archived','abandoned')),
                CHECK(weight > 0)
            );

            CREATE TABLE IF NOT EXISTS key_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                objective_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                metric_type TEXT NOT NULL DEFAULT 'number',
                current_value REAL NOT NULL DEFAULT 0,
                target_value REAL NOT NULL DEFAULT 100,
                unit TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(objective_id) REFERENCES objectives(id) ON DELETE CASCADE,
                CHECK(metric_type IN ('number','percentage','boolean')),
                CHECK(status IN ('active','archived','abandoned'))
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                objective_id INTEGER,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(objective_id) REFERENCES objectives(id) ON DELETE SET NULL,
                CHECK(status IN ('planning','active','paused','completed'))
            );

            CREATE TABLE IF NOT EXISTS weekly_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                today_task_date TEXT DEFAULT '',
                completion INTEGER NOT NULL DEFAULT 0,
                progress_note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(task_id, year, week),
                FOREIGN KEY(task_id) REFERENCES todos(id) ON DELETE CASCADE,
                CHECK(week >= 1 AND week <= 53),
                CHECK(completion >= 0 AND completion <= 100)
            );

            CREATE TABLE IF NOT EXISTS weekly_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                proud TEXT DEFAULT '',
                change TEXT DEFAULT '',
                "commit" TEXT DEFAULT '',
                auto_summary TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(year, week)
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
        if version < 4:
            self._migrate_to_v4()
            version = 4
        if version < 5:
            self._migrate_to_v5()
            version = 5
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

    def _migrate_to_v4(self):
        self.conn.execute("BEGIN")
        try:
            now = datetime.now().isoformat()
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS objectives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    period TEXT NOT NULL DEFAULT 'quarter',
                    year INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    weight INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK(period IN ('month','quarter','year')),
                    CHECK(status IN ('active','archived','abandoned')),
                    CHECK(weight > 0)
                );

                CREATE TABLE IF NOT EXISTS key_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    objective_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    metric_type TEXT NOT NULL DEFAULT 'number',
                    current_value REAL NOT NULL DEFAULT 0,
                    target_value REAL NOT NULL DEFAULT 100,
                    unit TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(objective_id) REFERENCES objectives(id) ON DELETE CASCADE,
                    CHECK(metric_type IN ('number','percentage','boolean')),
                    CHECK(status IN ('active','archived','abandoned'))
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    objective_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(objective_id) REFERENCES objectives(id) ON DELETE SET NULL,
                    CHECK(status IN ('planning','active','paused','completed'))
                );

                CREATE TABLE IF NOT EXISTS weekly_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    today_task_date TEXT DEFAULT '',
                    completion INTEGER NOT NULL DEFAULT 0,
                    progress_note TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(task_id, year, week),
                    FOREIGN KEY(task_id) REFERENCES todos(id) ON DELETE CASCADE,
                    CHECK(week >= 1 AND week <= 53),
                    CHECK(completion >= 0 AND completion <= 100)
                );

                CREATE TABLE IF NOT EXISTS weekly_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    proud TEXT DEFAULT '',
                    change TEXT DEFAULT '',
                    "commit" TEXT DEFAULT '',
                    auto_summary TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(year, week)
                );
            """)
            if "updated_at" in self._columns("todos"):
                self.conn.execute(
                    "UPDATE todos SET updated_at=COALESCE(NULLIF(updated_at, ''), created_at, ?) "
                    "WHERE updated_at IS NULL OR updated_at=''",
                    (now,),
                )
            self.conn.execute(
                "INSERT INTO schema_meta (key,value) VALUES ('schema_version','4') "
                "ON CONFLICT(key) DO UPDATE SET value='4'"
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _migrate_to_v5(self):
        # v5 removes the task-project binding. Rebuild todos so old v4
        # databases lose project_id while preserving task and scheduling data.
        columns = self._columns("todos")
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.execute("BEGIN")
        try:
            self.conn.execute("""
                CREATE TABLE todos_v5_migration (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    priority TEXT NOT NULL CHECK(priority IN ('high','medium','low')),
                    due_date TEXT,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done')),
                    created_at TEXT NOT NULL,
                    quadrant TEXT NOT NULL DEFAULT 'q2',
                    today_date TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                )
            """)
            insert_columns = [
                "id",
                "title",
                "priority",
                "due_date",
                "status",
                "created_at",
                "quadrant",
                "today_date",
                "updated_at",
            ]
            select_parts = []
            now = datetime.now().isoformat()
            for column in insert_columns:
                if column in columns:
                    if column == "updated_at":
                        select_parts.append(f"COALESCE(NULLIF({column}, ''), created_at, '{now}')")
                    elif column == "quadrant":
                        select_parts.append(f"COALESCE(NULLIF({column}, ''), 'q2')")
                    elif column == "today_date":
                        select_parts.append(f"COALESCE({column}, '')")
                    else:
                        select_parts.append(column)
                elif column == "quadrant":
                    select_parts.append("'q2'")
                elif column == "today_date":
                    select_parts.append("''")
                elif column == "updated_at":
                    select_parts.append(f"COALESCE(created_at, '{now}')")
                elif column == "status":
                    select_parts.append("'pending'")
                elif column == "priority":
                    select_parts.append("'medium'")
                elif column == "due_date":
                    select_parts.append("''")
                elif column == "created_at":
                    select_parts.append(f"'{now}'")
                else:
                    select_parts.append(column)
            self.conn.execute(
                f"INSERT INTO todos_v5_migration ({', '.join(insert_columns)}) "
                f"SELECT {', '.join(select_parts)} FROM todos"
            )
            self.conn.execute("DROP TABLE todos")
            self.conn.execute("ALTER TABLE todos_v5_migration RENAME TO todos")
            self.conn.execute(
                "INSERT INTO schema_meta (key,value) VALUES ('schema_version','5') "
                "ON CONFLICT(key) DO UPDATE SET value='5'"
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self.conn.execute("PRAGMA foreign_keys=ON")

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

    def get_finance_totals_between(self, start_date: str, end_date: str) -> dict:
        rows = self.execute_query(
            "SELECT type, SUM(amount) as total FROM records WHERE date BETWEEN ? AND ? GROUP BY type",
            (start_date, end_date),
        )
        totals = {"income": 0.0, "expense": 0.0}
        for row in rows:
            totals[row["type"]] = float(row["total"] or 0)
        totals["balance"] = totals["income"] - totals["expense"]
        return totals

    # ==================== 目标 / KR / 项目 ====================

    def add_objective(self, title: str, description: str = "", period: str = "quarter", year: int | None = None, weight: int = 1) -> int:
        now = datetime.now().isoformat()
        target_year = year or date.today().year
        return self.execute(
            "INSERT INTO objectives (title,description,period,year,status,weight,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (title.strip(), description, period, target_year, "active", weight, now, now),
        )

    def update_objective(self, oid: int, title: str, description: str, period: str, year: int, status: str, weight: int) -> None:
        self.execute(
            "UPDATE objectives SET title=?,description=?,period=?,year=?,status=?,weight=?,updated_at=? WHERE id=?",
            (title.strip(), description, period, year, status, weight, datetime.now().isoformat(), oid),
        )

    def delete_objective(self, oid: int) -> None:
        self.execute("DELETE FROM objectives WHERE id=?", (oid,))

    def get_objective(self, oid: int) -> dict | None:
        rows = self.execute_query("SELECT * FROM objectives WHERE id=?", (oid,))
        return rows[0] if rows else None

    def get_objectives(self, status_filter: str = "active") -> list[dict]:
        if status_filter == "all":
            return self.execute_query("SELECT * FROM objectives ORDER BY year DESC, weight DESC, updated_at DESC")
        return self.execute_query(
            "SELECT * FROM objectives WHERE status=? ORDER BY year DESC, weight DESC, updated_at DESC",
            (status_filter,),
        )

    def add_key_result(self, objective_id: int, title: str, metric_type: str = "number", current_value: float = 0, target_value: float = 100, unit: str = "") -> int:
        now = datetime.now().isoformat()
        return self.execute(
            "INSERT INTO key_results (objective_id,title,metric_type,current_value,target_value,unit,status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (objective_id, title.strip(), metric_type, current_value, target_value, unit, "active", now, now),
        )

    def update_key_result(self, kr_id: int, title: str, metric_type: str, current_value: float, target_value: float, unit: str, status: str) -> None:
        self.execute(
            "UPDATE key_results SET title=?,metric_type=?,current_value=?,target_value=?,unit=?,status=?,updated_at=? WHERE id=?",
            (title.strip(), metric_type, current_value, target_value, unit, status, datetime.now().isoformat(), kr_id),
        )

    def update_key_result_progress(self, kr_id: int, current_value: float) -> None:
        self.execute(
            "UPDATE key_results SET current_value=?, updated_at=? WHERE id=?",
            (current_value, datetime.now().isoformat(), kr_id),
        )

    def delete_key_result(self, kr_id: int) -> None:
        self.execute("DELETE FROM key_results WHERE id=?", (kr_id,))

    def get_key_results(self, objective_id: int | None = None, status_filter: str = "active") -> list[dict]:
        clauses = []
        params = []
        if objective_id is not None:
            clauses.append("objective_id=?")
            params.append(objective_id)
        if status_filter != "all":
            clauses.append("status=?")
            params.append(status_filter)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.execute_query(
            f"SELECT * FROM key_results{where} ORDER BY updated_at DESC, id DESC",
            tuple(params),
        )

    def add_project(self, title: str, description: str = "", objective_id: int | None = None, status: str = "active") -> int:
        now = datetime.now().isoformat()
        return self.execute(
            "INSERT INTO projects (objective_id,title,description,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (objective_id, title.strip(), description, status, now, now),
        )

    def update_project(self, project_id: int, title: str, description: str, objective_id: int | None, status: str) -> None:
        self.execute(
            "UPDATE projects SET objective_id=?,title=?,description=?,status=?,updated_at=? WHERE id=?",
            (objective_id, title.strip(), description, status, datetime.now().isoformat(), project_id),
        )

    def delete_project(self, project_id: int) -> None:
        self.execute("DELETE FROM projects WHERE id=?", (project_id,))

    def get_project(self, project_id: int) -> dict | None:
        rows = self.execute_query("SELECT * FROM projects WHERE id=?", (project_id,))
        return rows[0] if rows else None

    def get_projects(self, objective_id: int | None = None, status_filter: str = "active") -> list[dict]:
        clauses = []
        params = []
        if objective_id is not None:
            clauses.append("objective_id=?")
            params.append(objective_id)
        if status_filter != "all":
            clauses.append("status=?")
            params.append(status_filter)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.execute_query(
            f"SELECT * FROM projects{where} ORDER BY updated_at DESC, id DESC",
            tuple(params),
        )

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

    # ==================== 周计划 / 周报 ====================

    def add_weekly_task(self, task_id: int, year: int, week: int) -> int:
        now = datetime.now().isoformat()
        existing = self.execute_query(
            "SELECT id FROM weekly_tasks WHERE task_id=? AND year=? AND week=?",
            (task_id, year, week),
        )
        if existing:
            return existing[0]["id"]
        return self.execute(
            "INSERT INTO weekly_tasks (task_id,year,week,today_task_date,completion,progress_note,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (task_id, year, week, "", 0, "", now, now),
        )

    def remove_weekly_task(self, weekly_task_id: int) -> None:
        self.execute("DELETE FROM weekly_tasks WHERE id=?", (weekly_task_id,))

    def get_weekly_tasks(self, year: int, week: int) -> list[dict]:
        return self.execute_query(
            """
            SELECT wt.*, t.title, t.priority, t.due_date, t.status AS task_status,
                   t.quadrant, t.today_date
            FROM weekly_tasks wt
            JOIN todos t ON t.id = wt.task_id
            WHERE wt.year=? AND wt.week=?
            ORDER BY wt.created_at ASC, wt.id ASC
            """,
            (year, week),
        )

    def update_weekly_task(self, weekly_task_id: int, completion: int | None = None, progress_note: str | None = None, today_task_date: str | None = None) -> None:
        fields = []
        params = []
        if completion is not None:
            fields.append("completion=?")
            params.append(completion)
        if progress_note is not None:
            fields.append("progress_note=?")
            params.append(progress_note)
        if today_task_date is not None:
            fields.append("today_task_date=?")
            params.append(today_task_date)
        if not fields:
            return
        fields.append("updated_at=?")
        params.append(datetime.now().isoformat())
        params.append(weekly_task_id)
        self.execute(
            f"UPDATE weekly_tasks SET {', '.join(fields)} WHERE id=?",
            tuple(params),
        )

    def get_weekly_review(self, year: int, week: int) -> dict | None:
        rows = self.execute_query(
            "SELECT * FROM weekly_reviews WHERE year=? AND week=?",
            (year, week),
        )
        return rows[0] if rows else None

    def save_weekly_review(self, year: int, week: int, proud: str, change: str, commit: str, auto_summary: str) -> int:
        now = datetime.now().isoformat()
        existing = self.get_weekly_review(year, week)
        if existing:
            self.execute(
            "UPDATE weekly_reviews SET proud=?,change=?," '"commit"' "=?,auto_summary=?,updated_at=? WHERE id=?",
                (proud, change, commit, auto_summary, now, existing["id"]),
            )
            return existing["id"]
        return self.execute(
            "INSERT INTO weekly_reviews (year,week,proud,change," '"commit"' ",auto_summary,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (year, week, proud, change, commit, auto_summary, now, now),
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

    def get_pomodoro_totals_between(self, start_date: str, end_date: str) -> dict:
        rows = self.execute_query(
            "SELECT COUNT(*) as count, SUM(actual_minutes) as minutes FROM pomodoro_sessions "
            "WHERE status='completed' AND substr(started_at, 1, 10) BETWEEN ? AND ?",
            (start_date, end_date),
        )
        row = rows[0] if rows else {}
        return {"count": row.get("count", 0) or 0, "minutes": row.get("minutes", 0) or 0}

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

    def get_exercise_minutes_between(self, start_date: str, end_date: str) -> int:
        rows = self.execute_query(
            "SELECT SUM(duration) as total FROM health_exercise WHERE date BETWEEN ? AND ?",
            (start_date, end_date),
        )
        return int((rows[0]["total"] if rows else 0) or 0)

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
