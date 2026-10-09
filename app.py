from flask import Flask, redirect, render_template, request, url_for
from pathlib import Path
import os

from services.landing_price_v2.routes import landing_v2


app = Flask(__name__)


def load_local_env(path):
    """Load simple KEY=VALUE settings from the ignored local .env file."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


app.register_blueprint(landing_v2)


@app.get("/health")
def health_check():
    return {"ok": True}, 200


@app.before_request
def log_request_start():
    app.logger.info("Incoming request: %s %s", request.method, request.path)


@app.get("/")
def index():
    return redirect(url_for("landing_v2.calculator_page"))


@app.get("/bad-gateway")
def bad_gateway_page():
    return render_template("error_502.html", request_id="a47297ee6f067fec-CMH")


@app.errorhandler(502)
def handle_bad_gateway(error):
    return render_template("error_502.html", request_id="a47297ee6f067fec-CMH"), 502


if __name__ == "__main__":
    load_local_env(Path(__file__).with_name(".env"))
    app.run(debug=True, host="127.0.0.1", port=5000)
