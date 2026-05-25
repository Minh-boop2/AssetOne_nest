from bson import ObjectId
from pymongo import DESCENDING
import unicodedata
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from mongo import activities_collection, users_collection

from templates.activity.activity_model import (
    activity_serializer,
    create_activity_model,
    is_valid_object_id,
)


ROLES_CAN_VIEW_ALL = ["ADMIN", "QUAN_LY"]
ROLE_EMPLOYEE = "NHAN_VIEN"

DEFAULT_ACTIVITY_LIMIT = 10

ACTIVITY_TYPE_OPTIONS = [
    "Báo cáo",
    "Cấp phát",
    "Thu hồi",
    "Tài sản",
    "Người dùng",
    "Phân quyền",
    "Mail",
    "Hoạt động",
    "Hệ thống",
]


def get_current_user_by_id(user_id):
    if not user_id:
        return None

    if not is_valid_object_id(user_id):
        return None

    return users_collection.find_one({"_id": ObjectId(user_id)})


def can_view_all_activities(role):
    return role in ROLES_CAN_VIEW_ALL


def normalize_text(value):
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")

    return text


def clean_metadata(data):
    if not isinstance(data, dict):
        return {}

    hidden_fields = [
        "password",
        "password_hash",
        "confirm_password",
        "token",
        "access_token",
        "refresh_token",
    ]

    cleaned = {}

    for key, value in data.items():
        if key in hidden_fields:
            cleaned[key] = "***"
        else:
            cleaned[key] = value

    return cleaned


def detect_module_from_path(path):
    if not path:
        return "system"

    parts = [part for part in path.split("/") if part]

    if len(parts) >= 2 and parts[0] == "api":
        return parts[1]

    if len(parts) >= 1:
        return parts[0]

    return "system"


def build_action_from_request(method, path):
    module = detect_module_from_path(path)
    method = method.upper()

    module_name_map = {
        "assets": "tài sản",
        "assign": "cấp phát",
        "users": "người dùng",
        "mail": "mail",
        "permissions": "phân quyền",
        "reports": "báo cáo",
        "activities": "hoạt động",
        "system": "hệ thống",
    }

    module_name = module_name_map.get(module, module)

    if method == "POST":
        return f"Tạo mới dữ liệu {module_name}"

    if method in ["PUT", "PATCH"]:
        return f"Cập nhật dữ liệu {module_name}"

    if method == "DELETE":
        return f"Xóa dữ liệu {module_name}"

    return f"Thao tác với dữ liệu {module_name}"


def create_activity_log(
    user_id,
    action,
    module=None,
    method=None,
    path=None,
    status_code=None,
    target_id=None,
    target_name=None,
    metadata=None,
):
    current_user = get_current_user_by_id(user_id)

    if not current_user:
        return {
            "success": False,
            "message": "Không tìm thấy user tạo log"
        }, 404

    if not action:
        return {
            "success": False,
            "message": "Thiếu nội dung hoạt động"
        }, 400

    activity_data = {
        "user_id": current_user["_id"],
        "employee_code": current_user.get("employee_code"),
        "full_name": current_user.get("full_name"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),

        "action": action,
        "module": module,
        "method": method,
        "path": path,
        "status_code": status_code,

        "target_id": target_id,
        "target_name": target_name,

        "metadata": metadata or {},
    }

    activity = create_activity_model(activity_data)

    result = activities_collection.insert_one(activity)

    created_activity = activities_collection.find_one({"_id": result.inserted_id})

    return {
        "success": True,
        "message": "Tạo log hoạt động thành công",
        "data": activity_serializer(created_activity)
    }, 201


def make_regex_condition(fields, patterns):
    conditions = []

    for field in fields:
        for pattern in patterns:
            conditions.append({
                field: {
                    "$regex": pattern,
                    "$options": "i"
                }
            })

    if not conditions:
        return {}

    return {
        "$or": conditions
    }


def build_activity_type_condition(activity_type):
    if not activity_type or activity_type == "Tất cả":
        return {}

    normalized = normalize_text(activity_type)

    action_fields = [
        "action",
        "target_name",
    ]

    general_fields = [
        "action",
        "module",
        "path",
        "target_name",
    ]

    if "bao cao" in normalized or "report" in normalized:
        return make_regex_condition(general_fields, [
            "báo cáo",
            "bao cao",
            "report",
            "reports",
        ])

    if "thu hoi" in normalized or "recover" in normalized or "recall" in normalized:
        return make_regex_condition(action_fields, [
            "thu hồi",
            "thu hoi",
            "recover",
            "recall",
            "return",
        ])

    if "cap phat" in normalized or "assign" in normalized:
        return {
            "$and": [
                make_regex_condition(action_fields, [
                    "cấp phát",
                    "cap phat",
                    "assign",
                    "assignment",
                ]),
                {
                    "action": {
                        "$not": {
                            "$regex": "thu hồi|thu hoi|recover|recall|return",
                            "$options": "i"
                        }
                    }
                },
                {
                    "target_name": {
                        "$not": {
                            "$regex": "thu hồi|thu hoi|recover|recall|return",
                            "$options": "i"
                        }
                    }
                }
            ]
        }

    if "tai san" in normalized or "asset" in normalized:
        return {
            "$and": [
                make_regex_condition(general_fields, [
                    "tài sản",
                    "tai san",
                    "asset",
                    "assets",
                ]),
                {
                    "action": {
                        "$not": {
                            "$regex": "cấp phát|cap phat|thu hồi|thu hoi|assign|recover|recall|return",
                            "$options": "i"
                        }
                    }
                }
            ]
        }

    if "nguoi dung" in normalized or "user" in normalized:
        return make_regex_condition(general_fields, [
            "người dùng",
            "nguoi dung",
            "user",
            "users",
        ])

    if "phan quyen" in normalized or "permission" in normalized:
        return make_regex_condition(general_fields, [
            "phân quyền",
            "phan quyen",
            "permission",
            "permissions",
        ])

    if "mail" in normalized or "email" in normalized:
        return make_regex_condition(general_fields, [
            "mail",
            "email",
        ])

    if "hoat dong" in normalized or "activity" in normalized:
        return make_regex_condition(general_fields, [
            "hoạt động",
            "hoat dong",
            "activity",
            "activities",
        ])

    if "he thong" in normalized or "system" in normalized:
        return make_regex_condition(general_fields, [
            "hệ thống",
            "he thong",
            "system",
        ])

    return make_regex_condition(general_fields, [activity_type])


def merge_query(base_query, extra_condition):
    if not extra_condition:
        return base_query

    if not base_query:
        return extra_condition

    return {
        "$and": [
            base_query,
            extra_condition,
        ]
    }


def build_permission_query(current_user, args):
    query = {}
    current_role = current_user.get("role")

    user_id = args.get("user_id")
    role = args.get("role")
    employee_code = args.get("employee_code")

    if can_view_all_activities(current_role):
        if user_id:
            if not is_valid_object_id(user_id):
                return None, {
                    "success": False,
                    "message": "user_id không hợp lệ"
                }, 400

            query["user_id"] = ObjectId(user_id)

        if role:
            query["role"] = role

        if employee_code:
            query["employee_code"] = employee_code

    else:
        query["user_id"] = current_user["_id"]

    return query, None, None


def build_activity_query(args, current_user):
    permission_query, error_response, error_status = build_permission_query(current_user, args)

    if error_response:
        return None, error_response, error_status

    query = dict(permission_query)

    keyword = (
        args.get("keyword")
        or args.get("search")
        or args.get("q")
    )

    activity_type = (
        args.get("type")
        or args.get("activity_type")
        or args.get("loai")
    )

    user_name = (
        args.get("user_name")
        or args.get("full_name")
        or args.get("name")
        or args.get("ten_nguoi_dung")
    )

    module = args.get("module")
    action = args.get("action")
    status_code = args.get("status_code")

    extra_conditions = []

    if module and module != "Tất cả":
        query["module"] = {
            "$regex": module,
            "$options": "i"
        }

    if action and action != "Tất cả":
        query["action"] = {
            "$regex": action,
            "$options": "i"
        }

    if status_code and status_code != "Tất cả":
        try:
            query["status_code"] = int(status_code)
        except Exception:
            query["status_code"] = status_code

    if user_name and user_name != "Tất cả":
        query["full_name"] = {
            "$regex": user_name,
            "$options": "i"
        }

    type_condition = build_activity_type_condition(activity_type)

    if type_condition:
        extra_conditions.append(type_condition)

    if keyword:
        extra_conditions.append({
            "$or": [
                {"employee_code": {"$regex": keyword, "$options": "i"}},
                {"full_name": {"$regex": keyword, "$options": "i"}},
                {"email": {"$regex": keyword, "$options": "i"}},
                {"role": {"$regex": keyword, "$options": "i"}},
                {"action": {"$regex": keyword, "$options": "i"}},
                {"module": {"$regex": keyword, "$options": "i"}},
                {"target_name": {"$regex": keyword, "$options": "i"}},
                {"path": {"$regex": keyword, "$options": "i"}},
            ]
        })

    for condition in extra_conditions:
        query = merge_query(query, condition)

    return query, None, None


def get_activities(args, current_user_id):
    current_user = get_current_user_by_id(current_user_id)

    if not current_user:
        return {
            "success": False,
            "message": "Không tìm thấy user hiện tại"
        }, 404

    try:
        page = int(args.get("page", 1))
    except Exception:
        page = 1

    if page < 1:
        page = 1

    limit = DEFAULT_ACTIVITY_LIMIT
    skip = (page - 1) * limit

    query, error_response, error_status = build_activity_query(args, current_user)

    if error_response:
        return error_response, error_status

    total = activities_collection.count_documents(query)

    activities = (
        activities_collection
        .find(query)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )

    data = [activity_serializer(activity) for activity in activities]

    total_pages = (total + limit - 1) // limit if total > 0 else 1

    current_role = current_user.get("role")

    return {
        "success": True,
        "message": "Lấy danh sách hoạt động thành công",
        "data": data,
        "viewer": {
            "id": str(current_user["_id"]),
            "employee_code": current_user.get("employee_code"),
            "full_name": current_user.get("full_name"),
            "email": current_user.get("email"),
            "role": current_role,
            "can_view_all": can_view_all_activities(current_role),
        },
        "filters": {
            "keyword": args.get("keyword") or args.get("search") or args.get("q") or "",
            "type": args.get("type") or args.get("activity_type") or args.get("loai") or "Tất cả",
            "user_name": args.get("user_name") or args.get("full_name") or args.get("name") or "",
            "module": args.get("module") or "Tất cả",
            "action": args.get("action") or "Tất cả",
            "status_code": args.get("status_code") or "Tất cả",
        },
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1 if page > 1 else 1,
            "next_page": page + 1 if page < total_pages else total_pages,
        }
    }, 200


def get_activity_filter_options(current_user_id):
    current_user = get_current_user_by_id(current_user_id)

    if not current_user:
        return {
            "success": False,
            "message": "Không tìm thấy user hiện tại"
        }, 404

    permission_query, error_response, error_status = build_permission_query(current_user, {})

    if error_response:
        return error_response, error_status

    type_options = []

    for activity_type in ACTIVITY_TYPE_OPTIONS:
        type_query = merge_query(
            dict(permission_query),
            build_activity_type_condition(activity_type)
        )

        count = activities_collection.count_documents(type_query)

        type_options.append({
            "label": activity_type,
            "value": activity_type,
            "count": count,
        })

    user_pipeline = [
        {
            "$match": permission_query
        },
        {
            "$group": {
                "_id": "$full_name",
                "count": {
                    "$sum": 1
                },
                "user_id": {
                    "$first": "$user_id"
                },
                "employee_code": {
                    "$first": "$employee_code"
                },
                "email": {
                    "$first": "$email"
                },
                "role": {
                    "$first": "$role"
                },
            }
        },
        {
            "$sort": {
                "_id": 1
            }
        }
    ]

    user_options = []

    for item in activities_collection.aggregate(user_pipeline):
        full_name = item.get("_id")

        if not full_name:
            continue

        user_id = item.get("user_id")

        user_options.append({
            "id": str(user_id) if user_id else "",
            "full_name": full_name,
            "value": full_name,
            "label": full_name,
            "employee_code": item.get("employee_code"),
            "email": item.get("email"),
            "role": item.get("role"),
            "count": item.get("count", 0),
        })

    total = activities_collection.count_documents(permission_query)

    return {
        "success": True,
        "message": "Lấy bộ lọc hoạt động thành công",
        "data": {
            "total": total,
            "type_options": type_options,
            "user_options": user_options,
            "limit": DEFAULT_ACTIVITY_LIMIT,
        }
    }, 200


def get_activity_by_id(activity_id, current_user_id):
    current_user = get_current_user_by_id(current_user_id)

    if not current_user:
        return {
            "success": False,
            "message": "Không tìm thấy user hiện tại"
        }, 404

    if not is_valid_object_id(activity_id):
        return {
            "success": False,
            "message": "ID hoạt động không hợp lệ"
        }, 400

    activity = activities_collection.find_one({"_id": ObjectId(activity_id)})

    if not activity:
        return {
            "success": False,
            "message": "Không tìm thấy hoạt động"
        }, 404

    current_role = current_user.get("role")

    if not can_view_all_activities(current_role):
        if str(activity.get("user_id")) != str(current_user["_id"]):
            return {
                "success": False,
                "message": "Bạn không có quyền xem hoạt động này"
            }, 403

    return {
        "success": True,
        "message": "Lấy chi tiết hoạt động thành công",
        "data": activity_serializer(activity)
    }, 200


def get_activity_stats(current_user_id):
    current_user = get_current_user_by_id(current_user_id)

    if not current_user:
        return {
            "success": False,
            "message": "Không tìm thấy user hiện tại"
        }, 404

    current_role = current_user.get("role")

    query = {}

    if not can_view_all_activities(current_role):
        query["user_id"] = current_user["_id"]

    total = activities_collection.count_documents(query)

    create_count = activities_collection.count_documents({
        **query,
        "method": "POST"
    })

    update_count = activities_collection.count_documents({
        **query,
        "method": {"$in": ["PUT", "PATCH"]}
    })

    delete_count = activities_collection.count_documents({
        **query,
        "method": "DELETE"
    })

    return {
        "success": True,
        "message": "Lấy thống kê hoạt động thành công",
        "data": {
            "total": total,
            "create_count": create_count,
            "update_count": update_count,
            "delete_count": delete_count,
        }
    }, 200
def detect_activity_export_type(activity):
    module = str(activity.get("module") or "").lower()
    action = str(activity.get("action") or "").lower()
    path = str(activity.get("path") or "").lower()
    target_name = str(activity.get("target_name") or "").lower()

    text = f"{module} {action} {path} {target_name}"

    if "report" in text or "báo cáo" in text or "bao cao" in text:
        return "Báo cáo"

    if "thu hồi" in text or "thu hoi" in text or "recover" in text or "recall" in text or "return" in text:
        return "Thu hồi"

    if "assign" in text or "cấp phát" in text or "cap phat" in text:
        return "Cấp phát"

    if "asset" in text or "tài sản" in text or "tai san" in text:
        return "Tài sản"

    if "user" in text or "người dùng" in text or "nguoi dung" in text:
        return "Người dùng"

    if "permission" in text or "phân quyền" in text or "phan quyen" in text:
        return "Phân quyền"

    if "mail" in text or "email" in text:
        return "Mail"

    if "activity" in text or "hoạt động" in text or "hoat dong" in text:
        return "Hoạt động"

    return "Hệ thống"


def format_activity_export_time(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%H:%M %d/%m/%Y")

    text = str(value).strip()

    if not text:
        return ""

    clean_text = text.replace("Z", "").replace("+00:00", "")

    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%H:%M %d/%m/%Y",
        "%d/%m/%Y %H:%M",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(clean_text[:26], fmt)
            return parsed.strftime("%H:%M %d/%m/%Y")
        except Exception:
            pass

    return text


def build_activity_export_description(activity):
    action = activity.get("action") or ""
    target_name = activity.get("target_name") or ""
    path = activity.get("path") or ""

    if target_name:
        return f'{action} "{target_name}"'

    if path:
        return f"{action} ({path})"

    return action or "Không có mô tả"


def get_activities_export(args, current_user_id):
    current_user = get_current_user_by_id(current_user_id)

    if not current_user:
        return None, None, {
            "success": False,
            "message": "Không tìm thấy user hiện tại"
        }, 404

    query, error_response, error_status = build_activity_query(args, current_user)

    if error_response:
        return None, None, error_response, error_status

    activities = (
        activities_collection
        .find(query)
        .sort("created_at", DESCENDING)
        .limit(10000)
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Hoạt động"

    headers = [
        "Người thực hiện",
        "Hành động",
        "Loại đối tượng",
        "Mô tả",
        "Thời gian",
    ]

    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    header_font = Font(bold=True, color="000000")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="left", vertical="center")

    row_index = 2

    for activity in activities:
        full_name = (
            activity.get("full_name")
            or activity.get("email")
            or activity.get("employee_code")
            or "Chưa xác định"
        )

        action = activity.get("action") or "Thao tác hệ thống"
        activity_type = detect_activity_export_type(activity)
        description = build_activity_export_description(activity)
        created_at = activity.get("created_at") or activity.get("updated_at") or activity.get("time")

        ws.append([
            full_name,
            action,
            activity_type,
            description,
            format_activity_export_time(created_at),
        ])

        for cell in ws[row_index]:
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

        row_index += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 62
    ws.column_dimensions["E"].width = 20

    for row in ws.iter_rows(min_row=2):
        ws.row_dimensions[row[0].row].height = 22

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Activities_{filename_time}.xlsx"

    return output, filename, None, 200