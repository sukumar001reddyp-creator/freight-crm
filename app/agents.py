from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import Agent

agents_bp = Blueprint("agents", __name__, url_prefix="/agents")

@agents_bp.route("/")
@login_required
def agent_list():
    agents = Agent.query.order_by(Agent.country.asc(), Agent.name.asc()).all()
    return render_template("agents/list.html", agents=agents)

@agents_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_agent():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        country = request.form.get("country", "").strip()

        if not name or not email or not country:
            flash("Please fill in all required fields.", "danger")
            return render_template("agents/add.html")

        agent = Agent(name=name, email=email, country=country)
        db.session.add(agent)
        try:
            db.session.commit()
            flash(f"Agent {name} added successfully.", "success")
            return redirect(url_for("agents.agent_list"))
        except Exception:
            db.session.rollback()
            flash("Unable to add agent. Please try again.", "danger")

    return render_template("agents/add.html")