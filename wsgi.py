"""
WSGI entrypoint for Gunicorn / Production deployment.
Zemicon Landing Cost Calculator
"""
from app import app

if __name__ == "__main__":
    app.run()
