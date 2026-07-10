from functools import wraps
from flask import abort
from flask_login import current_user

ROLE_ADMIN = "admin"
ROLE_SALES = "sales_executive"
ROLE_OPERATIONS = "operations_team"
ROLE_MANAGEMENT = "management_viewer"


def role():
    return getattr(current_user, "role", None) if current_user.is_authenticated else None


def is_admin():
    return role() == ROLE_ADMIN


def is_sales_executive():
    return role() in {"sales", ROLE_SALES}


def roles_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if role() not in allowed_roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def can_access_dashboard():
    return is_admin() or is_sales_executive()


def can_access_clients():
    return is_admin() or is_sales_executive()


def can_access_enquiries():
    return is_admin() or is_sales_executive()


def can_access_quotations():
    return is_admin() or is_sales_executive()


def can_access_tasks():
    return is_admin() or is_sales_executive()


# Present requirement: operations is intentionally disabled.
def can_access_shipments():
    # Admin manages all shipments.
    # Sales can read shipments linked to their assigned clients.
    return is_admin() or is_sales_executive()


def can_access_reports():
    return is_admin()


def can_manage_users():
    return is_admin()


def can_access_settings():
    return is_admin()


class TemplatePermissions:
    can_access_dashboard = staticmethod(can_access_dashboard)
    can_access_clients = staticmethod(can_access_clients)
    can_access_enquiries = staticmethod(can_access_enquiries)
    can_access_quotations = staticmethod(can_access_quotations)
    can_access_tasks = staticmethod(can_access_tasks)
    can_access_shipments = staticmethod(can_access_shipments)
    can_access_reports = staticmethod(can_access_reports)
    can_manage_users = staticmethod(can_manage_users)
    can_access_settings = staticmethod(can_access_settings)
    is_admin = staticmethod(is_admin)
    is_sales_executive = staticmethod(is_sales_executive)


permissions = TemplatePermissions()
