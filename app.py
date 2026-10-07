from flask import Flask, redirect, url_for

from services.landing_price_v2.routes import landing_v2


app = Flask(__name__)
app.register_blueprint(landing_v2)


@app.get("/")
def index():
    return redirect(url_for("landing_v2.calculator_page"))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
