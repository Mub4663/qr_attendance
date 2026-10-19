import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'qr_attendance_secret_2024'
    DATABASE = os.path.join(BASE_DIR, 'database', 'attendance.db')
    QR_FOLDER = os.path.join(BASE_DIR, 'static', 'qrcodes')
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    QR_EXPIRY_MINUTES = 15   # QR code expires after 15 minutes
