from flask import Blueprint

landing_v2 = Blueprint("landing_v2", __name__)

from .database import close_database

landing_v2.teardown_app_request(close_database)

from . import routes
