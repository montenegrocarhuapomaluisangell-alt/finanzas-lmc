import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "finanzas_lmc.db")

app = Flask(__name__, static_folder=BASE_DIR)
app.secret_key = "finanzas-lmc-secure-key-#9812-montenegro"

# Cross-origin and proxy session cookies configuration
app.config.update(
    SESSION_COOKIE_NAME='flmc_session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False, # Allows local IP and HTTP
    PERMANENT_SESSION_LIFETIME=86400 * 365 * 10 # Sesion permanente (10 anos)
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Budgets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        limit_amount REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Savings goals table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        target REAL NOT NULL,
        current REAL DEFAULT 0,
        icon TEXT DEFAULT '🎯',
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    # Registration requests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registration_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create default user 'Montenegro' if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'Montenegro' OR username = 'montenegro'")
    user = cursor.fetchone()
    if not user:
        pwd_hash = generate_password_hash("123456")
        cursor.execute("""
        INSERT INTO users (username, full_name, email, password_hash, role)
        VALUES (?, ?, ?, ?, ?)
        """, ('Montenegro', 'Luis Ángel Montenegro', 'montenegrocarhuapomaluisangell@gmail.com', pwd_hash, 'admin'))
        user_id = cursor.lastrowid
        
        # Insert initial demo data for Montenegro
        cursor.execute("INSERT INTO transactions (user_id, type, description, amount, category, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, 'income', 'Sueldo mensual', 5200.0, 'Salario', '2026-10-01'))
        cursor.execute("INSERT INTO transactions (user_id, type, description, amount, category, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, 'income', 'Consultoría Financiera', 1800.0, 'Freelance', '2026-10-05'))
        cursor.execute("INSERT INTO transactions (user_id, type, description, amount, category, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, 'expense', 'Alquiler oficina', 1400.0, 'Vivienda', '2026-10-01'))
        cursor.execute("INSERT INTO transactions (user_id, type, description, amount, category, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, 'expense', 'Supermercado Wong', 420.0, 'Alimentación', '2026-10-03'))
        cursor.execute("INSERT INTO transactions (user_id, type, description, amount, category, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, 'expense', 'Combustible Repsol', 180.0, 'Transporte', '2026-10-04'))
        cursor.execute("INSERT INTO transactions (user_id, type, description, amount, category, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, 'expense', 'Luz + Internet fibra', 260.0, 'Servicios', '2026-10-05'))
        cursor.execute("INSERT INTO transactions (user_id, type, description, amount, category, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, 'income', 'Dividendos inversión BVL', 650.0, 'Inversiones', '2026-10-15'))
                       
        cursor.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, ?, ?)", (user_id, 'Alimentación', 800.0))
        cursor.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, ?, ?)", (user_id, 'Transporte', 400.0))
        cursor.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, ?, ?)", (user_id, 'Servicios', 350.0))
        cursor.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, ?, ?)", (user_id, 'Entretenimiento', 300.0))
        
        cursor.execute("INSERT INTO goals (user_id, name, target, current, icon) VALUES (?, ?, ?, ?, ?)",
                       (user_id, 'Fondo de Reserva', 25000.0, 18500.0, '🛡️'))
        cursor.execute("INSERT INTO goals (user_id, name, target, current, icon) VALUES (?, ?, ?, ?, ?)",
                       (user_id, 'Inversión en Bienes Raíces', 50000.0, 12000.0, '🏢'))
        cursor.execute("INSERT INTO goals (user_id, name, target, current, icon) VALUES (?, ?, ?, ?, ?)",
                       (user_id, 'Viaje Internacional', 8000.0, 5400.0, '✈️'))
        
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(BASE_DIR, filename)

# ═══════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        return jsonify({"success": False, "error": "Ingresa usuario y contraseña"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)", (username, username))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user["password_hash"], password):
        session.permanent = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["full_name"] = user["full_name"]
        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"]
            }
        })
    return jsonify({"success": False, "error": "Credenciales inválidas"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, email, role FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify({"authenticated": True, "user": dict(user)})
    return jsonify({"authenticated": False}), 401

@app.route("/api/register-request", methods=["POST"])
def register_request():
    data = request.json or {}
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if not full_name or not email:
        return jsonify({"success": False, "error": "Nombre y correo son obligatorios"}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Save to registration requests
    cursor.execute("""
    INSERT INTO registration_requests (full_name, email, phone)
    VALUES (?, ?, ?)
    """, (full_name, email, phone))

    # Also automatically create user account so the new user has their own isolated account!
    username = email.split("@")[0].replace(".", "_")
    # ensure unique username
    base_user = username
    c = 1
    while True:
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        if not cursor.fetchone():
            break
        username = f"{base_user}_{c}"
        c += 1

    pwd_to_use = password if password else "123456"
    pwd_hash = generate_password_hash(pwd_to_use)

    cursor.execute("""
    INSERT INTO users (username, full_name, email, password_hash, role)
    VALUES (?, ?, ?, ?, 'member')
    """, (username, full_name, email, pwd_hash))
    new_user_id = cursor.lastrowid

    # Give the new user their own clean demo data
    cursor.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, 'Alimentación', 500.0)", (new_user_id,))
    cursor.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, 'Transporte', 200.0)", (new_user_id,))
    cursor.execute("INSERT INTO goals (user_id, name, target, current, icon) VALUES (?, 'Mi Primer Ahorro', 1000.0, 150.0, '🎯')", (new_user_id,))

    conn.commit()
    conn.close()

    # Log notification targeted to admin email
    admin_email = "montenegrocarhuapomaluisangell@gmail.com"
    print(f"\n[NOTIFICACION CORREO a {admin_email}]:")
    print(f"Nueva solicitud de cuenta recibida de: {full_name} ({email}) - Usuario asignado: {username}\n")

    return jsonify({
        "success": True,
        "message": f"Solicitud enviada a {admin_email}. Tu usuario asignado es: {username}",
        "assigned_username": username
    })

@app.route("/api/change-password", methods=["POST"])
def change_password():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "No has iniciado sesión o la sesión expiró"}), 401

    data = request.json or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"success": False, "error": "Debes ingresar tu contraseña actual y la nueva"}), 400

    if len(new_password) < 4:
        return jsonify({"success": False, "error": "La contraseña debe tener mínimo 4 caracteres"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], current_password):
        conn.close()
        return jsonify({"success": False, "error": "La contraseña actual no es correcta"}), 400

    # PBKDF2 with salt preserves exact casing, digits, letters and symbols
    new_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Contraseña actualizada correctamente"})

# ═══════════════════════════════════════
# DATA SYNC ENDPOINTS (SQLite)
# ═══════════════════════════════════════
@app.route("/api/data", methods=["GET"])
def get_user_data():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "No autorizado"}), 401
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, type, description, amount, category, date FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", (user_id,))
    transactions = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT id, category, limit_amount as [limit] FROM budgets WHERE user_id = ?", (user_id,))
    budgets = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT id, name, target, current, icon FROM goals WHERE user_id = ?", (user_id,))
    goals = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return jsonify({
        "transactions": transactions,
        "budgets": budgets,
        "goals": goals
    })

@app.route("/api/data/sync", methods=["POST"])
def sync_user_data():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "No autorizado"}), 401
    data = request.json or {}
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Replace transactions
    if "transactions" in data:
        cursor.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
        for t in data["transactions"]:
            cursor.execute("""
            INSERT INTO transactions (id, user_id, type, description, amount, category, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (t.get("id"), user_id, t["type"], t["description"], float(t["amount"]), t["category"], t["date"]))
            
    # Replace budgets
    if "budgets" in data:
        cursor.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
        for b in data["budgets"]:
            cursor.execute("""
            INSERT INTO budgets (id, user_id, category, limit_amount)
            VALUES (?, ?, ?, ?)
            """, (b.get("id"), user_id, b["category"], float(b["limit"])))
            
    # Replace goals
    if "goals" in data:
        cursor.execute("DELETE FROM goals WHERE user_id = ?", (user_id,))
        for g in data["goals"]:
            cursor.execute("""
            INSERT INTO goals (id, user_id, name, target, current, icon)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (g.get("id"), user_id, g["name"], float(g["target"]), float(g.get("current", 0)), g.get("icon", "🎯")))
            
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    print("Servidor Finanzas LMC corriendo en http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
