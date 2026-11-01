# Smart Folder Automation (Python + Flask + SQLite)

    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000

What it automates
- Sorts the files in a folder (for example Downloads) into Images, Documents, Videos, Audio, Archives, Code, Installers, Others
- Preview before running, one-click "Organise now", or a background scheduler (5 min / hourly / daily)
- Every move is stored in SQLite, so any run can be undone
- Dashboard: stats, category breakdown, run history (auto-refreshes every 15 s)

Safety
- Only folders inside your user folder are allowed (never the whole user folder, drives or system folders)
- Top-level files only; hidden files, symlinks and half-downloaded files (.crdownload, .part) are skipped
- Nothing is deleted or overwritten (name clashes become "file (1).pdf")
- Try it first on a test folder, for example C:\Users\<you>\Downloads\test
