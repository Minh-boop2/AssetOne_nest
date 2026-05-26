from datetime import datetime, timezone, timedelta
from bson import ObjectId
from werkzeug.security import generate_password_hash


# Danh sách role hợp lệ của user
VALID_ROLES = ["ADMIN", "QUAN_LY", "NHAN_VIEN"]

# Danh sách trạng thái hợp lệ của user
VALID_STATUS = ["HOAT_DONG", "NGUNG_HOAT_DONG"]

# Múi giờ Việt Nam UTC+7
VN_TZ = timezone(timedelta(hours=7))

# Avatar mặc định
# Hiện tại bạn đang để ảnh ở: img/default-avatar.jpg
DEFAULT_AVATAR_URL = "/static/img/default-avatar.jpg"


# Lấy thời gian hiện tại theo múi giờ Việt Nam
def now_vietnam():
    return datetime.now(VN_TZ)


# Đổi thời gian sang định dạng ngày giờ Việt Nam để hiển thị
def format_datetime_vietnam(value):
    if not value:
        return None

    if isinstance(value, str):
        return value

    # MongoDB thường trả datetime dạng UTC nhưng không có timezone
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    vietnam_time = value.astimezone(VN_TZ)

    return vietnam_time.strftime("%d/%m/%Y %H:%M")


# Chuyển dữ liệu user từ MongoDB sang dạng dễ dùng cho frontend
def user_serializer(user):
    return {
        "id": str(user["_id"]),
        "employee_code": user.get("employee_code"),
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "department": user.get("department"),
        "floor": user.get("floor"),
        "role": user.get("role"),
        "status": user.get("status"),
        "avatar_url": user.get("avatar_url") or DEFAULT_AVATAR_URL,

        # Dùng created_at làm ngày tham gia
        "created_at": format_datetime_vietnam(user.get("created_at")),
        "updated_at": format_datetime_vietnam(user.get("updated_at")),
    }


# Tạo dữ liệu user mới trước khi lưu vào database
def create_user_model(data):
    now = now_vietnam()

    return {
        "employee_code": data.get("employee_code"),
        "full_name": data.get("full_name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "department": data.get("department"),
        "floor": data.get("floor"),
        "role": data.get("role", "NHAN_VIEN"),
        "status": data.get("status", "HOAT_DONG"),
        "avatar_url": data.get("avatar_url") or DEFAULT_AVATAR_URL,
        "password_hash": generate_password_hash(data.get("password")),
        "created_at": now,
        "updated_at": now,
    }


# Tạo dữ liệu cập nhật user
# Chỉ cho phép cập nhật các field có trong allowed_fields
def update_user_model(data):
    allowed_fields = [
        "employee_code",
        "full_name",
        "email",
        "phone",
        "department",
        "floor",
        "role",
        "status",
        "avatar_url",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]

    # Mỗi lần cập nhật thì ghi lại thời gian sửa cuối cùng
    update_data["updated_at"] = now_vietnam()

    return update_data


# Kiểm tra id có phải ObjectId hợp lệ của MongoDB hay không
def is_valid_object_id(id):
    return ObjectId.is_valid(id)
