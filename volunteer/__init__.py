from flask import Blueprint
volunteer_bp = Blueprint('volunteer', __name__, template_folder='../templates/volunteer')
from volunteer import routes  # noqa
