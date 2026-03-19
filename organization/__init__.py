from flask import Blueprint
organization_bp = Blueprint('organization', __name__, template_folder='../templates/organization')
from organization import routes  # noqa
