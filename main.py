from flask import Flask, render_template_string, request, send_file, redirect, session, after_this_request
import py7zr, os, uuid, shutil, tempfile, secrets, csv
from datetime import datetime

app = Flask(__name__)
app.secret_key = "master_vault_app_v8_final"

LOGIN_PASS = "L3v1v4n1t3rs0n"
WORK_DIR = os.path.join(tempfile.gettempdir(), "vault_work")
LOG_FILE = "sleutel_logboek.csv"

if not os.path.exists(WORK_DIR):
    os.makedirs(WORK_DIR)
else:
    shutil.rmtree(WORK_DIR)
    os.makedirs(WORK_DIR)

HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SECURITY TERMINAL V5 - OPTIMIZED</title>
    <style>
        body { font-family: 'Courier New', monospace; background: #050505; color: #00ff41; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; text-transform: uppercase; }
        .app-container { width: 95%; max-width: 800px; border: 1px solid #00ff41; background: rgba(0, 20, 5, 0.95); padding: 30px; box-shadow: 0 0 40px rgba(0, 255, 65, 0.2); }
        h1 { font-size: 1.5em; border-bottom: 2px solid #00ff41; padding-bottom: 10px; margin-bottom: 20px; text-shadow: 0 0 10px #00ff41; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; }
        .box { border: 1px dashed #00ff41; padding: 20px; background: rgba(0, 255, 65, 0.02); }
        input, button { width: 100%; padding: 15px; margin-top: 10px; background: #000; border: 1px solid #00ff41; color: #00ff41; font-family: inherit; font-size: 1em; }
        button { cursor: pointer; font-weight: bold; transition: 0.3s; }
        button:hover { background: #00ff41; color: #000; box-shadow: 0 0 15px #00ff41; }
        .logout { color: #ff3344; text-decoration: none; font-size: 0.8em; float: right; border: 1px solid #ff3344; padding: 5px 10px; }
        .status-bar { margin-top: 30px; font-size: 0.8em; background: #001500; padding: 10px; border-left: 5px solid #00ff41; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="app-container">
        {% if not session.get('auth') %}
            <h1>> SYSTEM LOCKED</h1>
            <form method="POST" action="/login">
                <input type="password" name="p" placeholder="ENTER MASTER KEY" required autofocus>
                <button type="submit">AUTHENTICATE</button>
            </form>
        {% else %}
            <h1>> TERMINAL ONLINE <a href="/logout" class="logout">LOGOUT</a></h1>
            <div class="grid">
                <div class="box">
                    <h3>1. LOCK FILE (AES-256)</h3>
                    <form method="POST" action="/encrypt" enctype="multipart/form-data">
                        <input type="file" name="f" required>
                        <button type="submit">EXECUTE LOCK</button>
                    </form>
                </div>
                <div class="box">
                    <h3>2. UNLOCK FILE</h3>
                    <form method="POST" action="/decrypt" enctype="multipart/form-data">
                        <input type="file" name="f" accept=".7z" required>
                        <input type="text" name="k" placeholder="PASTE UNIQUE FILE KEY" required>
                        <button type="submit">EXECUTE UNLOCK</button>
                    </form>
                </div>
            </div>
            <div class="box" style="margin-top: 30px;">
                <h3>3. MASTER LOGBOOK (Excel)</h3>
                <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 15px;">
                    <form method="POST" action="/lock_log"><button type="submit">SECURE LOG (7Z)</button></form>
                    <form method="POST" action="/unlock_log" enctype="multipart/form-data">
                        <input type="file" name="f" accept=".7z" required>
                        <button type="submit">OPEN LOG</button>
                    </form>
                </div>
            </div>
        {% endif %}
        <div class="status-bar">>> STATUS: {{ msg }}</div>
    </div>
</body>
</html>
"""

def log_key(name, key):
    header = ["Datum", "Bestand", "Sleutel"]
    exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), name, key])

@app.route('/')
def index():
    return render_template_string(HTML, msg=request.args.get('m', 'SYSTEM_READY'))

@app.route('/login', methods=['POST'])
def login():
    if request.form.get('p') == LOGIN_PASS:
        session['auth'] = True
        return redirect('/')
    return redirect('/?m=ACCESS_DENIED')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/encrypt', methods=['POST'])
def encrypt():
    if not session.get('auth'): return redirect('/')
    f = request.files['f']
    gen_key = secrets.token_hex(16)
    log_key(f.filename, gen_key)

    job_id = uuid.uuid4().hex
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    p = os.path.join(job_dir, f.filename)
    f.save(p)

    out = p + ".7z"
    with py7zr.SevenZipFile(out, 'w', password=gen_key, header_encryption=True, filters=[{"id": py7zr.FILTER_COPY}]) as sz:
        sz.write(p, arcname=f.filename)

    return send_file(out, as_attachment=True, download_name=f.filename + ".7z")

@app.route('/decrypt', methods=['POST'])
def decrypt():
    if not session.get('auth'): return redirect('/')
    f, key = request.files['f'], request.form.get('k')
    job_id = uuid.uuid4().hex
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    p = os.path.join(job_dir, f.filename)
    f.save(p)

    try:
        with py7zr.SevenZipFile(p, 'r', password=key) as sz:
            sz.extractall(job_dir)

        extracted_file = None
        for n in os.listdir(job_dir):
            if n != f.filename:
                extracted_file = os.path.join(job_dir, n)
                break

        if extracted_file:
            return send_file(extracted_file, as_attachment=True)
        return redirect('/?m=ERROR_EXTRACTING_FILE')
    except:
        return redirect('/?m=INVALID_KEY_OR_CORRUPT')

@app.route('/lock_log', methods=['POST'])
def lock_log():
    if not session.get('auth') or not os.path.exists(LOG_FILE):
        return redirect('/?m=NO_LOG_FOUND')

    job_id = uuid.uuid4().hex
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    out = os.path.join(job_dir, "sleutel_logboek.7z")
    with py7zr.SevenZipFile(out, 'w', password=LOGIN_PASS, header_encryption=True) as sz:
        sz.write(LOG_FILE, arcname=LOG_FILE)
    return send_file(out, as_attachment=True)

@app.route('/unlock_log', methods=['POST'])
def unlock_log():
    if not session.get('auth'): return redirect('/')
    f = request.files['f']
    job_id = uuid.uuid4().hex
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    p = os.path.join(job_dir, f.filename)
    f.save(p)

    try:
        with py7zr.SevenZipFile(p, 'r', password=LOGIN_PASS) as sz:
            sz.extractall(job_dir)
        return send_file(os.path.join(job_dir, LOG_FILE), as_attachment=True, download_name="sleutel_logboek.csv")
    except:
        return redirect('/?m=LOG_AUTH_FAILED')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
