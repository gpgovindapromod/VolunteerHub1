"""Volunteer Hub – Flask Application"""
from flask import Flask, render_template
from config import Config
from db import init_db
from auth import auth_bp
from volunteer import volunteer_bp
from organization import organization_bp
from admin import admin_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    init_db(app)
    app.register_blueprint(auth_bp,         url_prefix='/auth')
    app.register_blueprint(volunteer_bp,    url_prefix='/volunteer')
    app.register_blueprint(organization_bp, url_prefix='/organization')
    app.register_blueprint(admin_bp,        url_prefix='/admin')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app

app = create_app()
if __name__ == '__main__':
    app.run(debug=True)
