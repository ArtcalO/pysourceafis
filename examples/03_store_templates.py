"""
Store templates in SQLite and rebuild a gallery from them at start-up.

Templates are biometric data: this example keeps them in a local file only to
show the flow. In production encrypt them (e.g. AES-GCM with the row id as
associated data) and restrict access to the database.

    python examples/03_store_templates.py [database.sqlite]
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

from pysourceafis import Fingerprint, Gallery, engine_version
from pysourceafis.testing import synthetic_image


def open_db(path):
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE IF NOT EXISTS templates ("
        " person TEXT NOT NULL, finger TEXT NOT NULL, engine TEXT NOT NULL, template BLOB NOT NULL,"
        " PRIMARY KEY (person, finger))"
    )
    return db


def enroll(db, person, finger, fingerprint):
    db.execute(
        "INSERT OR REPLACE INTO templates VALUES (?, ?, ?, ?)",
        (person, finger, engine_version(), fingerprint.to_bytes()),
    )
    db.commit()


def load_gallery(db) -> Gallery:
    rows = db.execute("SELECT person, finger, engine, template FROM templates").fetchall()
    stale = [(p, f) for p, f, engine, _ in rows if engine != engine_version()]
    if stale:
        print(f"{len(stale)} templates come from another SourceAFIS version and must be re-extracted.")
    gallery = Gallery()
    failed = gallery.add_templates(((p, f), t) for p, f, engine, t in rows if engine == engine_version())
    print(f"gallery loaded: {len(gallery)} fingerprints ({len(failed)} invalid)")
    return gallery


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "pysourceafis-demo.sqlite"
    db = open_db(path)
    for i in range(10):  # SYNTHETIC demo enrollment
        enroll(db, f"person-{i}", "right-index", Fingerprint.from_bytes(synthetic_image(i, 0)))
    print(f"stored {db.execute('SELECT COUNT(*) FROM templates').fetchone()[0]} templates in {path}")

    with load_gallery(db) as gallery:  # e.g. after a restart: no images needed
        probe = Fingerprint.from_bytes(synthetic_image(4, 1))
        print("best match:", gallery.search(probe, top_k=1)[0])
    db.close()


if __name__ == "__main__":
    main()
