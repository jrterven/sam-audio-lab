import json
import sqlite3
import time
import uuid
from .config import DATA


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'lab.sqlite', timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT, created REAL, body TEXT)')
    return db


def save(kind, body, record_id=None):
    record_id = record_id or uuid.uuid4().hex
    body = dict(body, id=record_id, kind=kind)
    with connect() as db:
        old = db.execute('SELECT created FROM records WHERE id=?', (record_id,)).fetchone()
        body['created'] = old[0] if old else time.time()
        db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?)',
                   (record_id, kind, body['created'], json.dumps(body, allow_nan=False)))
    return body


def get(record_id, kind=None):
    with connect() as db:
        row = db.execute('SELECT kind,body FROM records WHERE id=?', (record_id,)).fetchone()
    if not row or (kind and row[0] != kind):
        raise KeyError(record_id)
    return json.loads(row[1])


def all_of(kind):
    with connect() as db:
        rows = db.execute('SELECT body FROM records WHERE kind=? ORDER BY created DESC', (kind,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def update(record_id, **changes):
    body = get(record_id)
    return save(body['kind'], dict(body, **changes), record_id)
