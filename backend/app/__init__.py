"""
Flask application factory for DeCOBOL.
"""

from typing import Optional, Dict, Any
from flask import Flask, jsonify
from app.config import settings
from app.api.routes import api_bp


def create_app(config_override: Optional[Dict[str, Any]] = None) -> Flask:
    """Application factory for DeCOBOL backend."""
    app = Flask(__name__)

    # Default application config
    app.config["JSON_SORT_KEYS"] = False
    app.config["FLASK_DEBUG"] = settings.flask_debug

    if config_override:
        app.config.update(config_override)

    # Enable CORS for local development
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        return response

    # Register API blueprint
    app.register_blueprint(api_bp, url_prefix="/api")

    # Root route
    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "DeCOBOL Modernization API",
            "version": "0.1.0",
            "health": "/api/health",
            "docs": "/api/tools",
        })

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app
