from flask import Flask
from config import Config
from database import init_db
from routes.auth import auth_bp
from routes.lecturer import lecturer_bp
from routes.student import student_bp
from routes.reports import reports_bp, admin_bp

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(lecturer_bp)
app.register_blueprint(student_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(admin_bp)

# Initialise database on first run
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
