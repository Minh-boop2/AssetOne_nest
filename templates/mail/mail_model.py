import re
from datetime import datetime, timedelta


# Thời gian hiệu lực của link đặt lại mật khẩu, tính bằng phút
RESET_TOKEN_EXPIRE_MINUTES = 15


# Đưa email về dạng thống nhất:
# bỏ khoảng trắng đầu cuối và đổi thành chữ thường
def normalize_email(email):
    if not email:
        return ""

    return str(email).strip().lower()


# Kiểm tra email có đúng định dạng cơ bản hay không
def is_valid_email(email):
    if not email:
        return False

    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return re.match(pattern, email) is not None


# Kiểm tra dữ liệu khi người dùng yêu cầu quên mật khẩu
def validate_forgot_password_data(data):
    if data is None:
        data = {}

    email = normalize_email(data.get("email"))

    if not email:
        return False, "Vui lòng nhập Gmail", None

    if not is_valid_email(email):
        return False, "Gmail không đúng định dạng", None

    return True, "", {
        "email": email
    }


# Kiểm tra dữ liệu khi người dùng đặt lại mật khẩu mới
def validate_reset_password_data(data):
    if data is None:
        data = {}

    token = str(data.get("token", "")).strip()
    password = str(data.get("password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()

    if not token:
        return False, "Link đặt lại mật khẩu không hợp lệ", None

    if not password:
        return False, "Vui lòng nhập mật khẩu mới", None

    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự", None

    if confirm_password and password != confirm_password:
        return False, "Mật khẩu xác nhận không khớp", None

    return True, "", {
        "token": token,
        "password": password
    }


# Tạo dữ liệu token đặt lại mật khẩu để lưu vào user
# Bao gồm token, thời gian hết hạn và thời gian tạo token
def create_reset_token_model(token):
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

    return {
        "reset_password_token": token,
        "reset_password_expires_at": expires_at,
        "reset_password_created_at": now
    }


# Kiểm tra token đặt lại mật khẩu đã hết hạn hay chưa
def is_reset_token_expired(expires_at):
    if not expires_at:
        return True

    return expires_at < datetime.utcnow()


# Tạo response thành công theo format chung
def success_response(message, data=None):
    response = {
        "success": True,
        "message": message
    }

    if data is not None:
        response["data"] = data

    return response


# Tạo response lỗi theo format chung
def error_response(message):
    return {
        "success": False,
        "message": message
    }