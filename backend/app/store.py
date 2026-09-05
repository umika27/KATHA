import sqlite3
from pathlib import Path
from .models import Session
from .config import settings

class SessionRepository:
 def get(self,id): raise NotImplementedError
 def save(self,s): raise NotImplementedError
class SQLiteLikeJsonRepository(SessionRepository):
 """SQLite persistence behind a replaceable repository contract."""
 def __init__(self,path=None):
  configured=settings.database_url.removeprefix("sqlite:///")
  self.path=Path(path or configured); self.path.parent.mkdir(parents=True,exist_ok=True)
  with sqlite3.connect(self.path) as db:
   db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
   if not db.execute("SELECT 1 FROM schema_version").fetchone(): db.execute("INSERT INTO schema_version VALUES (1)")
   db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
   columns={row[1] for row in db.execute("PRAGMA table_info(sessions)")}
   if "updated_at" not in columns: db.execute("ALTER TABLE sessions ADD COLUMN updated_at TEXT")
 def get(self,id):
  with sqlite3.connect(self.path) as db: row=db.execute("SELECT payload FROM sessions WHERE id=?",(id,)).fetchone()
  return Session.model_validate_json(row[0]) if row else Session(id=id)
 def save(self,s):
  with sqlite3.connect(self.path) as db: db.execute("INSERT INTO sessions(id,payload) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP",(s.id,s.model_dump_json()))
  return s
 def reset(self,id,session): return self.save(session)
