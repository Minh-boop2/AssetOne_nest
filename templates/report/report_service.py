import math
import re
from bson import ObjectId

from mongo import users_collection

from templates.report.report_model import (
    REPORT_TYPES,
    REPORT_STATUSES,
    REPORTER_ROLES,
    ALLOWED_FILE_EXTENSIONS,
    current_vietnam_datetime,
    current_vietnam_time,
    build_report_id_query,
    serialize_report,
    count_reports,
    find_reports,
    find_report_by_query,
    find_report_by_code,
    insert_report,
    update_report_by_query,
    delete_report_by_query,
    generate_report_code,
    save_uploaded_file,
    delete_uploaded_file,
)

from templates.asset.asset_model import (
    find_assets,
    find_asset_by_query,
)

from templates.asset.asset_service import (
    update_asset,
    assign_asset,
    normalize_asset,
)


FULL_REPORT_ROLES = ["ADMIN", "QUAN_LY"]

REQUIRED_CREATE_FIELDS = {
    "report_name": "Vui lòng nhập tên báo cáo.",
    "report_type": "Vui lòng chọn loại báo cáo.",
    "description": "Vui lòng nhập nội dung báo cáo.",
}

ASSET_REQUIRED_REPORT_TYPES = [
    "Báo hỏng",
    "Cần cấp mới",
]

USING_STATUS_VALUES = [
    "using",
    "Đang sử dụng",
    "Dang su dung",
]


def _value(data, *keys, default=""):
    data = data or {}

    for key in keys:
        if key in data:
            value = data.get(key)

            if isinstance(value, str):
                return value.strip()

            return value

    return default


def _current_user_id(current_user):
    if not current_user:
        return ""

    return str(current_user.get("_id") or current_user.get("id") or "")


def _current_user_name(current_user):
    if not current_user:
        return ""

    return (
        current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("email")
        or ""
    )


def _current_user_role_label(current_user):
    role = (current_user or {}).get("role") or ""

    if role == "ADMIN":
        return "Admin"

    if role == "QUAN_LY":
        return "Manager"

    if role == "NHAN_VIEN":
        return "Staff"

    return role


def _current_user_department(current_user):
    return (
        (current_user or {}).get("department")
        or ""
    )


def _current_user_location(current_user):
    return (
        (current_user or {}).get("floor")
        or (current_user or {}).get("location")
        or ""
    )


def _can_view_all_reports(current_user):
    if not current_user:
        return False

    return current_user.get("role") in FULL_REPORT_ROLES


def _merge_queries(*queries):
    clean_queries = []

    for query in queries:
        if query:
            clean_queries.append(query)

    if not clean_queries:
        return {}

    if len(clean_queries) == 1:
        return clean_queries[0]

    return {
        "$and": clean_queries
    }


def _build_report_visibility_query(current_user=None):
    if not current_user:
        return {}

    if _can_view_all_reports(current_user):
        return {}

    user_id = _current_user_id(current_user)
    employee_code = current_user.get("employee_code") or ""

    conditions = []

    if user_id:
        conditions.append({
            "reporter_user_id": user_id
        })

    if employee_code:
        conditions.append({
            "reporter_employee_code": employee_code
        })

    if not conditions:
        return {
            "_id": {
                "$exists": False
            }
        }

    return {
        "$or": conditions
    }


def _build_asset_owner_conditions(current_user=None):
    if not current_user:
        return []

    user_id = _current_user_id(current_user)
    employee_code = current_user.get("employee_code") or ""

    conditions = []

    if user_id:
        conditions.append({
            "user_id": user_id
        })

    if employee_code:
        conditions.append({
            "employee_code": employee_code
        })

    return conditions


def _build_asset_key_conditions(asset_key):
    asset_key = str(asset_key or "").strip()

    if not asset_key:
        return []

    conditions = [
        {
            "asset_code": asset_key
        }
    ]

    if ObjectId.is_valid(asset_key):
        conditions.append({
            "_id": ObjectId(asset_key)
        })

    return conditions


def _build_owned_asset_query(current_user=None, asset_key=None):
    owner_conditions = _build_asset_owner_conditions(current_user)

    if not owner_conditions:
        return None

    conditions = [
        {
            "$or": owner_conditions
        },
        {
            "status": {
                "$in": USING_STATUS_VALUES
            }
        }
    ]

    if asset_key:
        asset_key_conditions = _build_asset_key_conditions(asset_key)

        if not asset_key_conditions:
            return None

        conditions.append({
            "$or": asset_key_conditions
        })

    return {
        "$and": conditions
    }


def _validate_report_type(report_type):
    return report_type in REPORT_TYPES


def _validate_status(status):
    return status in REPORT_STATUSES


def _validate_create_data(data):
    errors = []

    for field, message in REQUIRED_CREATE_FIELDS.items():
        value = _value(data, field)

        if not value:
            errors.append({
                "field": field,
                "message": message,
            })

    report_type = _value(data, "report_type", "type")

    if report_type and not _validate_report_type(report_type):
        errors.append({
            "field": "report_type",
            "message": "Loại báo cáo không hợp lệ.",
        })

    status = _value(data, "status", default="Chờ xử lý") or "Chờ xử lý"

    if status and not _validate_status(status):
        errors.append({
            "field": "status",
            "message": "Trạng thái báo cáo không hợp lệ.",
        })

    return errors


def _save_files(uploaded_files):
    saved_files = []

    for uploaded_file in uploaded_files or []:
        if not uploaded_file or not uploaded_file.filename:
            continue

        try:
            file_record = save_uploaded_file(uploaded_file)

            if file_record:
                saved_files.append(file_record)

        except ValueError as error:
            for saved_file in saved_files:
                delete_uploaded_file(saved_file)

            return None, str(error)

    return saved_files, None


def _find_user_for_report(report):
    reporter_user_id = report.get("reporter_user_id")
    reporter_employee_code = report.get("reporter_employee_code")
    reporter_email = report.get("reporter_email")

    if reporter_user_id and ObjectId.is_valid(reporter_user_id):
        user = users_collection.find_one({
            "_id": ObjectId(reporter_user_id)
        })

        if user:
            return user

    if reporter_employee_code:
        user = users_collection.find_one({
            "employee_code": reporter_employee_code
        })

        if user:
            return user

    if reporter_email:
        user = users_collection.find_one({
            "email": reporter_email
        })

        if user:
            return user

    return None


def _get_asset_key_from_data(data):
    return (
        _value(data, "asset_id", default="")
        or _value(data, "asset_code", default="")
        or _value(data, "asset", default="")
    )


def _get_asset_key_from_report(report):
    return (
        report.get("asset_id")
        or report.get("asset_code")
        or report.get("asset")
        or ""
    )


def _get_owned_asset(asset_key, current_user=None):
    if not asset_key:
        return None, "Vui lòng chọn tài sản."

    query = _build_owned_asset_query(
        current_user=current_user,
        asset_key=asset_key,
    )

    if not query:
        return None, "Không xác định được tài sản đang sở hữu."

    raw_asset = find_asset_by_query(query)

    if not raw_asset:
        return None, "Không tìm thấy tài sản đang sở hữu của bạn."

    asset = normalize_asset(raw_asset)

    if asset.get("status") != "using":
        return None, "Chỉ được chọn tài sản đang sử dụng / đang sở hữu."

    return asset, None


def _build_report_query(filters=None, current_user=None):
    filters = filters or {}
    conditions = []

    visibility_query = _build_report_visibility_query(current_user)

    if visibility_query:
        conditions.append(visibility_query)

    search = _value(filters, "search", "q", default="")
    report_type = _value(filters, "report_type", "type", default="")
    status = _value(filters, "status", default="")
    reporter = _value(filters, "reporter", default="")
    department = _value(filters, "department", default="")
    location = _value(filters, "location", default="")

    if search:
        safe_search = re.escape(search)

        conditions.append({
            "$or": [
                {"report_code": {"$regex": safe_search, "$options": "i"}},
                {"report_name": {"$regex": safe_search, "$options": "i"}},
                {"report_type": {"$regex": safe_search, "$options": "i"}},
                {"reporter": {"$regex": safe_search, "$options": "i"}},
                {"reporter_employee_code": {"$regex": safe_search, "$options": "i"}},
                {"asset_code": {"$regex": safe_search, "$options": "i"}},
                {"asset_name": {"$regex": safe_search, "$options": "i"}},
                {"department": {"$regex": safe_search, "$options": "i"}},
                {"location": {"$regex": safe_search, "$options": "i"}},
                {"description": {"$regex": safe_search, "$options": "i"}},
            ]
        })

    if report_type and report_type != "Tất cả":
        conditions.append({
            "report_type": report_type
        })

    if status and status != "Tất cả":
        conditions.append({
            "status": status
        })

    if reporter:
        conditions.append({
            "reporter": {
                "$regex": re.escape(reporter),
                "$options": "i"
            }
        })

    if department and department != "Tất cả":
        conditions.append({
            "department": department
        })

    if location and location != "Tất cả":
        conditions.append({
            "location": location
        })

    if not conditions:
        return {}

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions
    }


def _serialize_asset_option(asset):
    return {
        "id": asset.get("id"),
        "code": asset.get("asset_code"),
        "asset_code": asset.get("asset_code"),
        "name": asset.get("asset_name") or asset.get("asset"),
        "asset_name": asset.get("asset_name") or asset.get("asset"),
        "type": asset.get("type"),
        "category": asset.get("category"),
        "status": asset.get("status"),
        "department": asset.get("department"),
        "location": asset.get("location"),
        "user_id": asset.get("user_id"),
        "employee_code": asset.get("employee_code"),
        "user": asset.get("user") or asset.get("receiver"),
    }


def get_my_report_asset_options(current_user=None):
    if not current_user:
        return {
            "success": False,
            "message": "Không xác định được người dùng hiện tại.",
            "data": [],
            "total": 0,
        }, 401

    query = _build_owned_asset_query(current_user=current_user)

    if not query:
        return {
            "success": True,
            "message": "Người dùng hiện tại chưa có tài sản đang sở hữu.",
            "data": [],
            "total": 0,
        }, 200

    raw_assets = find_assets(
        query=query,
        skip=0,
        limit=100000,
        sort_field="_id",
        sort_order=-1,
    )

    assets = [
        _serialize_asset_option(normalize_asset(item))
        for item in raw_assets
    ]

    return {
        "success": True,
        "message": "Lấy danh sách tài sản đang sở hữu thành công.",
        "data": assets,
        "total": len(assets),
    }, 200


def get_report_options(current_user=None):
    asset_response, _ = get_my_report_asset_options(current_user)

    return {
        "success": True,
        "message": "Lấy tùy chọn báo cáo thành công.",
        "data": {
            "report_types": REPORT_TYPES,
            "types": REPORT_TYPES,
            "statuses": REPORT_STATUSES,
            "reporter_roles": REPORTER_ROLES,
            "allowed_file_extensions": sorted(ALLOWED_FILE_EXTENSIONS),
            "asset_options": asset_response.get("data", []),
        }
    }, 200


def get_reports(filters=None, current_user=None):
    filters = filters or {}

    try:
        page = int(_value(filters, "page", default=1))
    except Exception:
        page = 1

    try:
        limit = int(_value(filters, "limit", "per_page", default=10))
    except Exception:
        limit = 10

    page = max(1, page)
    limit = max(1, min(limit, 100))
    skip = (page - 1) * limit

    query = _build_report_query(
        filters=filters,
        current_user=current_user,
    )

    total = count_reports(query)
    total_pages = math.ceil(total / limit) if total > 0 else 1

    if page > total_pages:
        page = total_pages
        skip = (page - 1) * limit

    reports = find_reports(
        query=query,
        skip=skip,
        limit=limit,
        sort_field="_id",
        sort_order=-1,
    )

    data = [
        serialize_report(report)
        for report in reports
    ]

    return {
        "success": True,
        "message": "Lấy danh sách báo cáo thành công.",
        "data": data,
        "items": data,
        "total": total,
        "pagination": {
            "page": page,
            "limit": limit,
            "per_page": limit,
            "total": total,
            "total_items": total,
            "total_pages": total_pages,
        }
    }, 200


def get_report_by_id(report_id, current_user=None):
    report_query = build_report_id_query(report_id)
    visibility_query = _build_report_visibility_query(current_user)

    query = _merge_queries(
        report_query,
        visibility_query,
    )

    report = find_report_by_query(query)

    if not report:
        return {
            "success": False,
            "message": "Không tìm thấy báo cáo.",
        }, 404

    return {
        "success": True,
        "message": "Lấy chi tiết báo cáo thành công.",
        "data": serialize_report(report),
    }, 200


def create_report(data, uploaded_files=None, current_user=None):
    data = data or {}

    errors = _validate_create_data(data)

    if errors:
        return {
            "success": False,
            "message": errors[0]["message"],
            "errors": errors,
        }, 400

    report_type = _value(data, "report_type", "type")
    asset_key = _get_asset_key_from_data(data)

    asset = None

    if report_type in ASSET_REQUIRED_REPORT_TYPES:
        asset, asset_error = _get_owned_asset(
            asset_key=asset_key,
            current_user=current_user,
        )

        if asset_error:
            return {
                "success": False,
                "message": asset_error,
            }, 400

    report_code = _value(data, "report_code", default="")

    if not report_code:
        report_code = generate_report_code()

    if find_report_by_code(report_code):
        return {
            "success": False,
            "message": "Mã báo cáo đã tồn tại.",
        }, 409

    saved_files, file_error = _save_files(uploaded_files)

    if file_error:
        return {
            "success": False,
            "message": file_error,
        }, 400

    now = current_vietnam_datetime()

    reporter_user_id = _current_user_id(current_user)
    reporter_employee_code = (current_user or {}).get("employee_code") or ""
    reporter_email = (current_user or {}).get("email") or ""

    report = {
        "report_code": report_code,
        "report_name": _value(data, "report_name", "title", "name"),
        "report_type": report_type,

        "reporter_user_id": reporter_user_id,
        "reporter_employee_code": reporter_employee_code,
        "reporter_email": reporter_email,
        "reporter": _current_user_name(current_user),
        "reporter_role": _current_user_role_label(current_user),

        "asset_id": asset.get("id") if asset else "",
        "asset_code": asset.get("asset_code") if asset else "",
        "asset_name": (
            asset.get("asset_name")
            or asset.get("asset")
            if asset else "Chưa xác định"
        ) or "Chưa xác định",
        "asset_type": asset.get("type") if asset else "",
        "asset_status": asset.get("status") if asset else "",

        "department": _current_user_department(current_user),
        "location": _current_user_location(current_user),

        "description": _value(data, "description", "content"),
        "status": "Chờ xử lý",
        "time": _value(data, "time", default=current_vietnam_time()),

        "files": saved_files or [],

        "approved_by": "",
        "approved_at": None,
        "approval_note": "",
        "asset_action_result": None,

        "cancelled_by": "",
        "cancelled_at": None,
        "cancel_reason": "",

        "created_at": now,
        "updated_at": now,
    }

    result = insert_report(report)

    created_report = find_report_by_query({
        "_id": result.inserted_id
    })

    return {
        "success": True,
        "message": "Tạo báo cáo thành công.",
        "data": serialize_report(created_report),
    }, 201


def update_report(report_id, data, uploaded_files=None, current_user=None):
    data = data or {}

    report_query = build_report_id_query(report_id)
    visibility_query = _build_report_visibility_query(current_user)

    query = _merge_queries(
        report_query,
        visibility_query,
    )

    report = find_report_by_query(query)

    if not report:
        return {
            "success": False,
            "message": "Không tìm thấy báo cáo.",
        }, 404

    if report.get("status") == "Hoàn thành":
        return {
            "success": False,
            "message": "Báo cáo đã hoàn thành, không thể chỉnh sửa.",
        }, 400

    new_report_code = _value(data, "report_code", default=None)

    if new_report_code and new_report_code != report.get("report_code"):
        existing_report = find_report_by_code(new_report_code)

        if existing_report and str(existing_report.get("_id")) != str(report.get("_id")):
            return {
                "success": False,
                "message": "Mã báo cáo đã tồn tại.",
            }, 409

    new_report_type = _value(data, "report_type", "type", default=None)

    if new_report_type and not _validate_report_type(new_report_type):
        return {
            "success": False,
            "message": "Loại báo cáo không hợp lệ.",
        }, 400

    new_status = _value(data, "status", default=None)

    if new_status and not _validate_status(new_status):
        return {
            "success": False,
            "message": "Trạng thái báo cáo không hợp lệ.",
        }, 400

    saved_files, file_error = _save_files(uploaded_files)

    if file_error:
        return {
            "success": False,
            "message": file_error,
        }, 400

    update_data = {}

    editable_fields = {
        "report_code": ("report_code",),
        "report_name": ("report_name", "title", "name"),
        "report_type": ("report_type", "type"),
        "description": ("description", "content"),
        "status": ("status",),
        "time": ("time",),
    }

    for field, aliases in editable_fields.items():
        new_value = _value(data, *aliases, default=None)

        if new_value is not None:
            update_data[field] = new_value

    asset_key = _get_asset_key_from_data(data)

    if asset_key:
        asset, asset_error = _get_owned_asset(
            asset_key=asset_key,
            current_user=current_user,
        )

        if asset_error:
            return {
                "success": False,
                "message": asset_error,
            }, 400

        update_data["asset_id"] = asset.get("id")
        update_data["asset_code"] = asset.get("asset_code")
        update_data["asset_name"] = asset.get("asset_name") or asset.get("asset") or "Chưa xác định"
        update_data["asset_type"] = asset.get("type")
        update_data["asset_status"] = asset.get("status")

    current_files = report.get("files", [])

    if not isinstance(current_files, list):
        current_files = []

    if saved_files:
        update_data["files"] = current_files + saved_files

    if not update_data:
        return {
            "success": False,
            "message": "Không có dữ liệu để cập nhật.",
        }, 400

    update_data["updated_at"] = current_vietnam_datetime()

    update_report_by_query(
        {
            "_id": report.get("_id")
        },
        update_data
    )

    updated_report = find_report_by_query({
        "_id": report.get("_id")
    })

    return {
        "success": True,
        "message": "Cập nhật báo cáo thành công.",
        "data": serialize_report(updated_report),
    }, 200


def approve_report(report_id, data=None, current_user=None):
    data = data or {}

    report = find_report_by_query(
        build_report_id_query(report_id)
    )

    if not report:
        return {
            "success": False,
            "message": "Không tìm thấy báo cáo.",
        }, 404

    if report.get("status") == "Hoàn thành":
        return {
            "success": False,
            "message": "Báo cáo đã được duyệt trước đó.",
        }, 400

    if report.get("status") == "Đã hủy":
        return {
            "success": False,
            "message": "Báo cáo đã hủy, không thể duyệt.",
        }, 400

    report_type = report.get("report_type")
    asset_key = _get_asset_key_from_report(report)

    asset_action_result = None

    if report_type == "Báo hỏng":
        if not asset_key:
            return {
                "success": False,
                "message": "Báo cáo chưa có tài sản để chuyển sang trạng thái hỏng.",
            }, 400

        result = update_asset(
            asset_id=asset_key,
            data={
                "status": "broken"
            },
            current_user=current_user,
        )

        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("message") or "Không thể cập nhật trạng thái tài sản.",
            }, result.get("status_code", 400)

        asset_action_result = {
            "action": "mark_broken",
            "message": "Đã chuyển tài sản sang trạng thái hỏng.",
            "asset": result.get("item"),
        }

    elif report_type == "Cần cấp mới":
        if not asset_key:
            return {
                "success": False,
                "message": "Báo cáo chưa có tài sản để cấp phát.",
            }, 400

        reporter = _find_user_for_report(report)

        if not reporter:
            return {
                "success": False,
                "message": "Không tìm thấy người báo cáo để cấp phát tài sản.",
            }, 404

        result = assign_asset(
            asset_id=asset_key,
            data={
                "user_id": str(reporter.get("_id")),
                "employee_code": reporter.get("employee_code") or "",
                "email": reporter.get("email") or "",
            }
        )

        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("message") or "Không thể cấp phát tài sản.",
            }, result.get("status_code", 400)

        asset_action_result = {
            "action": "assign_to_reporter",
            "message": "Đã cấp phát tài sản cho người báo cáo.",
            "asset": result.get("item"),
        }

    else:
        asset_action_result = {
            "action": "none",
            "message": "Báo cáo loại Khác chỉ cập nhật trạng thái hoàn thành.",
        }

    now = current_vietnam_datetime()

    update_data = {
        "status": "Hoàn thành",
        "approved_by": _current_user_name(current_user),
        "approved_at": now,
        "approval_note": _value(data, "approval_note", "note", default=""),
        "asset_action_result": asset_action_result,
        "updated_at": now,
    }

    update_report_by_query(
        {
            "_id": report.get("_id")
        },
        update_data
    )

    updated_report = find_report_by_query({
        "_id": report.get("_id")
    })

    return {
        "success": True,
        "message": "Duyệt báo cáo thành công.",
        "data": serialize_report(updated_report),
        "asset_action_result": asset_action_result,
    }, 200


def cancel_report(report_id, data=None, current_user=None):
    data = data or {}

    report = find_report_by_query(
        build_report_id_query(report_id)
    )

    if not report:
        return {
            "success": False,
            "message": "Không tìm thấy báo cáo.",
        }, 404

    if report.get("status") == "Hoàn thành":
        return {
            "success": False,
            "message": "Báo cáo đã hoàn thành, không thể hủy.",
        }, 400

    now = current_vietnam_datetime()

    update_report_by_query(
        {
            "_id": report.get("_id")
        },
        {
            "status": "Đã hủy",
            "cancelled_by": _current_user_name(current_user),
            "cancelled_at": now,
            "cancel_reason": _value(data, "cancel_reason", "reason", default=""),
            "updated_at": now,
        }
    )

    updated_report = find_report_by_query({
        "_id": report.get("_id")
    })

    return {
        "success": True,
        "message": "Hủy báo cáo thành công.",
        "data": serialize_report(updated_report),
    }, 200


def delete_report(report_id):
    report = find_report_by_query(
        build_report_id_query(report_id)
    )

    if not report:
        return {
            "success": False,
            "message": "Không tìm thấy báo cáo.",
        }, 404

    for file_record in report.get("files", []):
        delete_uploaded_file(file_record)

    result = delete_report_by_query({
        "_id": report.get("_id")
    })

    return {
        "success": True,
        "message": "Xóa báo cáo thành công.",
        "deleted_count": result.deleted_count,
        "data": serialize_report(report),
    }, 200


def delete_report_file(report_id, file_id, current_user=None):
    report_query = build_report_id_query(report_id)
    visibility_query = _build_report_visibility_query(current_user)

    query = _merge_queries(
        report_query,
        visibility_query,
    )

    report = find_report_by_query(query)

    if not report:
        return {
            "success": False,
            "message": "Không tìm thấy báo cáo.",
        }, 404

    files = report.get("files", [])

    if not isinstance(files, list):
        files = []

    deleted_file = None
    new_files = []

    for file_record in files:
        if str(file_record.get("id")) == str(file_id):
            deleted_file = file_record
        else:
            new_files.append(file_record)

    if not deleted_file:
        return {
            "success": False,
            "message": "Không tìm thấy file.",
        }, 404

    delete_uploaded_file(deleted_file)

    update_report_by_query(
        {
            "_id": report.get("_id")
        },
        {
            "files": new_files,
            "updated_at": current_vietnam_datetime(),
        }
    )

    return {
        "success": True,
        "message": "Xóa file thành công.",
        "data": deleted_file,
    }, 200


def get_report_overview(current_user=None):
    visibility_query = _build_report_visibility_query(current_user)

    reports = find_reports(
        query=visibility_query,
        skip=0,
        limit=100000,
        sort_field="_id",
        sort_order=-1,
    )

    by_type = {}
    by_status = {}
    total_files = 0

    for report in reports:
        report_type = report.get("report_type", "Khác")
        status = report.get("status", "Chờ xử lý")
        files = report.get("files", [])

        by_type[report_type] = by_type.get(report_type, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1

        if isinstance(files, list):
            total_files += len(files)

    return {
        "success": True,
        "message": "Lấy thống kê báo cáo thành công.",
        "data": {
            "total": len(reports),
            "pending": by_status.get("Chờ xử lý", 0),
            "completed": by_status.get("Hoàn thành", 0),
            "cancelled": by_status.get("Đã hủy", 0),
            "total_files": total_files,
            "by_type": by_type,
            "by_status": by_status,
        }
    }, 200