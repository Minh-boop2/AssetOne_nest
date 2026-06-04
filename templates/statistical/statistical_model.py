# File: statistical_model.py
# Nhiệm vụ:
# - Chuẩn hóa dữ liệu thống kê nhân viên trước khi trả về frontend.
# - Format số lượng, phần trăm, ngày giờ.
# - Chuyển role/status trong database thành nhãn dễ đọc trên giao diện.

from datetime import timezone, timedelta


# Múi giờ Việt Nam: UTC +7
VN_TZ = timezone(timedelta(hours=7))


# Mapping role trong database sang nhãn hiển thị trên frontend
ROLE_LABELS = {
    "ADMIN": "Admin",
    "QUAN_LY": "Manager",
    "NHAN_VIEN": "Staff",
}


# Mapping trạng thái trong database sang nhãn hiển thị trên frontend
STATUS_LABELS = {
    "HOAT_DONG": "Hoạt động",
    "NGUNG_HOAT_DONG": "Đã nghỉ",
}


# Format số lượng: 1000 -> 1.000
def format_number(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return "0"


# Tính phần trăm, làm tròn 1 chữ số thập phân
def percent(value, total):
    if total == 0:
        return 0

    return round((value / total) * 100, 1)


# Tính độ dài thanh bar.
# Nếu có dữ liệu nhưng số quá nhỏ thì vẫn cho tối thiểu 6% để frontend nhìn thấy.
def safe_bar_percent(value, max_value):
    if max_value == 0:
        return 0

    result = round((value / max_value) * 100, 1)

    return max(result, 6)


# Tạo dữ liệu cho biểu đồ tròn/donut.
# Frontend dùng value, percent, from_deg, to_deg để vẽ phần trăm.
def build_segments(items):
    total = sum(item.get("value", 0) for item in items)
    current_degree = 0

    for item in items:
        value = item.get("value", 0)
        degree = (value / total) * 360 if total else 0

        item["percent"] = percent(value, total)
        item["from_deg"] = round(current_degree, 2)
        item["to_deg"] = round(current_degree + degree, 2)

        current_degree += degree

    return items


# Tạo dữ liệu cho các thanh thống kê ngang.
# Ví dụ: nhân viên theo vai trò, nhân viên theo phòng ban.
def build_bar_items(counter):
    max_value = max(counter.values()) if counter else 1

    items = []

    for label, value in counter.items():
        items.append({
            "label": label,
            "value": value,
            "value_text": format_number(value),
            "percent": safe_bar_percent(value, max_value),
        })

    return items


# Format datetime sang giờ Việt Nam dạng dd/mm/yyyy hh:mm
def format_datetime_vietnam(value):
    if not value:
        return ""

    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    vietnam_time = value.astimezone(VN_TZ)

    return vietnam_time.strftime("%d/%m/%Y %H:%M")


# Lấy label role để hiển thị
def get_role_label(role):
    return ROLE_LABELS.get(role, role or "Khác")


# Lấy label trạng thái để hiển thị
def get_status_label(status):
    return STATUS_LABELS.get(status, status or "Không rõ")


# Class trạng thái để frontend style màu sắc
def get_status_class(status):
    if status == "HOAT_DONG":
        return "success"

    if status == "NGUNG_HOAT_DONG":
        return "danger"

    return "info"


# Chuyển một user trong MongoDB thành object sạch để trả về frontend
def employee_serializer(user):
    status = user.get("status")

    return {
        "id": str(user.get("_id")) if user.get("_id") else "",
        "employee_code": user.get("employee_code") or "",
        "full_name": user.get("full_name") or "Chưa xác định",
        "email": user.get("email") or "",
        "phone": user.get("phone") or "",
        "department": user.get("department") or "Khác",
        "dept": user.get("department") or "Khác",
        "floor": user.get("floor") or "",
        "role": get_role_label(user.get("role")),
        "role_raw": user.get("role") or "",
        "status": get_status_label(status),
        "status_raw": status or "",
        "status_class": get_status_class(status),
        "created_at": format_datetime_vietnam(user.get("created_at")),
        "updated_at": format_datetime_vietnam(user.get("updated_at")),
    }