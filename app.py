"""Smart Folder Automation: Flask dashboard + background scheduler + SQLite history."""
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import db
import organizer

app = Flask(__name__)
LOCK = threading.Lock()                 # manual runs, scheduler and undo never overlap
INTERVALS = (0, 5, 15, 60, 1440)        # minutes; 0 = manual only
STAMP = "%Y-%m-%d %H:%M:%S"


def stamp():
    return datetime.now().strftime(STAMP)


def rows(sql, args=()):
    with db.connect() as c:
        return [dict(r) for r in c.execute(sql, args)]


def get_folder(fid):
    r = rows("SELECT * FROM folders WHERE id=?", (fid,))
    return r[0] if r else None


def run_folder(folder, trigger):
    """Organise one watched folder and log the run. Returns a summary dict."""
    with LOCK:
        path = Path(folder["path"])
        _, err = organizer.validate_folder(str(path))
        if err:
            return {"error": err}
        moves, errors = organizer.execute(path, organizer.plan(path))
        run_id = None
        with db.connect() as c:
            if moves:
                run_id = c.execute("INSERT INTO runs (folder_path, started_at, trigger, moved_count, bytes) VALUES (?,?,?,?,?)",
                                   (str(path), stamp(), trigger, len(moves), sum(m["size"] for m in moves))).lastrowid
                c.executemany("INSERT INTO moves (run_id, src, dst, category, size) VALUES (?,?,?,?,?)",
                              [(run_id, m["src"], m["dst"], m["category"], m["size"]) for m in moves])
            c.execute("UPDATE folders SET last_run=? WHERE id=?", (stamp(), folder["id"]))
        return {"run_id": run_id, "moved": len(moves), "errors": errors}


def tick():
    """One scheduler pass: run every enabled folder whose interval has elapsed."""
    for f in rows("SELECT * FROM folders WHERE enabled=1 AND interval_minutes>0"):
        due = True
        if f["last_run"]:
            due = (datetime.now() - datetime.strptime(f["last_run"], STAMP)).total_seconds() >= f["interval_minutes"] * 60
        if due:
            run_folder(f, "auto")


def scheduler_loop():
    while True:
        try:
            tick()
        except Exception as e:           # keep the scheduler alive no matter what
            print("Scheduler error:", e)
        time.sleep(20)


# ---------------- pages & API ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/folders")
def list_folders():
    return jsonify(rows("SELECT * FROM folders ORDER BY id DESC"))


@app.post("/api/folders")
def add_folder():
    d = request.get_json(silent=True) or {}
    path, err = organizer.validate_folder(str(d.get("path", "")))
    interval = d.get("interval_minutes", 0)
    if err:
        return jsonify(error=err), 400
    if interval not in INTERVALS:
        return jsonify(error="Invalid interval"), 400
    try:
        with db.connect() as c:
            fid = c.execute("INSERT INTO folders (path, interval_minutes) VALUES (?,?)", (str(path), interval)).lastrowid
    except Exception:
        return jsonify(error="This folder is already being watched"), 409
    return jsonify(id=fid), 201


@app.patch("/api/folders/<int:fid>")
def update_folder(fid):
    d = request.get_json(silent=True) or {}
    if not get_folder(fid):
        return jsonify(error="Folder not found"), 404
    with db.connect() as c:
        if "interval_minutes" in d:
            if d["interval_minutes"] not in INTERVALS:
                return jsonify(error="Invalid interval"), 400
            c.execute("UPDATE folders SET interval_minutes=? WHERE id=?", (d["interval_minutes"], fid))
        if "enabled" in d:
            c.execute("UPDATE folders SET enabled=? WHERE id=?", (1 if d["enabled"] else 0, fid))
    return jsonify(ok=True)


@app.delete("/api/folders/<int:fid>")
def remove_folder(fid):
    with db.connect() as c:
        c.execute("DELETE FROM folders WHERE id=?", (fid,))
    return jsonify(ok=True)


@app.post("/api/folders/<int:fid>/preview")
def preview(fid):
    f = get_folder(fid)
    if not f:
        return jsonify(error="Folder not found"), 404
    path, err = organizer.validate_folder(f["path"])
    if err:
        return jsonify(error=err), 400
    items = organizer.plan(path)
    summary = {}
    for i in items:
        summary[i["category"]] = summary.get(i["category"], 0) + 1
    return jsonify(files=items[:500], summary=summary, total=len(items), bytes=sum(i["size"] for i in items))


@app.post("/api/folders/<int:fid>/run")
def run_now(fid):
    f = get_folder(fid)
    if not f:
        return jsonify(error="Folder not found"), 404
    res = run_folder(f, "manual")
    return (jsonify(res), 400) if "error" in res else jsonify(res)


@app.get("/api/runs")
def list_runs():
    return jsonify(rows("SELECT * FROM runs ORDER BY id DESC LIMIT 30"))


@app.get("/api/runs/<int:rid>")
def run_detail(rid):
    return jsonify(rows("SELECT src, dst, category, size FROM moves WHERE run_id=? ORDER BY id", (rid,)))


@app.post("/api/runs/<int:rid>/undo")
def undo(rid):
    with LOCK:
        r = rows("SELECT * FROM runs WHERE id=?", (rid,))
        if not r:
            return jsonify(error="Run not found"), 404
        if r[0]["status"] != "done":
            return jsonify(error="This run was already undone"), 409
        restored, missing = organizer.restore(rows("SELECT src, dst FROM moves WHERE run_id=? ORDER BY id", (rid,)))
        with db.connect() as c:
            c.execute("UPDATE runs SET status='undone' WHERE id=?", (rid,))
    return jsonify(restored=restored, missing=missing)


@app.get("/api/stats")
def stats():
    t = rows("SELECT COUNT(*) runs, COALESCE(SUM(moved_count),0) files, COALESCE(SUM(bytes),0) bytes FROM runs WHERE status='done'")[0]
    cats = rows("""SELECT m.category, COUNT(*) n FROM moves m JOIN runs r ON r.id=m.run_id
                   WHERE r.status='done' GROUP BY m.category ORDER BY n DESC""")
    return jsonify(runs=t["runs"], files=t["files"], bytes=t["bytes"], categories=cats,
                   folders=rows("SELECT COUNT(*) n FROM folders")[0]["n"])


db.init_db()
if __name__ == "__main__":
    threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run(debug=False)                 # debug off so the scheduler thread starts only once
