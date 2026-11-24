from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = "ticket-secret-2024"

# ── Demo users ────────────────────────────────────────────────
USERS = {"admin": "admin123", "agent": "agent123"}

# ── In-memory ticket store ────────────────────────────────────
TICKETS = {}

def seed():
    samples = [
        ("Cannot access VPN", "User cannot connect to corporate VPN from home.", "High", "Open", "Network"),
        ("Laptop running slow", "MacBook Pro takes 10+ minutes to boot.", "Medium", "In Progress", "Hardware"),
        ("Outlook not syncing", "New emails not appearing in Outlook desktop client.", "Medium", "Open", "Software"),
        ("Printer offline – 3rd floor", "HP LaserJet shows offline despite being powered on.", "Low", "Resolved", "Hardware"),
        ("Password reset request", "User locked out of Active Directory account.", "High", "Open", "Access"),
    ]
    for title, desc, priority, status, category in samples:
        tid = "TKT-" + str(uuid.uuid4())[:8].upper()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        TICKETS[tid] = dict(id=tid, title=title, description=desc,
                            priority=priority, status=status,
                            category=category, assignee="",
                            created_at=now, updated_at=now)

seed()

# ── Auth decorator ────────────────────────────────────────────
from functools import wraps
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("tickets") if "user" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form["username"], request.form["password"]
        if USERS.get(u) == p:
            session["user"] = u
            flash(f"Welcome, {u}!", "success")
            return redirect(url_for("tickets"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/tickets")
@login_required
def tickets():
    q      = request.args.get("q", "").strip().lower()
    status = request.args.get("status", "")
    data   = list(TICKETS.values())
    if q:
        data = [t for t in data if q in t["id"].lower() or q in t["title"].lower()]
    if status:
        data = [t for t in data if t["status"] == status]
    data.sort(key=lambda t: t["created_at"], reverse=True)
    return render_template("tickets.html", tickets=data, q=q, status=status)

@app.route("/tickets/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    if request.method == "POST":
        tid = "TKT-" + str(uuid.uuid4())[:8].upper()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        TICKETS[tid] = dict(
            id=tid,
            title=request.form["title"],
            description=request.form["description"],
            priority=request.form["priority"],
            status="Open",
            category=request.form["category"],
            assignee=request.form.get("assignee", ""),
            created_at=now, updated_at=now
        )
        flash(f"Ticket {tid} created.", "success")
        return redirect(url_for("tickets"))
    return render_template("new_ticket.html")

@app.route("/tickets/<tid>")
@login_required
def ticket_detail(tid):
    t = TICKETS.get(tid)
    if not t:
        flash("Ticket not found.", "danger")
        return redirect(url_for("tickets"))
    return render_template("ticket_detail.html", ticket=t)

@app.route("/tickets/<tid>/edit", methods=["GET", "POST"])
@login_required
def edit_ticket(tid):
    t = TICKETS.get(tid)
    if not t:
        flash("Ticket not found.", "danger")
        return redirect(url_for("tickets"))
    if request.method == "POST":
        t["title"]       = request.form["title"]
        t["description"] = request.form["description"]
        t["priority"]    = request.form["priority"]
        t["status"]      = request.form["status"]
        t["category"]    = request.form["category"]
        t["assignee"]    = request.form.get("assignee", "")
        t["updated_at"]  = datetime.now().strftime("%Y-%m-%d %H:%M")
        flash(f"Ticket {tid} updated.", "success")
        return redirect(url_for("ticket_detail", tid=tid))
    return render_template("edit_ticket.html", ticket=t)

if __name__ == "__main__":
    app.run(debug=True, port=5050)
