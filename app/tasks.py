from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_login import (
    login_required,
    current_user,
)

from app import db

from app.models import (
    Client,
    ClientTask,
    User,
)


# =========================================================
# BLUEPRINT
# =========================================================

tasks_bp = Blueprint(
    "tasks",
    __name__,
    url_prefix="/tasks"
)


# =========================================================
# ALLOWED VALUES
# =========================================================

TASK_TYPES = {
    "follow_up",
    "call",
    "email",
    "meeting",
    "general",
}

TASK_PRIORITIES = {
    "low",
    "medium",
    "high",
    "urgent",
}

TASK_STATUSES = {
    "pending",
    "in_progress",
    "completed",
    "cancelled",
}


# =========================================================
# SAFE INTERNAL REDIRECT
# Prevent external redirect URLs.
# =========================================================

def is_safe_next_url(target):

    if not target:
        return False

    host_url = urlparse(
        request.host_url
    )

    redirect_url = urlparse(
        urljoin(
            request.host_url,
            target
        )
    )

    return (
        redirect_url.scheme
        in {"http", "https"}
        and host_url.netloc
        == redirect_url.netloc
    )


# =========================================================
# TASK LIST
# URL: /tasks/
# =========================================================

@tasks_bp.route("/")
@login_required
def task_list():

    status_filter = request.args.get(
        "status",
        ""
    ).strip()

    priority_filter = request.args.get(
        "priority",
        ""
    ).strip()

    type_filter = request.args.get(
        "type",
        ""
    ).strip()

    assignee_filter = request.args.get(
        "assignee",
        ""
    ).strip()


    query = db.select(
        ClientTask
    )


    # -----------------------------------------
    # FILTER: STATUS
    # -----------------------------------------

    if status_filter in TASK_STATUSES:

        query = query.where(
            ClientTask.status
            == status_filter
        )


    # -----------------------------------------
    # FILTER: PRIORITY
    # -----------------------------------------

    if priority_filter in TASK_PRIORITIES:

        query = query.where(
            ClientTask.priority
            == priority_filter
        )


    # -----------------------------------------
    # FILTER: TYPE
    # -----------------------------------------

    if type_filter in TASK_TYPES:

        query = query.where(
            ClientTask.task_type
            == type_filter
        )


    # -----------------------------------------
    # FILTER: ASSIGNEE
    # -----------------------------------------

    if assignee_filter.isdigit():

        query = query.where(
            ClientTask.assigned_to_id
            == int(assignee_filter)
        )


    # -----------------------------------------
    # ORDER
    # -----------------------------------------

    query = query.order_by(
        ClientTask.due_date.asc(),
        ClientTask.created_at.desc()
    )


    tasks = (
        db.session.execute(query)
        .scalars()
        .all()
    )


    users = (
        db.session.execute(
            db.select(User)
            .order_by(
                User.full_name.asc()
            )
        )
        .scalars()
        .all()
    )


    # SQLite commonly returns stored DateTime
    # values as offset-naive datetimes.
    now = datetime.now()


    return render_template(
        "tasks/list.html",
        tasks=tasks,
        users=users,
        now=now,
        status_filter=status_filter,
        priority_filter=priority_filter,
        type_filter=type_filter,
        assignee_filter=assignee_filter,
    )


# =========================================================
# CREATE TASK / FOLLOW-UP
# URL: /tasks/create
# =========================================================

@tasks_bp.route(
    "/create",
    methods=["GET", "POST"]
)
@login_required
def create_task():

    clients = (
        db.session.execute(
            db.select(Client)
            .where(
                Client.is_archived.is_(False)
            )
            .order_by(
                Client.company_name.asc()
            )
        )
        .scalars()
        .all()
    )


    users = (
        db.session.execute(
            db.select(User)
            .order_by(
                User.full_name.asc()
            )
        )
        .scalars()
        .all()
    )


    # -----------------------------------------
    # OPTIONAL PRESELECTED CLIENT
    # Example:
    # /tasks/create?client_id=5
    # -----------------------------------------

    selected_client_id = request.args.get(
        "client_id",
        type=int
    )


    if request.method == "POST":

        # -------------------------------------
        # READ FORM
        # -------------------------------------

        client_id = request.form.get(
            "client_id",
            type=int
        )

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        task_type = request.form.get(
            "task_type",
            "follow_up"
        ).strip()

        due_date_raw = request.form.get(
            "due_date",
            ""
        ).strip()

        assigned_to_id = request.form.get(
            "assigned_to_id",
            type=int
        )

        priority = request.form.get(
            "priority",
            "medium"
        ).strip()


        # -------------------------------------
        # VALIDATION: CLIENT
        # -------------------------------------

        if not client_id:

            flash(
                "Please select a client.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=selected_client_id,
            )


        client = db.session.get(
            Client,
            client_id
        )


        if not client:

            flash(
                "Selected client was not found.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=selected_client_id,
            )


        # -------------------------------------
        # VALIDATION: TITLE
        # -------------------------------------

        if not title:

            flash(
                "Task title is required.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=client_id,
            )


        # -------------------------------------
        # VALIDATION: TYPE
        # -------------------------------------

        if task_type not in TASK_TYPES:

            flash(
                "Invalid task type.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=client_id,
            )


        # -------------------------------------
        # VALIDATION: PRIORITY
        # -------------------------------------

        if priority not in TASK_PRIORITIES:

            flash(
                "Invalid priority.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=client_id,
            )


        # -------------------------------------
        # VALIDATION: ASSIGNEE
        # -------------------------------------

        if not assigned_to_id:

            flash(
                "Please select an assignee.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=client_id,
            )


        assigned_user = db.session.get(
            User,
            assigned_to_id
        )


        if not assigned_user:

            flash(
                "Selected assignee was not found.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=client_id,
            )


        # -------------------------------------
        # PARSE DUE DATE
        # -------------------------------------

        try:

            due_date = datetime.fromisoformat(
                due_date_raw
            )

            due_date = due_date.replace(
                tzinfo=timezone.utc
            )

        except (TypeError, ValueError):

            flash(
                "Please enter a valid due date and time.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=client_id,
            )


        # -------------------------------------
        # CREATE TASK
        # -------------------------------------

        task = ClientTask(
            client_id=client.id,
            title=title,
            description=description or None,
            task_type=task_type,
            due_date=due_date,
            assigned_to_id=assigned_user.id,
            priority=priority,
            status="pending",
            created_by_id=current_user.id,
        )


        # -------------------------------------
        # SAVE
        # -------------------------------------

        try:

            db.session.add(task)
            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print(
                "TASK CREATE ERROR:",
                repr(e),
                flush=True
            )

            flash(
                "Unable to create task. Please try again.",
                "danger"
            )

            return render_template(
                "tasks/create.html",
                clients=clients,
                users=users,
                selected_client_id=client_id,
            )


        flash(
            "Task created successfully.",
            "success"
        )

        return redirect(
            url_for("tasks.task_list")
        )


    return render_template(
        "tasks/create.html",
        clients=clients,
        users=users,
        selected_client_id=selected_client_id,
    )


# =========================================================
# START TASK
# URL: /tasks/<task_id>/start
# =========================================================

@tasks_bp.route(
    "/<int:task_id>/start",
    methods=["POST"]
)
@login_required
def start_task(task_id):

    task = db.get_or_404(
        ClientTask,
        task_id
    )


    if task.status != "pending":

        flash(
            "Only pending tasks can be started.",
            "warning"
        )

        return redirect(
            url_for("tasks.task_list")
        )


    try:

        task.status = "in_progress"

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            "TASK START ERROR:",
            repr(e),
            flush=True
        )

        flash(
            "Unable to start task.",
            "danger"
        )

        return redirect(
            url_for("tasks.task_list")
        )


    flash(
        "Task moved to In Progress.",
        "success"
    )

    return redirect(
        url_for("tasks.task_list")
    )


# =========================================================
# COMPLETE TASK
# URL: /tasks/<task_id>/complete
# =========================================================

@tasks_bp.route(
    "/<int:task_id>/complete",
    methods=["POST"]
)
@login_required
def complete_task(task_id):

    task = db.get_or_404(
        ClientTask,
        task_id
    )


    if task.status not in {
        "pending",
        "in_progress",
    }:

        flash(
            "This task cannot be completed.",
            "warning"
        )

        return redirect(
            url_for("tasks.task_list")
        )


    try:

        task.status = "completed"

        task.completed_at = datetime.now(
            timezone.utc
        )

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            "TASK COMPLETE ERROR:",
            repr(e),
            flush=True
        )

        flash(
            "Unable to complete task.",
            "danger"
        )

        return redirect(
            url_for("tasks.task_list")
        )


    flash(
        "Task completed successfully.",
        "success"
    )

    return redirect(
        url_for("tasks.task_list")
    )


# =========================================================
# EDIT TASK
# URL: /tasks/<task_id>/edit
# =========================================================

@tasks_bp.route(
    "/<int:task_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_task(task_id):

    task = db.get_or_404(
        ClientTask,
        task_id
    )


    # -----------------------------------------
    # RETURN DESTINATION
    #
    # Client page nunchi edit chesthe:
    #   /clients/5#tasks
    #
    # Global Tasks nunchi edit chesthe:
    #   empty -> /tasks/
    # -----------------------------------------

    next_url = request.args.get(
        "next",
        ""
    ).strip()


    # -----------------------------------------
    # LOCK FINISHED TASKS
    # -----------------------------------------

    if task.status in {
        "completed",
        "cancelled",
    }:

        flash(
            "Completed or cancelled tasks cannot be edited.",
            "warning"
        )

        if is_safe_next_url(next_url):
            return redirect(next_url)

        return redirect(
            url_for("tasks.task_list")
        )


    # -----------------------------------------
    # LOAD CLIENTS
    # -----------------------------------------

    clients = (
        db.session.execute(
            db.select(Client)
            .where(
                Client.is_archived.is_(False)
            )
            .order_by(
                Client.company_name.asc()
            )
        )
        .scalars()
        .all()
    )


    # -----------------------------------------
    # LOAD USERS
    # -----------------------------------------

    users = (
        db.session.execute(
            db.select(User)
            .order_by(
                User.full_name.asc()
            )
        )
        .scalars()
        .all()
    )


    # -----------------------------------------
    # POST: UPDATE TASK
    # -----------------------------------------

    if request.method == "POST":

        client_id = request.form.get(
            "client_id",
            type=int
        )

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        task_type = request.form.get(
            "task_type",
            ""
        ).strip()

        due_date_raw = request.form.get(
            "due_date",
            ""
        ).strip()

        assigned_to_id = request.form.get(
            "assigned_to_id",
            type=int
        )

        priority = request.form.get(
            "priority",
            ""
        ).strip()


        # -------------------------------------
        # FIND CLIENT / USER
        # -------------------------------------

        client = (
            db.session.get(
                Client,
                client_id
            )
            if client_id
            else None
        )


        assigned_user = (
            db.session.get(
                User,
                assigned_to_id
            )
            if assigned_to_id
            else None
        )


        # -------------------------------------
        # VALIDATION: CLIENT
        # -------------------------------------

        if not client:

            flash(
                "Please select a valid client.",
                "danger"
            )

            return render_template(
                "tasks/edit.html",
                task=task,
                clients=clients,
                users=users,
                next_url=next_url,
            )


        # -------------------------------------
        # VALIDATION: TITLE
        # -------------------------------------

        if not title:

            flash(
                "Task title is required.",
                "danger"
            )

            return render_template(
                "tasks/edit.html",
                task=task,
                clients=clients,
                users=users,
                next_url=next_url,
            )


        # -------------------------------------
        # VALIDATION: TYPE
        # -------------------------------------

        if task_type not in TASK_TYPES:

            flash(
                "Invalid task type.",
                "danger"
            )

            return render_template(
                "tasks/edit.html",
                task=task,
                clients=clients,
                users=users,
                next_url=next_url,
            )


        # -------------------------------------
        # VALIDATION: PRIORITY
        # -------------------------------------

        if priority not in TASK_PRIORITIES:

            flash(
                "Invalid priority.",
                "danger"
            )

            return render_template(
                "tasks/edit.html",
                task=task,
                clients=clients,
                users=users,
                next_url=next_url,
            )


        # -------------------------------------
        # VALIDATION: ASSIGNEE
        # -------------------------------------

        if not assigned_user:

            flash(
                "Please select a valid assignee.",
                "danger"
            )

            return render_template(
                "tasks/edit.html",
                task=task,
                clients=clients,
                users=users,
                next_url=next_url,
            )


        # -------------------------------------
        # PARSE DUE DATE
        # -------------------------------------

        try:

            due_date = datetime.fromisoformat(
                due_date_raw
            )

            due_date = due_date.replace(
                tzinfo=timezone.utc
            )

        except (TypeError, ValueError):

            flash(
                "Please enter a valid due date and time.",
                "danger"
            )

            return render_template(
                "tasks/edit.html",
                task=task,
                clients=clients,
                users=users,
                next_url=next_url,
            )


        # -------------------------------------
        # UPDATE
        # -------------------------------------

        try:

            task.client_id = client.id
            task.title = title
            task.description = (
                description or None
            )
            task.task_type = task_type
            task.due_date = due_date
            task.assigned_to_id = (
                assigned_user.id
            )
            task.priority = priority

            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print(
                "TASK EDIT ERROR:",
                repr(e),
                flush=True
            )

            flash(
                "Unable to update task.",
                "danger"
            )

            return render_template(
                "tasks/edit.html",
                task=task,
                clients=clients,
                users=users,
                next_url=next_url,
            )


        flash(
            "Task updated successfully.",
            "success"
        )


        # -------------------------------------
        # RETURN TO ORIGINAL PAGE
        # -------------------------------------

        if is_safe_next_url(next_url):
            return redirect(next_url)

        return redirect(
            url_for("tasks.task_list")
        )


    # -----------------------------------------
    # GET: SHOW EDIT PAGE
    # -----------------------------------------

    return render_template(
        "tasks/edit.html",
        task=task,
        clients=clients,
        users=users,
        next_url=next_url,
    )


# =========================================================
# CANCEL TASK
# URL: /tasks/<task_id>/cancel
# =========================================================

@tasks_bp.route(
    "/<int:task_id>/cancel",
    methods=["POST"]
)
@login_required
def cancel_task(task_id):

    task = db.get_or_404(
        ClientTask,
        task_id
    )


    if task.status not in {
        "pending",
        "in_progress",
    }:

        flash(
            "This task cannot be cancelled.",
            "warning"
        )

        return redirect(
            url_for("tasks.task_list")
        )


    try:

        task.status = "cancelled"
        task.completed_at = None

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            "TASK CANCEL ERROR:",
            repr(e),
            flush=True
        )

        flash(
            "Unable to cancel task.",
            "danger"
        )

        return redirect(
            url_for("tasks.task_list")
        )


    flash(
        "Task cancelled successfully.",
        "success"
    )

    return redirect(
        url_for("tasks.task_list")
    )