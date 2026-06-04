# File: statistical_service.py
# Nhiệm vụ:
# - Xử lý logic thống kê nhân viên.
# - Chỉ đọc dữ liệu từ users_collection.
# - Không sửa, không xóa dữ liệu của module quản lý nhân viên.
# - Không xử lý doanh thu, tiền tệ, tài sản, cấp phát, báo cáo.

from collections import Counter

from pymongo import DESCENDING

from mongo import users_collection

from templates.statistical.statistical_model import (
    build_segments,
    build_bar_items,
    employee_serializer,
    get_role_label,
    format_number,
)


# Sắp xếp counter theo số lượng giảm dần.
# Nếu bằng số lượng thì sắp xếp theo tên tăng dần.
def sort_counter(counter):
    return dict(
        sorted(
            counter.items(),
            key=lambda item: (-item[1], str(item[0]))
        )
    )


# API service chính cho trang thống kê nhân viên.
# Dữ liệu lấy trực tiếp từ collection users.
def get_statistical_employees():
    users = list(
        users_collection
        .find({})
        .sort("created_at", DESCENDING)
    )

    total_users = len(users)

    active_users = len([
        user for user in users
        if user.get("status") == "HOAT_DONG"
    ])

    inactive_users = len([
        user for user in users
        if user.get("status") == "NGUNG_HOAT_DONG"
    ])

    role_counter = Counter(
        get_role_label(user.get("role"))
        for user in users
        if user.get("role")
    )

    dept_counter = Counter(
        user.get("department") or "Khác"
        for user in users
    )

    role_counter = sort_counter(role_counter)
    dept_counter = sort_counter(dept_counter)

    role_items = build_bar_items(role_counter)

    dept_items = build_bar_items(
        dict(list(dept_counter.items())[:6])
    )

    employee_segments = build_segments([
        {
            "label": "Đang làm",
            "value": active_users,
            "value_text": format_number(active_users),
            "color": "#22c55e",
            "class": "green",
        },
        {
            "label": "Đã nghỉ",
            "value": inactive_users,
            "value_text": format_number(inactive_users),
            "color": "#ef4444",
            "class": "red",
        },
    ])

    recent_users = [
        employee_serializer(user)
        for user in users[:8]
    ]

    return {
        "success": True,
        "message": "Lấy thống kê nhân viên thành công",
        "data": {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "employee_segments": employee_segments,
            "role_items": role_items,
            "dept_items": dept_items,
            "recent_users": recent_users,
        }
    }, 200


# Giữ route overview để frontend cũ vẫn chạy được nếu còn gọi /api/statistical/overview.
# Nhưng dữ liệu overview bây giờ cũng chính là thống kê nhân viên.
def get_statistical_overview():
    return get_statistical_employees()