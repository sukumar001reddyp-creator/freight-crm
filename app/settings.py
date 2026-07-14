from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

# url_for_security తీసేసి క్లీన్‌గా ఇలా డిక్లేర్ చెయ్యి బ్రో
settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
@login_required
def index():
    if current_user.role != "admin":
        abort(403)
        
    return render_template('settings/index.html')