# File: statistical_service.py
# File này xử lý logic thống kê
# Chỉ đọc dữ liệu từ users_collection, không sửa dữ liệu module khác

from collections import Counter

from pymongo import DESCENDING

from mongo import users_collection

from templates.statistical.statistical_model import (
    build_segments,
    build_bar_items,
    employee_serializer,
    get_role_label,
    format_number,
    format_money,
)


def sort_counter(counter):
    return dict(
        sorted(
            counter.items(),
            key=lambda item: (-item[1], str(item[0]))
        )
    )


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


def get_statistical_overview():
    finance_summary = {
        "total_revenue_text": format_money(0),
        "total_cost_text": format_money(0),
        "total_profit_text": format_money(0),
        "total_loss_text": format_money(0),
        "total_orders_text": format_number(0),
    }

    finance_cards = [
        {
            "title": "Doanh thu",
            "value": finance_summary["total_revenue_text"],
            "icon": "💰",
            "class": "purple",
            "desc": "Tổng tiền thu được trong hệ thống",
        },
        {
            "title": "Chi phí",
            "value": finance_summary["total_cost_text"],
            "icon": "💳",
            "class": "cyan",
            "desc": "Tổng chi phí vận hành và xử lý",
        },
        {
            "title": "Tiền lời",
            "value": finance_summary["total_profit_text"],
            "icon": "📈",
            "class": "green",
            "desc": "Lợi nhuận sau khi trừ chi phí",
        },
        {
            "title": "Tiền lỗ",
            "value": finance_summary["total_loss_text"],
            "icon": "📉",
            "class": "orange",
            "desc": "Tổn thất phát sinh trong hệ thống",
        },
    ]

    finance_segments = build_segments([
        {
            "label": "Doanh thu",
            "value": 0,
            "value_text": format_money(0),
            "color": "#8b5cf6",
            "class": "purple",
        },
        {
            "label": "Chi phí",
            "value": 0,
            "value_text": format_money(0),
            "color": "#06b6d4",
            "class": "cyan",
        },
        {
            "label": "Tiền lời",
            "value": 0,
            "value_text": format_money(0),
            "color": "#22c55e",
            "class": "green",
        },
        {
            "label": "Tiền lỗ",
            "value": 0,
            "value_text": format_money(0),
            "color": "#f97316",
            "class": "orange",
        },
    ])

    return {
        "success": True,
        "message": "Lấy thống kê tổng quan thành công",
        "data": {
            "finance_summary": finance_summary,
            "finance_months": [],
            "finance_cards": finance_cards,
            "finance_segments": finance_segments,
            "revenue_sources": [],
            "expense_categories": [],
            "financial_reports": [],
            "total_revenue_text": finance_summary["total_revenue_text"],
            "total_cost_text": finance_summary["total_cost_text"],
            "total_profit_text": finance_summary["total_profit_text"],
            "total_loss_text": finance_summary["total_loss_text"],
            "total_orders_text": finance_summary["total_orders_text"],
        }
    }, 200


def get_statistical_assets():
    return {
        "success": True,
        "message": "Chưa cấu hình thống kê tài sản",
        "data": {
            "total_assets": 0,
            "type_items": [],
            "status_segments": [],
            "recent_assets": [],
            "damaged_assets": [],
            "total_damaged": 0,
            "total_repair_cost": 0,
            "total_repair_cost_text": "0đ",
            "repair_level_items": [],
            "repair_status_segments": [],
        }
    }, 200


def get_statistical_assign():
    return {
        "success": True,
        "message": "Chưa cấu hình thống kê cấp phát",
        "data": {
            "assign_total": 0,
            "status_segments": [],
            "dept_items": [],
            "location_items": [],
        }
    }, 200


def get_statistical_report():
    return {
        "success": True,
        "message": "Chưa cấu hình thống kê báo cáo",
        "data": {
            "report_total": 0,
            "log_items": [],
            "status_items": [],
            "log_segments": [],
            "recent_logs": [],
        }
    }, 200