# File: activity_model.py
# File này chuẩn bị dữ liệu log hoạt động trước khi lưu và trước khi trả về frontend

from datetime import datetime, timezone, timedelta
from bson import ObjectId


# Các method này là những thao tác có thể làm thay đổi dữ liệu
VALID_ACTIVITY_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

# Múi giờ Việt Nam, lệch UTC +7 tiếng
VN_TZ = timezone(timedelta(hours=7))


# Lấy thời gian hiện tại theo giờ Việt Nam
def now_vietnam():
    return datetime.now(VN_TZ)


# Chuyển thời gian sang dạng ngày/giờ dễ đọc theo giờ Việt Nam
def format_datetime_vietnam(value):
    if not value:
        return None

    # Nếu thời gian đã là chuỗi rồi thì trả về luôn
    if isinstance(value, str):
        return value

    # Nếu datetime chưa có timezone thì xem như đang là giờ UTC
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    # Đổi thời gian sang giờ Việt Nam
    vietnam_time = value.astimezone(VN_TZ)

    return vietnam_time.strftime("%d/%m/%Y %H:%M")


# Kiểm tra id có đúng kiểu ObjectId của MongoDB hay không
def is_valid_object_id(id):
    return ObjectId.is_valid(id)


# Chuyển 1 bản ghi hoạt động trong database thành dữ liệu trả về cho frontend
def activity_serializer(activity):
    return {
        "id": str(activity["_id"]),
        "user_id": str(activity.get("user_id")) if activity.get("user_id") else None,
        "employee_code": activity.get("employee_code"),
        "full_name": activity.get("full_name"),
        "email": activity.get("email"),
        "role": activity.get("role"),

        "action": activity.get("action"),
        "module": activity.get("module"),
        "method": activity.get("method"),
        "path": activity.get("path"),
        "status_code": activity.get("status_code"),

        "target_id": activity.get("target_id"),
        "target_name": activity.get("target_name"),

        "metadata": activity.get("metadata", {}),

        "created_at": format_datetime_vietnam(activity.get("created_at")),
    }


# Tạo object log hoạt động đúng format để lưu vào MongoDB
def create_activity_model(data):
    return {
        "user_id": data.get("user_id"),
        "employee_code": data.get("employee_code"),
        "full_name": data.get("full_name"),
        "email": data.get("email"),
        "role": data.get("role"),

        "action": data.get("action"),
        "module": data.get("module"),
        "method": data.get("method"),
        "path": data.get("path"),
        "status_code": data.get("status_code"),

        "target_id": data.get("target_id"),
        "target_name": data.get("target_name"),

        "metadata": data.get("metadata", {}),

        "created_at": now_vietnam(),
    }
