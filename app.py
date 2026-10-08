from flask import Flask, redirect, render_template, request, url_for

from services.landing_price_v2.routes import landing_v2


app = Flask(__name__)
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
    app.run(debug=True, host="127.0.0.1", port=5000)
