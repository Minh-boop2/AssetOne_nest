# Service report: xử lý logic chính của báo cáo, quyền xem, upload file và thao tác tài sản
import math
import re
from bson import ObjectId
import secrets
import string
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


# Các role được xem toàn bộ báo cáo
FULL_REPORT_ROLES = ["ADMIN", "QUAN_LY"]

# Các trường bắt buộc khi tạo báo cáo
REQUIRED_CREATE_FIELDS = {
    "report_name": "Vui lòng nhập tên báo cáo.",
    "report_type": "Vui lòng chọn loại báo cáo.",
    "description": "Vui lòng nhập nội dung báo cáo.",
}

# Các loại báo cáo bắt buộc phải chọn tài sản
ASSET_REQUIRED_REPORT_TYPES = [
    "Báo hỏng",
    "Cần cấp mới",
]

# Các trạng thái tài sản được hiểu là đang sử dụng
USING_STATUS_VALUES = [
    "using",
    "Đang sử dụng",
    "Dang su dung",
]

# Những trạng thái báo cáo KHÔNG khóa tài sản khỏi dropdown chọn tài sản.
# Báo cáo đang chờ xử lý sẽ khóa tài sản; Hoàn thành / Đã hủy thì tài sản được hiện lại.
# Các trạng thái báo cáo không còn khóa tài sản trong dropdown
REPORT_ASSET_UNLOCKED_STATUSES = [
    "Đã hủy",
    "Hoàn thành",
]

# Các role được phép tạo báo cáo
ALLOWED_CREATE_REPORT_ROLES = [
    "ADMIN",
    "QUAN_LY",
    "NHAN_VIEN",
]

# Các role được phép xóa báo cáo
ALLOWED_DELETE_REPORT_ROLES = [
    "ADMIN",
    "QUAN_LY",
    "NHAN_VIEN",
]

# Tiền tố mã báo cáo tự sinh
REPORT_CODE_PREFIX = "REPORT"
# Độ dài phần random trong mã báo cáo
REPORT_CODE_LENGTH = 8
# Số lần thử tối đa khi tạo mã báo cáo không trùng
REPORT_CODE_MAX_ATTEMPTS = 50


# Tạo mã báo cáo ngẫu nhiên và đảm bảo không bị trùng
def generate_unique_report_code():
    alphabet = string.ascii_uppercase + string.digits

    for _ in range(REPORT_CODE_MAX_ATTEMPTS):
        random_part = "".join(
            secrets.choice(alphabet)
            for _ in range(REPORT_CODE_LENGTH)
        )

        report_code = f"{REPORT_CODE_PREFIX}-{random_part}"

        if not find_report_by_code(report_code):
            return report_code

    raise ValueError("Không thể tạo mã báo cáo không trùng. Vui lòng thử lại.")


# Lấy giá trị từ data theo nhiều tên field khác nhau
def _value(data, *keys, default=""):
    data = data or {}

    for key in keys:
        if key in data:
            value = data.get(key)

            if isinstance(value, str):
                return value.strip()

            return value

    return default


# Lấy id của user hiện tại
def _current_user_id(current_user):
    if not current_user:
        return ""

    return str(current_user.get("_id") or current_user.get("id") or "")


# Lấy tên hiển thị của user hiện tại
def _current_user_name(current_user):
    if not current_user:
        return ""

    return (
        current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("email")
        or ""
    )


# Đổi role trong database sang tên role dễ hiển thị
def _current_user_role_label(current_user):
    role = (current_user or {}).get("role") or ""

    if role == "ADMIN":
        return "Admin"

    if role == "QUAN_LY":
        return "Manager"

    if role == "NHAN_VIEN":
        return "Staff"

    return role


# Lấy role gốc của user hiện tại
def _current_user_role(current_user):
    return (current_user or {}).get("role") or ""


# Lấy phòng ban của user hiện tại
def _current_user_department(current_user):
    return (
        (current_user or {}).get("department")
        or ""
    )


# Lấy vị trí hoặc tầng của user hiện tại
def _current_user_location(current_user):
    return (
        (current_user or {}).get("floor")
        or (current_user or {}).get("location")
        or ""
    )


# Kiểm tra user có quyền xem tất cả báo cáo hay không
def _can_view_all_reports(current_user):
    if not current_user:
        return False

    return current_user.get("role") in FULL_REPORT_ROLES


# Gộp nhiều query MongoDB lại bằng $and
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


# Tạo query giới hạn báo cáo theo quyền xem của user
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


# Tạo điều kiện tìm tài sản thuộc user hiện tại
def _build_asset_owner_conditions(current_user=None):
    if not current_user:
        return []

    user_id = _current_user_id(current_user)
    employee_code = str(current_user.get("employee_code") or "").strip()

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


# Tạo điều kiện tìm báo cáo do user hiện tại tạo
def _build_report_owner_conditions(current_user=None):
    if not current_user:
        return []

    user_id = _current_user_id(current_user)
    employee_code = current_user.get("employee_code") or ""
    email = current_user.get("email") or ""

    conditions = []

    if user_id:
        conditions.append({
            "reporter_user_id": user_id
        })

    if employee_code:
        conditions.append({
            "reporter_employee_code": employee_code
        })

    if email:
        conditions.append({
            "reporter_email": email
        })

    return conditions


# Chuẩn hóa giá trị thành chuỗi để so sánh key
def _string_key(value):
    value = str(value or "").strip()

    if not value:
        return ""

    return value


# Lấy các khóa nhận diện tài sản để kiểm tra tài sản có bị khóa không
def _get_asset_lock_keys(asset):
    asset = asset or {}

    keys = set()

    for key in ["id", "_id", "asset_id", "code", "asset_code"]:
        value = _string_key(asset.get(key))

        if value:
            keys.add(value)

    return keys


# Lấy các tài sản mà user đã tạo báo cáo nhưng chưa xử lý xong
def _get_current_user_reported_asset_keys(current_user=None):
    owner_conditions = _build_report_owner_conditions(current_user)

    if not owner_conditions:
        return set()

    reports = find_reports(
        query={
            "$and": [
                {
                    "$or": owner_conditions
                },
                {
                    "status": {
                        "$nin": REPORT_ASSET_UNLOCKED_STATUSES
                    }
                }
            ]
        },
        skip=0,
        limit=100000,
        sort_field="_id",
        sort_order=-1,
    )

    locked_keys = set()

    for report in reports:
        # Hỗ trợ cả báo cáo cũ chỉ có 1 tài sản và báo cáo mới có nhiều tài sản.
        for value in _get_asset_keys_from_report(report):
            if value:
                locked_keys.add(value)

    return locked_keys


# Kiểm tra tài sản đã có báo cáo đang chờ xử lý chưa
def _asset_has_locked_report(asset, current_user=None):
    asset_keys = _get_asset_lock_keys(asset)

    if not asset_keys:
        return False

    locked_keys = _get_current_user_reported_asset_keys(current_user)

    return bool(asset_keys.intersection(locked_keys))


# Kiểm tra tài sản có đang sử dụng để được chọn báo cáo không
def _is_asset_usable_for_report(asset):
    asset = asset or {}
    status = str(asset.get("status") or "").strip().lower()

    # normalize_asset đang chuẩn hóa "Đang sử dụng" về "using".
    # Check thêm tiếng Việt để chống trường hợp dữ liệu cũ chưa được chuẩn hóa.
    return status in [
        "using",
        "đang sử dụng",
        "dang su dung",
    ]


# Kiểm tra báo cáo có thuộc user hiện tại không
def _is_own_report(report, current_user=None):
    if not report or not current_user:
        return False

    user_id = _current_user_id(current_user)
    employee_code = current_user.get("employee_code") or ""
    email = current_user.get("email") or ""

    if user_id and str(report.get("reporter_user_id") or "") == user_id:
        return True

    if employee_code and str(report.get("reporter_employee_code") or "") == str(employee_code):
        return True

    if email and str(report.get("reporter_email") or "") == str(email):
        return True

    return False


# Kiểm tra user có được xóa báo cáo này không
def _can_delete_report(current_user=None, report=None):
    role = _current_user_role(current_user)

    if role not in ALLOWED_DELETE_REPORT_ROLES:
        return False

    if role in FULL_REPORT_ROLES:
        return True

    if role == "NHAN_VIEN":
        return _is_own_report(report, current_user)

    return False


# Tạo điều kiện tìm tài sản bằng asset_code hoặc ObjectId
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


# Tạo query tìm tài sản đang sử dụng của user hiện tại
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


# Kiểm tra loại báo cáo có hợp lệ không
def _validate_report_type(report_type):
    return report_type in REPORT_TYPES


# Kiểm tra trạng thái báo cáo có hợp lệ không
def _validate_status(status):
    return status in REPORT_STATUSES


# Kiểm tra dữ liệu bắt buộc khi tạo báo cáo
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


# Lưu nhiều file upload, nếu lỗi thì xóa lại file đã lưu
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


# Tìm user đã gửi báo cáo bằng user_id, mã nhân viên hoặc email
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


# Chuẩn hóa dữ liệu tài sản gửi lên / lưu trong báo cáo về danh sách key
def _normalize_asset_key_values(value):
    values = []

    if value is None:
        return values

    if isinstance(value, dict):
        for key in ["asset_id", "id", "_id", "asset_code", "code", "value", "asset"]:
            item_value = value.get(key)

            if item_value:
                values.extend(_normalize_asset_key_values(item_value))
                break

        return values

    if isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(_normalize_asset_key_values(item))

        return values

    if isinstance(value, str):
        # Frontend có thể gửi ["A1", "A2"] hoặc "A1,A2".
        parts = re.split(r"[,;]", value)
        return [
            part.strip()
            for part in parts
            if part and part.strip()
        ]

    value = _string_key(value)

    if value:
        values.append(value)

    return values


# Loại trùng nhưng vẫn giữ đúng thứ tự chọn tài sản
def _unique_asset_keys(values):
    unique_values = []
    seen_values = set()

    for value in values:
        value = _string_key(value)

        if not value or value in seen_values:
            continue

        unique_values.append(value)
        seen_values.add(value)

    return unique_values


# Lấy danh sách khóa tài sản từ data gửi lên
def _get_asset_keys_from_data(data):
    data = data or {}
    values = []

    multi_asset_fields = [
        "asset_ids",
        "asset_codes",
        "assets",
        "selected_assets",
        "selected_asset_ids",
        "selected_asset_codes",
    ]

    single_asset_fields = [
        "asset_id",
        "asset_code",
        "asset",
    ]

    for field in multi_asset_fields + single_asset_fields:
        if field in data:
            values.extend(_normalize_asset_key_values(data.get(field)))

    return _unique_asset_keys(values)


# Lấy khóa tài sản đầu tiên từ data gửi lên để tương thích code cũ
def _get_asset_key_from_data(data):
    asset_keys = _get_asset_keys_from_data(data)

    return asset_keys[0] if asset_keys else ""


# Lấy danh sách khóa tài sản từ dữ liệu báo cáo
def _get_asset_keys_from_report(report):
    report = report or {}
    values = []

    for field in ["asset_ids", "asset_codes"]:
        values.extend(_normalize_asset_key_values(report.get(field)))

    for asset in report.get("assets") or []:
        values.extend(_normalize_asset_key_values(asset))

    for field in ["asset_id", "asset_code", "asset"]:
        values.extend(_normalize_asset_key_values(report.get(field)))

    return _unique_asset_keys(values)


# Lấy khóa tài sản đầu tiên từ dữ liệu báo cáo 
def _get_asset_key_from_report(report):
    asset_keys = _get_asset_keys_from_report(report)

    return asset_keys[0] if asset_keys else ""


# Tìm tài sản đang sở hữu của user để gắn vào báo cáo
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


# Tìm nhiều tài sản đang sở hữu của user để gắn vào cùng một báo cáo
def _get_owned_assets(asset_keys, current_user=None):
    asset_keys = _unique_asset_keys(asset_keys)

    if not asset_keys:
        return [], "Vui lòng chọn ít nhất một tài sản."

    assets = []

    for asset_key in asset_keys:
        asset, asset_error = _get_owned_asset(
            asset_key=asset_key,
            current_user=current_user,
        )

        if asset_error:
            return [], f"{asset_error} ({asset_key})"

        assets.append(asset)

    return assets, None


# Tạo các field tài sản lưu trong báo cáo.
# Giữ asset_id / asset_code / asset_name của tài sản đầu tiên để không vỡ UI/API cũ,
# đồng thời lưu assets / asset_ids / asset_codes để xử lý nhiều tài sản.
def _build_report_asset_fields(assets):
    assets = assets or []
    asset_records = []

    for asset in assets:
        asset_id = _string_key(asset.get("id") or asset.get("_id"))
        asset_code = _string_key(asset.get("asset_code") or asset.get("code"))
        asset_name = (
            asset.get("asset_name")
            or asset.get("asset")
            or asset.get("name")
            or "Chưa xác định"
        )

        asset_records.append({
            "asset_id": asset_id,
            "asset_code": asset_code,
            "asset_name": asset_name,
            "asset": asset_name,
            "asset_type": asset.get("type") or asset.get("category") or "",
            "type": asset.get("type") or asset.get("category") or "",
            "category": asset.get("category") or asset.get("type") or "",
            "asset_status": asset.get("status") or "",
            "status": asset.get("status") or "",
            "department": asset.get("department") or "",
            "location": asset.get("location") or "",
            "user_id": asset.get("user_id") or "",
            "employee_code": asset.get("employee_code") or "",
            "user": asset.get("user") or asset.get("receiver") or "",
            "receiver": asset.get("receiver") or asset.get("user") or "",
        })

    first_asset = asset_records[0] if asset_records else {}

    return {
        "asset_id": first_asset.get("asset_id", ""),
        "asset_code": first_asset.get("asset_code", ""),
        "asset_name": first_asset.get("asset_name", "Chưa xác định"),
        "asset_type": first_asset.get("asset_type", ""),
        "asset_status": first_asset.get("asset_status", ""),
        "assets": asset_records,
        "asset_ids": [
            item.get("asset_id")
            for item in asset_records
            if item.get("asset_id")
        ],
        "asset_codes": [
            item.get("asset_code")
            for item in asset_records
            if item.get("asset_code")
        ],
        "asset_names": [
            item.get("asset_name")
            for item in asset_records
            if item.get("asset_name")
        ],
        "asset_count": len(asset_records),
    }


# Tạo query lọc danh sách báo cáo theo search, loại, trạng thái, phòng ban, vị trí
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


# Chuẩn hóa tài sản thành option để frontend hiển thị dropdown
def _serialize_asset_option(asset):
    return {
        "id": asset.get("id"),
        "value": asset.get("id") or asset.get("asset_code"),
        "code": asset.get("asset_code"),
        "asset_id": asset.get("id"),
        "asset_code": asset.get("asset_code"),
        "name": asset.get("asset_name") or asset.get("asset"),
        "label": (
            f"{asset.get('asset_code')} - {asset.get('asset_name') or asset.get('asset')}"
            if asset.get("asset_code")
            else (asset.get("asset_name") or asset.get("asset") or "")
        ),
        "asset_name": asset.get("asset_name") or asset.get("asset"),
        "asset": asset.get("asset_name") or asset.get("asset"),
        "type": asset.get("type"),
        "category": asset.get("category"),
        "status": asset.get("status"),
        "department": asset.get("department"),
        "location": asset.get("location"),
        "user_id": asset.get("user_id"),
        "employee_code": asset.get("employee_code"),
        "user": asset.get("user") or asset.get("receiver"),
        "receiver": asset.get("receiver") or asset.get("user"),
    }


# Đổi dữ liệu bất kỳ về list để trả về frontend
def _as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, set):
        return sorted(value)

    return list(value)


# Lấy danh sách loại báo cáo, trạng thái, role và định dạng file được phép
def get_report_options(current_user=None):
    return {
        "success": True,
        "message": "Lấy tùy chọn báo cáo thành công.",
        "data": {
            "report_types": _as_list(REPORT_TYPES),
            "types": _as_list(REPORT_TYPES),
            "statuses": _as_list(REPORT_STATUSES),
            "report_statuses": _as_list(REPORT_STATUSES),
            "reporter_roles": _as_list(REPORTER_ROLES),
            "allowed_file_extensions": _as_list(ALLOWED_FILE_EXTENSIONS),
        },
        "report_types": _as_list(REPORT_TYPES),
        "statuses": _as_list(REPORT_STATUSES),
        "reporter_roles": _as_list(REPORTER_ROLES),
        "allowed_file_extensions": _as_list(ALLOWED_FILE_EXTENSIONS),
    }, 200


# Lấy danh sách tài sản đang dùng của user để tạo báo cáo
def get_my_report_asset_options(current_user=None):
    if not current_user:
        return {
            "success": True,
            "message": "Bạn chưa đăng nhập.",
            "items": [],
            "assets": [],
            "data": [],
        }, 200

    user_id = str(
        current_user.get("_id")
        or current_user.get("id")
        or current_user.get("user_id")
        or ""
    ).strip()

    employee_code = str(current_user.get("employee_code") or "").strip()

    owner_conditions = []

    # Chỉ lấy tài sản thật sự thuộc user hiện tại.
    # Không fallback theo tên user/receiver để tránh kéo nhầm tài sản của người khác.
    if user_id:
        owner_conditions.append({
            "user_id": user_id
        })

    if employee_code:
        owner_conditions.append({
            "employee_code": employee_code
        })

    if not owner_conditions:
        return {
            "success": True,
            "message": "Không xác định được người dùng hiện tại.",
            "items": [],
            "assets": [],
            "data": [],
        }, 200

    query = {
        "$and": [
            {
                "$or": owner_conditions
            },
            {
                "status": {
                    "$in": USING_STATUS_VALUES
                }
            }
        ]
    }

    raw_assets = find_assets(
        query=query,
        skip=0,
        limit=100000,
        sort_field="_id",
        sort_order=-1,
    )

    items = []

    for raw_asset in raw_assets:
        asset = normalize_asset(raw_asset)

        # Chỉ hiện tài sản đang sử dụng.
        if asset.get("status") != "using":
            continue

        # Nếu tài sản đang có báo cáo chưa xử lý xong thì không cho chọn lại.
        # Báo cáo trạng thái "Hoàn thành" hoặc "Đã hủy" sẽ không khóa dropdown,
        # vì 2 trạng thái này nằm trong REPORT_ASSET_UNLOCKED_STATUSES.
        if _asset_has_locked_report(asset, current_user=current_user):
            continue

        asset_name = asset.get("asset_name") or asset.get("asset") or ""
        asset_code = asset.get("asset_code") or ""
        asset_id = asset.get("id") or asset_code

        label = asset_name

        if asset_code and asset_name:
            label = f"{asset_code} - {asset_name}"
        elif asset_code:
            label = asset_code

        items.append({
            "id": asset_id,
            "value": asset_id,
            "asset_id": asset_id,
            "asset_code": asset_code,
            "code": asset_code,
            "asset_name": asset_name,
            "asset": asset_name,
            "name": asset_name,
            "label": label,
            "type": asset.get("type") or asset.get("category") or "",
            "category": asset.get("category") or asset.get("type") or "",
            "status": asset.get("status") or "",
            "department": asset.get("department") or "",
            "location": asset.get("location") or "",
            "user_id": asset.get("user_id") or "",
            "employee_code": asset.get("employee_code") or "",
            "user": asset.get("user") or asset.get("receiver") or "",
            "receiver": asset.get("receiver") or asset.get("user") or "",
        })

    return {
        "success": True,
        "message": "Lấy danh sách tài sản đang sở hữu thành công.",
        "items": items,
        "assets": items,
        "data": items,
    }, 200

# Lấy danh sách báo cáo có phân trang và bộ lọc
def get_reports(filters=None, current_user=None):
    filters = filters or {}

    try:
        page = int(filters.get("page") or 1)
    except (TypeError, ValueError):
        page = 1

    try:
        limit = int(filters.get("limit") or filters.get("per_page") or 10)
    except (TypeError, ValueError):
        limit = 10

    page = max(1, page)
    limit = max(1, min(limit, 100))
    skip = (page - 1) * limit

    query = _build_report_query(
        filters=filters,
        current_user=current_user,
    )

    total_items = count_reports(query)
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1

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

    items = [
        serialize_report(report)
        for report in reports
    ]

    pagination = {
        "page": page,
        "per_page": limit,
        "limit": limit,
        "total_items": total_items,
        "total_pages": total_pages,
    }

    return {
        "success": True,
        "message": "Lấy danh sách báo cáo thành công.",
        "items": items,
        "data": items,
        "pagination": pagination,
    }, 200




# Lấy chi tiết một báo cáo theo id hoặc mã báo cáo
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


# Tạo báo cáo mới, kiểm tra dữ liệu, tài sản và lưu file nếu có
def create_report(data, uploaded_files=None, current_user=None):
    data = data or {}

    if _current_user_role(current_user) not in ALLOWED_CREATE_REPORT_ROLES:
        return {
            "success": False,
            "message": "Bạn không có quyền tạo báo cáo.",
        }, 403

    errors = _validate_create_data(data)

    if errors:
        return {
            "success": False,
            "message": errors[0]["message"],
            "errors": errors,
        }, 400

    report_type = _value(data, "report_type", "type")
    asset_keys = _get_asset_keys_from_data(data)

    assets = []

    if report_type in ASSET_REQUIRED_REPORT_TYPES:
        assets, asset_error = _get_owned_assets(
            asset_keys=asset_keys,
            current_user=current_user,
        )

        if asset_error:
            return {
                "success": False,
                "message": asset_error,
            }, 400

        for asset in assets:
            if _asset_has_locked_report(asset, current_user=current_user):
                asset_label = (
                    asset.get("asset_code")
                    or asset.get("asset_name")
                    or asset.get("asset")
                    or asset.get("id")
                    or ""
                )

                return {
                    "success": False,
                    "message": f"Bạn đã tạo báo cáo cho tài sản {asset_label}. Vui lòng chọn tài sản khác.",
                }, 409

    try:
        report_code = generate_unique_report_code()
    except ValueError as error:
        return {
            "success": False,
            "message": str(error),
        }, 500

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

        **_build_report_asset_fields(assets),

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


# Cập nhật báo cáo, có thể sửa thông tin hoặc thêm file
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

    asset_keys = _get_asset_keys_from_data(data)

    if asset_keys:
        assets, asset_error = _get_owned_assets(
            asset_keys=asset_keys,
            current_user=current_user,
        )

        if asset_error:
            return {
                "success": False,
                "message": asset_error,
            }, 400

        update_data.update(_build_report_asset_fields(assets))

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


# Duyệt báo cáo và xử lý tài sản theo loại báo cáo
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
    asset_keys = _get_asset_keys_from_report(report)

    asset_action_result = None

    if report_type == "Báo hỏng":
        if not asset_keys:
            return {
                "success": False,
                "message": "Báo cáo chưa có tài sản để chuyển sang trạng thái bảo trì.",
            }, 400

        updated_assets = []
        failed_assets = []

        for asset_key in asset_keys:
            result = update_asset(
                asset_id=asset_key,
                data={
                    "status": "maintenance"
                },
                current_user=current_user,
            )

            if not result.get("success"):
                failed_assets.append({
                    "asset_key": asset_key,
                    "message": result.get("message") or "Không thể cập nhật trạng thái tài sản.",
                    "status_code": result.get("status_code", 400),
                })
                continue

            updated_assets.append(result.get("item"))

        if failed_assets:
            return {
                "success": False,
                "message": "Một số tài sản chưa chuyển được sang trạng thái bảo trì.",
                "asset_action_result": {
                    "action": "mark_maintenance",
                    "updated_count": len(updated_assets),
                    "failed_count": len(failed_assets),
                    "updated_assets": updated_assets,
                    "failed_assets": failed_assets,
                },
            }, failed_assets[0].get("status_code", 400)

        asset_action_result = {
            "action": "mark_maintenance",
            "message": f"Đã chuyển {len(updated_assets)} tài sản sang trạng thái bảo trì.",
            "asset_count": len(updated_assets),
            "assets": updated_assets,
            # Giữ field asset cũ để frontend cũ vẫn đọc được tài sản đầu tiên.
            "asset": updated_assets[0] if updated_assets else None,
        }

    elif report_type == "Cần cấp mới":

        if not asset_keys:
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

        assigned_assets = []
        failed_assets = []

        for asset_key in asset_keys:
            result = assign_asset(
                asset_id=asset_key,
                data={
                    "user_id": str(reporter.get("_id")),
                    "employee_code": reporter.get("employee_code") or "",
                    "email": reporter.get("email") or "",
                }
            )

            if not result.get("success"):
                failed_assets.append({
                    "asset_key": asset_key,
                    "message": result.get("message") or "Không thể cấp phát tài sản.",
                    "status_code": result.get("status_code", 400),
                })
                continue

            assigned_assets.append(result.get("item"))

        if failed_assets:
            return {
                "success": False,
                "message": "Một số tài sản chưa cấp phát được.",
                "asset_action_result": {
                    "action": "assign_to_reporter",
                    "assigned_count": len(assigned_assets),
                    "failed_count": len(failed_assets),
                    "assigned_assets": assigned_assets,
                    "failed_assets": failed_assets,
                },
            }, failed_assets[0].get("status_code", 400)

        asset_action_result = {
            "action": "assign_to_reporter",
            "message": f"Đã cấp phát {len(assigned_assets)} tài sản cho người báo cáo.",
            "asset_count": len(assigned_assets),
            "assets": assigned_assets,
            # Giữ field asset cũ để frontend cũ vẫn đọc được tài sản đầu tiên.
            "asset": assigned_assets[0] if assigned_assets else None,
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


# Hủy báo cáo và lưu lý do hủy
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


# Xóa báo cáo và xóa luôn các file đã upload
def delete_report(report_id, current_user=None):
    report = find_report_by_query(
        build_report_id_query(report_id)
    )

    if not report:
        return {
            "success": False,
            "message": "Không tìm thấy báo cáo.",
        }, 404

    if not _can_delete_report(current_user=current_user, report=report):
        return {
            "success": False,
            "message": "Bạn không có quyền xóa báo cáo này.",
        }, 403

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


# Xóa một file trong báo cáo
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


# Thống kê tổng số báo cáo, trạng thái, loại và số file
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