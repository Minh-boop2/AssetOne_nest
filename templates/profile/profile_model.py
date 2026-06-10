# File này chuẩn hóa dữ liệu hồ sơ người dùng trước khi trả về frontend
# Đồng thời chuẩn bị dữ liệu cập nhật hồ sơ trước khi lưu vào MongoDB

from templates.user.user_model import (
    DEFAULT_AVATAR_URL,
    format_datetime_vietnam,
    now_vietnam,
)


# Nhãn hiển thị tương ứng với từng role trong hệ thống
ROLE_LABELS = {
    "ADMIN": "QUẢN TRỊ HỆ THỐNG",
    "QUAN_LY": "QUẢN LÝ",
    "NHAN_VIEN": "NHÂN VIÊN",
}


# Nhãn hiển thị tương ứng với trạng thái tài khoản
STATUS_LABELS = {
    "HOAT_DONG": "Hoạt động",
    "NGUNG_HOAT_DONG": "Ngưng hoạt động",
}


# Chuẩn hóa đường dẫn avatar, nếu thiếu thì dùng avatar mặc định
def normalize_avatar_url(avatar_url):
    if not avatar_url:
        return DEFAULT_AVATAR_URL

    if avatar_url == "/static/imgages/default-avatar.jpg":
        return DEFAULT_AVATAR_URL

    return avatar_url


# Chuyển dữ liệu user trong MongoDB thành object profile trả về frontend
def profile_serializer(user):
    role = user.get("role")
    status = user.get("status")
    full_name = user.get("full_name") or "Người dùng"

    return {
        "id": str(user.get("_id")),
        "employee_code": user.get("employee_code"),
        "full_name": full_name,
        "name": full_name,
        "email": user.get("email"),
        "phone": user.get("phone"),
        "department": user.get("department"),
        "dept": user.get("department"),
        "floor": user.get("floor"),
        "role": role,
        "role_label": ROLE_LABELS.get(role, role or "NHÂN VIÊN"),
        "status": status,
        "status_label": STATUS_LABELS.get(status, status or "Không xác định"),
        "is_active": status == "HOAT_DONG",
        "avatar_url": normalize_avatar_url(user.get("avatar_url")),
        "created_at": format_datetime_vietnam(user.get("created_at")),
        "updated_at": format_datetime_vietnam(user.get("updated_at")),
    }


# Tạo dữ liệu cập nhật hồ sơ, chỉ cho phép sửa các field an toàn
def update_profile_model(data):
    allowed_fields = [
        "full_name",
        "email",
        "phone",
        "avatar_url",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in data:
            value = data.get(field)

            if isinstance(value, str):
                value = value.strip()

            if field == "avatar_url":
                value = normalize_avatar_url(value)

            update_data[field] = value

    if update_data:
        update_data["updated_at"] = now_vietnam()

    return update_data