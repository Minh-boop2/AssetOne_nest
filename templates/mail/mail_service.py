import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from werkzeug.security import generate_password_hash

from mongo import users_collection

from templates.mail.mail_model import (
    validate_forgot_password_data,
    validate_reset_password_data,
    create_reset_token_model,
    is_reset_token_expired,
    success_response,
    error_response,
)


# Lấy thông tin Gmail và mật khẩu ứng dụng từ biến môi trường
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_APP_PASSWORD = os.getenv("MAIL_APP_PASSWORD")

# Link frontend dùng để tạo đường dẫn reset password gửi qua Gmail
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5000")


# Lấy cấu hình Gmail từ file .env
# Nếu App Password có khoảng trắng thì tự động bỏ khoảng trắng
def get_mail_config():
    username = os.getenv("MAIL_USERNAME")
    app_password = os.getenv("MAIL_APP_PASSWORD")

    if app_password:
        app_password = app_password.replace(" ", "")

    return username, app_password


# Gửi email chứa link đặt lại mật khẩu cho người dùng
def send_reset_password_email(to_email, reset_link):
    mail_username, mail_app_password = get_mail_config()

    if not mail_username or not mail_app_password:
        return False, "Chưa cấu hình MAIL_USERNAME hoặc MAIL_APP_PASSWORD trong file .env"

    subject = "Đặt lại mật khẩu AssetOne"

    html_body = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #111827;">
      <h2 style="color: #1f4fa3;">Đặt lại mật khẩu AssetOne</h2>

      <p>Xin chào,</p>

      <p>Bạn vừa yêu cầu đặt lại mật khẩu cho hệ thống AssetOne.</p>

      <p>Vui lòng bấm vào nút bên dưới để tạo mật khẩu mới:</p>

      <p style="margin: 24px 0;">
        <a
          href="{reset_link}"
          style="
            display: inline-block;
            padding: 12px 20px;
            background: #1f4fa3;
            color: #ffffff;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 700;
          "
        >
          Đặt lại mật khẩu
        </a>
      </p>

      <p>Nếu nút không hoạt động, bạn copy link này và dán vào trình duyệt:</p>

      <p style="word-break: break-all;">
        <a href="{reset_link}">{reset_link}</a>
      </p>

      <p>Link này có hiệu lực trong 15 phút.</p>

      <p>Nếu bạn không yêu cầu thao tác này, vui lòng bỏ qua email.</p>

      <p>Trân trọng,<br/>AssetOne System</p>
    </div>
    """

    text_body = f"""
Xin chào,

Bạn vừa yêu cầu đặt lại mật khẩu cho hệ thống AssetOne.

Vui lòng bấm vào link bên dưới để đặt lại mật khẩu:
{reset_link}

Link này có hiệu lực trong 15 phút.

Nếu bạn không yêu cầu thao tác này, vui lòng bỏ qua email.

Trân trọng,
AssetOne System
"""

    message = MIMEMultipart("alternative")
    message["From"] = mail_username
    message["To"] = to_email
    message["Subject"] = subject

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(mail_username, mail_app_password)
        server.sendmail(mail_username, to_email, message.as_string())
        server.quit()

        return True, "Đã gửi email đặt lại mật khẩu"

    except smtplib.SMTPAuthenticationError:
        return False, "Gmail hoặc App Password không đúng"

    except Exception as error:
        return False, f"Lỗi gửi Gmail: {str(error)}"


# Xử lý yêu cầu quên mật khẩu
# Kiểm tra Gmail, tạo token, lưu token vào user và gửi link reset qua Gmail
def request_forgot_password(data):
    is_valid, message, valid_data = validate_forgot_password_data(data)

    if not is_valid:
        return error_response(message), 400

    email = valid_data["email"]

    user = users_collection.find_one({
        "email": email
    })

    if not user:
        return error_response("Gmail không tồn tại trong hệ thống"), 404

    if user.get("status") == "NGUNG_HOAT_DONG":
        return error_response("Tài khoản đã ngưng hoạt động"), 403

    token = secrets.token_urlsafe(32)
    token_data = create_reset_token_model(token)

    users_collection.update_one(
        {
            "_id": user["_id"]
        },
        {
            "$set": token_data
        }
    )

    reset_link = f"{FRONTEND_BASE_URL}/reset-password/{token}"

    mail_success, mail_message = send_reset_password_email(email, reset_link)

    if not mail_success:
        return error_response(mail_message), 500

    return success_response(
        "Đã gửi link đặt lại mật khẩu qua Gmail",
        {
            "email": email
        }
    ), 200


# Kiểm tra token reset password có tồn tại và còn hạn hay không
def verify_reset_password_token(token):
    if not token:
        return error_response("Link đặt lại mật khẩu không hợp lệ"), 400

    user = users_collection.find_one({
        "reset_password_token": token
    })

    if not user:
        return error_response("Link đặt lại mật khẩu không hợp lệ"), 400

    expires_at = user.get("reset_password_expires_at")

    if is_reset_token_expired(expires_at):
        return error_response("Link đặt lại mật khẩu đã hết hạn"), 400

    return success_response("Token hợp lệ"), 200


# Đặt lại mật khẩu mới cho người dùng
# Sau khi đổi mật khẩu sẽ xóa token reset để không dùng lại được
def reset_password(data):
    is_valid, message, valid_data = validate_reset_password_data(data)

    if not is_valid:
        return error_response(message), 400

    token = valid_data["token"]
    password = valid_data["password"]

    user = users_collection.find_one({
        "reset_password_token": token
    })

    if not user:
        return error_response("Link đặt lại mật khẩu không hợp lệ"), 400

    expires_at = user.get("reset_password_expires_at")

    if is_reset_token_expired(expires_at):
        return error_response("Link đặt lại mật khẩu đã hết hạn"), 400

    users_collection.update_one(
        {
            "_id": user["_id"]
        },
        {
            "$set": {
                "password_hash": generate_password_hash(password)
            },
            "$unset": {
                "reset_password_token": "",
                "reset_password_expires_at": "",
                "reset_password_created_at": ""
            }
        }
    )

    return success_response("Đặt lại mật khẩu thành công"), 200