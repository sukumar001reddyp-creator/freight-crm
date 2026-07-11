from flask import Blueprint

portal_bp = Blueprint(
    "portal",
    __name__,
    url_prefix="/portal",
    template_folder="../templates/portal",
    static_folder="../static"
)

from app.portal import routes