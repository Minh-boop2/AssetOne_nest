# File: statistical_model.py
# File này chuẩn hóa dữ liệu thống kê trước khi trả về frontend

from datetime import timezone, timedelta


VN_TZ = timezone(timedelta(hours=7))


ROLE_LABELS = {
    "ADMIN": "Admin",
    "QUAN_LY": "Manager",
    "NHAN_VIEN": "Staff",
}


STATUS_LABELS = {
    "HOAT_DONG": "Hoạt động",
    "NGUNG_HOAT_DONG": "Đã nghỉ",
}


def format_number(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return "0"


def format_money(value):
    try:
        return f"{float(value):,.0f}".replace(",", ".") + "đ"
    except Exception:
        return "0đ"


def percent(value, total):
    if total == 0:
        return 0

    return round((value / total) * 100, 1)


def safe_bar_percent(value, max_value):
    if max_value == 0:
        return 0

    result = round((value / max_value) * 100, 1)

    return max(result, 6)


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


def format_datetime_vietnam(value):
    if not value:
        return ""

    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    vietnam_time = value.astimezone(VN_TZ)

    return vietnam_time.strftime("%d/%m/%Y %H:%M")


def get_role_label(role):
    return ROLE_LABELS.get(role, role or "Khác")


def get_status_label(status):
    return STATUS_LABELS.get(status, status or "Không rõ")


def get_status_class(status):
    if status == "HOAT_DONG":
        return "success"

    if status == "NGUNG_HOAT_DONG":
        return "danger"

    return "info"


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