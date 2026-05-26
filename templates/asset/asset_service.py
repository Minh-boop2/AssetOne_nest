# file này chứa phần xử lý chính cho chức năng quản lý tài sản
# API sẽ gọi các hàm trong file này để tìm, thêm, sửa, xóa và cấp phát tài sản
from bson import ObjectId
from datetime import datetime
import math
import re


# dùng users_collection để tìm người dùng khi cấp phát tài sản
from mongo import users_collection


# import các hàm thao tác trực tiếp với collection tài sản trong MongoDB
from .asset_model import (
    count_assets,
    find_assets,
    find_assets_for_counts,
    find_asset_by_query,
    delete_asset_by_query,
    insert_asset,
    insert_many_assets,
    find_assets_by_ids,
    asset_code_exists,
    update_asset_by_query,
)


# các trường sẽ được dùng khi người dùng nhập ô tìm kiếm
SEARCH_FIELDS = [
    "asset_name",
    "asset",
    "asset_code",
    "user",
    "receiver",
    "user_id",
    "employee_code",
    "department",
    "location",
    "status",
    "type",
    "category",
    "warranty",
    "spec",
    "notes",
]


# gom các cách viết khác nhau của cùng 1 loại tài sản
# ví dụ: pc, PC, Máy tính bàn đều hiểu là pc
TYPE_ALIASES = {
    "laptop": ["laptop", "Laptop", "LAPTOP"],
    "pc": ["pc", "PC", "Máy tính bàn", "May tinh ban", "Desktop", "desktop"],
    "printer": ["printer", "Printer", "Máy in", "May in"],
    "monitor": ["monitor", "Monitor", "Màn hình", "Man hinh"],
    "phone": ["phone", "Phone", "Điện thoại", "Dien thoai"],
    "projector": ["projector", "Projector", "Máy chiếu", "May chieu"],
    "scanner": ["scanner", "Scanner", "Máy quét", "May quet"],
    "network": ["network", "Network", "Thiết bị mạng", "Thiet bi mang"],
    "ups": ["ups", "UPS"],
    "camera": ["camera", "Camera", "Webcam", "webcam"],
    "speaker": ["speaker", "Speaker", "Loa"],
    "microphone": ["microphone", "Microphone", "Micro", "mic"],
    "keyboard": ["keyboard", "Keyboard", "Bàn phím", "Ban phim"],
    "mouse": ["mouse", "Mouse", "Chuột", "Chuot"],
    "tablet": ["tablet", "Tablet", "Máy tính bảng", "May tinh bang"],
    "server": ["server", "Server", "Máy chủ", "May chu"],
    "router": ["router", "Router"],
    "switch": ["switch", "Switch"],
    "storage": ["storage", "Storage", "Ổ cứng", "O cung", "NAS", "nas"],
    "accessory": ["accessory", "Accessory", "Phụ kiện", "Phu kien"],
}


# gom các cách viết khác nhau của cùng 1 trạng thái
STATUS_ALIASES = {
    "using": ["using", "Đang sử dụng", "Dang su dung", "Hoàn thành"],
    "available": ["available", "Chưa sử dụng", "Chua su dung"],
    "maintenance": ["maintenance", "Bảo trì", "Bao tri"],
    "broken": ["broken", "Hỏng", "Hong"],
    "pending": ["pending", "Chờ duyệt", "Cho duyet"],
}


# tên tiếng Việt dùng để hiển thị trạng thái cho dễ đọc
STATUS_LABELS = {
    "using": "Đang sử dụng",
    "available": "Chưa sử dụng",
    "maintenance": "Bảo trì",
    "broken": "Hỏng",
    "pending": "Chờ duyệt",
}


# class CSS tương ứng với từng trạng thái tài sản
STATUS_BADGE_CLASSES = {
    "using": "status-using",
    "available": "status-free",
    "maintenance": "status-error",
    "broken": "status-error",
    "pending": "status-free",
}


# các role này được xem toàn bộ tài sản trong hệ thống
FULL_ASSET_ROLES = ["ADMIN", "QUAN_LY"]


# kiểm tra user hiện tại có được xem toàn bộ tài sản hay không
def user_can_view_all_assets(current_user):
    # nếu không có user thì chắc chắn không được xem tất cả
    if not current_user:
        return False

    return current_user.get("role") in FULL_ASSET_ROLES


# gộp nhiều query MongoDB lại với nhau
# nếu có nhiều điều kiện thì dùng $and
def merge_asset_queries(*queries):
    # bỏ qua các query rỗng để tránh làm điều kiện bị sai
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


# tạo điều kiện lọc tài sản theo quyền xem của user
# ADMIN/QUAN_LY xem tất cả, nhân viên chỉ xem tài sản của chính mình
def build_asset_visibility_query(current_user=None):
    # nếu không truyền user thì mặc định không giới hạn dữ liệu
    if not current_user:
        return {}

    # user có quyền cao thì được xem tất cả nên query rỗng
    if user_can_view_all_assets(current_user):
        return {}

    current_user_id = str(current_user.get("_id") or "")
    employee_code = current_user.get("employee_code") or ""

    # nhân viên chỉ được xem tài sản gắn với user_id hoặc mã nhân viên của mình
    owner_conditions = []

    if current_user_id:
        owner_conditions.append({
            "user_id": current_user_id
        })

    if employee_code:
        owner_conditions.append({
            "employee_code": employee_code
        })

    # nếu không có thông tin định danh thì trả query không match tài sản nào
    if not owner_conditions:
        return {
            "_id": {
                "$exists": False
            }
        }

    return {
        "$or": owner_conditions
    }


# đổi datetime thành chuỗi để JSON trả về frontend không bị lỗi
def serialize_datetime(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.isoformat()

    return value


# chuẩn hóa loại tài sản về 1 mã thống nhất
# ví dụ: Máy in, Printer đều có thể về printer
def normalize_type_code(value):
    # xóa khoảng trắng thừa trước khi so sánh
    value = (value or "").strip()

    for code, aliases in TYPE_ALIASES.items():
        if value in aliases:
            return code

    return value


# chuẩn hóa trạng thái tài sản về 1 mã thống nhất
def normalize_status_code(value):
    # xóa khoảng trắng thừa trước khi so sánh
    value = (value or "").strip()

    for code, aliases in STATUS_ALIASES.items():
        if value in aliases:
            return code

    return "pending"


# lấy danh sách các cách viết có thể có của 1 loại tài sản
def aliases_for_type(asset_type):
    asset_type = (asset_type or "").strip()

    if not asset_type or asset_type == "Tất cả":
        return None

    code = normalize_type_code(asset_type)

    if code in TYPE_ALIASES:
        return TYPE_ALIASES.get(code, [asset_type])

    return [asset_type]


# lấy danh sách các cách viết có thể có của 1 trạng thái
def aliases_for_status(status):
    if not status or status == "Tất cả":
        return None

    code = normalize_status_code(status)

    return STATUS_ALIASES.get(code, [status])


# chuẩn hóa dữ liệu tài sản lấy từ database trước khi trả ra frontend
def normalize_asset(item):
    # copy item ra dict mới để không sửa trực tiếp dữ liệu gốc
    row = dict(item)

    raw_type = row.get("type") or row.get("category") or ""
    raw_status = row.get("status") or ""

    type_code = normalize_type_code(raw_type)
    status_code = normalize_status_code(raw_status)

    # đổi _id của MongoDB sang id dạng chuỗi cho frontend dễ dùng
    row["id"] = str(row.get("_id", ""))
    row["asset"] = row.get("asset") or row.get("asset_name") or ""
    row["asset_name"] = row.get("asset_name") or row.get("asset") or ""

    row["user_id"] = row.get("user_id") or ""
    row["employee_code"] = row.get("employee_code") or ""
    row["user"] = row.get("user") or row.get("receiver") or ""
    row["receiver"] = row.get("receiver") or row.get("user") or ""

    row["type"] = type_code
    row["category"] = type_code
    row["status"] = status_code

    row["raw_type"] = raw_type
    row["raw_status"] = raw_status

    row["department"] = row.get("department") or ""
    row["location"] = row.get("location") or ""
    row["asset_code"] = row.get("asset_code") or ""
    row["warranty"] = row.get("warranty") or ""
    row["spec"] = row.get("spec") or row.get("notes") or ""
    row["notes"] = row.get("notes") or row.get("spec") or ""

    row["assigned_at"] = serialize_datetime(row.get("assigned_at"))
    row["returned_at"] = serialize_datetime(row.get("returned_at"))
    row["created_at"] = serialize_datetime(row.get("created_at"))
    row["updated_at"] = serialize_datetime(row.get("updated_at"))

    # bỏ _id gốc vì ObjectId không trả JSON trực tiếp đẹp bằng string id
    row.pop("_id", None)

    return row


# chuẩn hóa dữ liệu tài sản frontend gửi lên trước khi lưu database
def normalize_asset_payload(data):
    # copy data ra dict mới để tránh làm thay đổi object ban đầu
    data = dict(data)

    asset_name = data.get("asset_name") or data.get("asset") or ""
    user = data.get("user") or data.get("receiver") or ""
    raw_type = data.get("type") or data.get("category") or ""
    raw_status = data.get("status") or "available"

    type_code = normalize_type_code(raw_type)
    status_code = normalize_status_code(raw_status)

    data["asset_name"] = asset_name
    data["asset"] = asset_name

    data["user_id"] = data.get("user_id") or ""
    data["employee_code"] = data.get("employee_code") or ""
    data["user"] = user
    data["receiver"] = user

    data["type"] = type_code
    data["category"] = type_code
    data["status"] = status_code

    data["asset_code"] = data.get("asset_code") or ""

    data["department"] = data.get("department") or ""
    data["location"] = data.get("location") or ""

    data["warranty"] = data.get("warranty") or ""
    data["spec"] = data.get("spec") or data.get("notes") or ""
    data["notes"] = data.get("notes") or data.get("spec") or ""

    # tự gắn thời gian tạo và cập nhật
    now = datetime.utcnow()
    data["created_at"] = data.get("created_at") or now
    data["updated_at"] = now

    data["assigned_at"] = data.get("assigned_at") or ""
    data["returned_at"] = data.get("returned_at") or ""

    return data


# kiểm tra dữ liệu tài sản có thiếu trường bắt buộc hay không
def validate_asset_payload(data):
    # gom lỗi vào dict để frontend biết field nào bị sai
    errors = {}

    if not data.get("asset_code"):
        errors["asset_code"] = "Mã tài sản là bắt buộc"

    if not data.get("asset_name") and not data.get("asset"):
        errors["asset_name"] = "Tên tài sản là bắt buộc"

    if not data.get("type") and not data.get("category"):
        errors["type"] = "Loại tài sản là bắt buộc"

    if not data.get("status"):
        errors["status"] = "Trạng thái là bắt buộc"

    return errors


# tạo query lọc danh sách tài sản theo tìm kiếm, loại, phòng ban và trạng thái
def build_asset_query(
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
):
    # mỗi bộ lọc sẽ tạo ra 1 điều kiện rồi gom lại ở cuối
    conditions = []

    if search:
        # escape để tránh ký tự đặc biệt trong regex gây lỗi tìm kiếm
        safe_search = re.escape(search.strip())

        conditions.append({
            "$or": [
                {field: {"$regex": safe_search, "$options": "i"}}
                for field in SEARCH_FIELDS
            ]
        })

    type_values = aliases_for_type(asset_type)

    if type_values:
        conditions.append({
            "$or": [
                {"type": {"$in": type_values}},
                {"category": {"$in": type_values}},
            ]
        })

    if department and department != "Tất cả":
        conditions.append({
            "department": department
        })

    status_values = aliases_for_status(status)

    if status_values:
        conditions.append({
            "status": {
                "$in": status_values
            }
        })

    if not conditions:
        return {}

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions
    }


# tạo query tìm tài sản theo ObjectId hoặc theo mã tài sản
def build_asset_id_query(asset_id):
    # nếu asset_id là ObjectId hợp lệ thì tìm theo _id
    if ObjectId.is_valid(asset_id):
        return {
            "_id": ObjectId(asset_id)
        }

    # nếu không phải ObjectId thì hiểu là mã tài sản
    return {
        "asset_code": asset_id
    }


# đếm số lượng tài sản theo loại, trạng thái, phòng ban và vị trí
# dữ liệu này dùng để hiển thị bộ lọc và thống kê nhanh
def get_asset_filter_counts(current_user=None):
    # khởi tạo các biến đếm mặc định
    type_counts = {
        "all": 0,
    }

    status_counts = {
        "all": 0,
        "using": 0,
        "available": 0,
        "maintenance": 0,
        "broken": 0,
        "pending": 0,
    }

    department_counts = {
        "all": 0
    }

    location_counts = {
        "all": 0
    }

    # chỉ đếm những tài sản user hiện tại được phép nhìn thấy
    visibility_query = build_asset_visibility_query(current_user)

    if visibility_query:
        cursor = find_assets(
            query=visibility_query,
            skip=0,
            limit=100000,
            sort_field="_id",
            sort_order=-1,
        )
    else:
        cursor = find_assets_for_counts()

    # duyệt từng tài sản để cộng số lượng vào nhóm tương ứng
    for item in cursor:
        type_code = normalize_type_code(item.get("type") or item.get("category"))
        status_code = normalize_status_code(item.get("status"))

        if not type_code:
            type_code = "other"

        if status_code not in status_counts:
            status_code = "pending"

        type_counts["all"] += 1
        status_counts["all"] += 1
        department_counts["all"] += 1
        location_counts["all"] += 1

        type_counts[type_code] = type_counts.get(type_code, 0) + 1
        status_counts[status_code] = status_counts.get(status_code, 0) + 1

        department = item.get("department")
        location = item.get("location")

        if department:
            department_counts[department] = department_counts.get(department, 0) + 1

        if location:
            location_counts[location] = location_counts.get(location, 0) + 1

    return {
        "type": type_counts,
        "status": status_counts,
        "department": department_counts,
        "location": location_counts,
    }


# lấy danh sách tài sản có phân trang, bộ lọc và phân quyền theo user
def list_assets(
    page=1,
    per_page=10,
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
    current_user=None,
):
    # ép page và per_page về giới hạn an toàn
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))

    # tạo query từ các bộ lọc người dùng chọn
    filter_query = build_asset_query(
        search=search,
        asset_type=asset_type,
        department=department,
        status=status,
    )

    visibility_query = build_asset_visibility_query(current_user)

    # gộp query bộ lọc với query phân quyền
    query = merge_asset_queries(
        filter_query,
        visibility_query,
    )

    # đếm tổng số tài sản để tính tổng số trang
    total_items = count_assets(query)
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

    if page > total_pages:
        page = total_pages

    skip = (page - 1) * per_page

    # lấy dữ liệu của trang hiện tại từ database
    raw_items = find_assets(
        query=query,
        skip=skip,
        limit=per_page,
        sort_field="_id",
        sort_order=-1,
    )

    # chuẩn hóa dữ liệu trước khi trả về frontend
    items = [normalize_asset(item) for item in raw_items]

    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages,
        },
        "filter_counts": get_asset_filter_counts(current_user=current_user),
        "scope": {
            "view_all": user_can_view_all_assets(current_user),
            "role": current_user.get("role") if current_user else None,
            "user_id": str(current_user.get("_id")) if current_user else None,
            "employee_code": current_user.get("employee_code") if current_user else None,
        }
    }


# tìm 1 tài sản theo id hoặc mã tài sản
# vẫn kiểm tra quyền xem của user hiện tại
def find_asset(asset_id, current_user=None):
    # vừa tìm theo id/mã tài sản, vừa kiểm tra quyền xem
    asset_id_query = build_asset_id_query(asset_id)
    visibility_query = build_asset_visibility_query(current_user)

    query = merge_asset_queries(
        asset_id_query,
        visibility_query,
    )

    item = find_asset_by_query(query)

    if not item:
        return None

    return normalize_asset(item)


# xóa 1 tài sản theo id hoặc mã tài sản
def delete_asset(asset_id):
    query = build_asset_id_query(asset_id)
    result = delete_asset_by_query(query)

    return {
        "deleted": result.deleted_count > 0,
        "deleted_count": result.deleted_count,
    }


# thêm mới 1 tài sản
# có chuẩn hóa dữ liệu, validate và kiểm tra trùng mã tài sản
def add_asset(data):
    # chuẩn hóa rồi kiểm tra dữ liệu trước khi thêm
    data = normalize_asset_payload(data)
    errors = validate_asset_payload(data)

    if errors:
        return {
            "created": False,
            "message": "Dữ liệu không hợp lệ",
            "errors": errors,
            "status_code": 400,
        }

    # không cho thêm nếu mã tài sản đã tồn tại
    if asset_code_exists(data["asset_code"]):
        return {
            "created": False,
            "message": "Mã tài sản đã tồn tại",
            "status_code": 409,
        }

    # thêm vào database rồi lấy lại item vừa tạo
    result = insert_asset(data)
    created_item = find_asset_by_query({
        "_id": result.inserted_id
    })

    return {
        "created": True,
        "item": normalize_asset(created_item),
    }


# tạo dữ liệu dùng để cập nhật tài sản
# chỉ lấy những field frontend gửi lên, không tự sửa field khác
def build_update_asset_data(data):
    # nếu data rỗng thì dùng dict rỗng để xử lý an toàn
    data = data or {}
    update_data = {}

    # chỉ cập nhật mã tài sản nếu frontend có gửi asset_code
    if "asset_code" in data:
        asset_code = (data.get("asset_code") or "").strip()

        if not asset_code:
            return None, {
                "asset_code": "Mã tài sản là bắt buộc"
            }

        update_data["asset_code"] = asset_code

    # cập nhật tên tài sản, hỗ trợ cả asset_name và asset
    if "asset_name" in data or "asset" in data:
        asset_name = (
            data.get("asset_name")
            or data.get("asset")
            or ""
        ).strip()

        if not asset_name:
            return None, {
                "asset_name": "Tên tài sản là bắt buộc"
            }

        update_data["asset_name"] = asset_name
        update_data["asset"] = asset_name

    # cập nhật loại tài sản, hỗ trợ cả type và category
    if "type" in data or "category" in data:
        raw_type = (
            data.get("type")
            or data.get("category")
            or ""
        ).strip()

        if not raw_type:
            return None, {
                "type": "Loại tài sản là bắt buộc"
            }

        type_code = normalize_type_code(raw_type)
        update_data["type"] = type_code
        update_data["category"] = type_code

    # cập nhật trạng thái nếu frontend có gửi status
    if "status" in data:
        raw_status = (data.get("status") or "").strip()

        if not raw_status:
            return None, {
                "status": "Trạng thái là bắt buộc"
            }

        update_data["status"] = normalize_status_code(raw_status)

    # các field này không bắt buộc, có thì cập nhật, không có thì bỏ qua
    optional_text_fields = [
        "warranty",
        "spec",
        "notes",
        "department",
        "location",
        "user_id",
        "employee_code",
        "user",
        "receiver",
    ]

    for field in optional_text_fields:
        if field in data:
            update_data[field] = data.get(field) or ""

    # spec và notes đang dùng như 2 tên khác nhau của cùng 1 nội dung mô tả
    if "spec" in update_data and "notes" not in update_data:
        update_data["notes"] = update_data["spec"]

    if "notes" in update_data and "spec" not in update_data:
        update_data["spec"] = update_data["notes"]

    # có dữ liệu cập nhật thì cập nhật luôn thời gian sửa
    if update_data:
        update_data["updated_at"] = datetime.utcnow()

    return update_data, None


# kiểm tra mã tài sản mới có bị trùng với tài sản khác hay không
def check_duplicate_asset_code_for_update(asset_id, asset, new_asset_code):
    # nếu không đổi mã tài sản thì không cần kiểm tra trùng
    if not new_asset_code:
        return False

    old_asset_code = asset.get("asset_code")

    # nếu mã mới giống mã cũ thì không tính là trùng
    if old_asset_code == new_asset_code:
        return False

    current_object_id = asset.get("_id")

    duplicate_query = {
        "asset_code": new_asset_code
    }

    if current_object_id:
        duplicate_query["_id"] = {
            "$ne": current_object_id
        }

    existed_asset = find_asset_by_query(duplicate_query)

    return existed_asset is not None


# cập nhật thông tin 1 tài sản
# có kiểm tra quyền, validate dữ liệu và chống trùng mã tài sản
def update_asset(asset_id, data, current_user=None):
    # đảm bảo data luôn là dict để tránh lỗi khi xử lý
    if data is None:
        data = {}

    asset_id_query = build_asset_id_query(asset_id)
    visibility_query = build_asset_visibility_query(current_user)

    find_query = merge_asset_queries(
        asset_id_query,
        visibility_query,
    )

    # tìm tài sản trong phạm vi user được phép thao tác
    asset = find_asset_by_query(find_query)

    if not asset:
        return {
            "success": False,
            "message": "Không tìm thấy tài sản",
            "status_code": 404,
        }

    # tạo dữ liệu cập nhật và lấy lỗi nếu có
    update_data, errors = build_update_asset_data(data)

    if errors:
        return {
            "success": False,
            "message": "Dữ liệu không hợp lệ",
            "errors": errors,
            "status_code": 400,
        }

    if not update_data:
        return {
            "success": False,
            "message": "Không có dữ liệu để cập nhật",
            "status_code": 400,
        }

    new_asset_code = update_data.get("asset_code")

    # nếu đổi sang mã đã tồn tại thì báo lỗi
    if check_duplicate_asset_code_for_update(asset_id, asset, new_asset_code):
        return {
            "success": False,
            "message": "Mã tài sản đã tồn tại",
            "status_code": 409,
        }

    update_query = {
        "_id": asset.get("_id")
    }

    # cập nhật database rồi lấy lại dữ liệu mới nhất
    update_asset_by_query(update_query, update_data)

    updated_asset = find_asset_by_query(update_query)

    return {
        "success": True,
        "message": "Cập nhật tài sản thành công",
        "item": normalize_asset(updated_asset),
        "status_code": 200,
    }


# thêm nhiều tài sản cùng lúc
# item nào lỗi sẽ bị bỏ qua và trả về trong skipped_items
def add_many_assets(items):
    # API bulk bắt buộc body phải là danh sách
    if not isinstance(items, list):
        return {
            "created": False,
            "message": "Body phải là một mảng JSON",
            "inserted_count": 0,
            "status_code": 400,
        }

    if len(items) == 0:
        return {
            "created": False,
            "message": "Danh sách rỗng",
            "inserted_count": 0,
            "status_code": 400,
        }

    # normalized_items là danh sách hợp lệ sẽ được thêm
    # skipped_items là danh sách bị bỏ qua kèm lý do
    normalized_items = []
    skipped_items = []
    seen_asset_codes = set()

    # kiểm tra từng dòng dữ liệu trong danh sách upload
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            skipped_items.append({
                "index": index,
                "reason": "Item không phải object JSON",
            })
            continue

        normalized = normalize_asset_payload(item)
        errors = validate_asset_payload(normalized)

        if errors:
            skipped_items.append({
                "index": index,
                "asset_code": normalized.get("asset_code"),
                "reason": "Dữ liệu không hợp lệ",
                "errors": errors,
            })
            continue

        asset_code = normalized.get("asset_code")

        # kiểm tra trùng mã ngay trong chính file upload
        if asset_code in seen_asset_codes:
            skipped_items.append({
                "index": index,
                "asset_code": asset_code,
                "reason": "Mã tài sản bị trùng trong danh sách upload",
            })
            continue

        # kiểm tra mã tài sản đã tồn tại trong database hay chưa
        if asset_code_exists(asset_code):
            skipped_items.append({
                "index": index,
                "asset_code": asset_code,
                "reason": "Mã tài sản đã tồn tại",
            })
            continue

        seen_asset_codes.add(asset_code)
        normalized_items.append(normalized)

    if not normalized_items:
        return {
            "created": False,
            "message": "Không có dữ liệu hợp lệ để thêm",
            "inserted_count": 0,
            "skipped_items": skipped_items,
            "status_code": 400,
        }

    # thêm các item hợp lệ vào database
    result = insert_many_assets(normalized_items)
    created_items = find_assets_by_ids(result.inserted_ids)

    return {
        "created": True,
        "message": "Inserted successfully",
        "inserted_count": len(result.inserted_ids),
        "ids": [str(item_id) for item_id in result.inserted_ids],
        "items": [normalize_asset(item) for item in created_items],
        "skipped_items": skipped_items,
    }


# lấy danh sách loại tài sản hiện có kèm số lượng từng loại
def get_asset_type_options(current_user=None):
    visibility_query = build_asset_visibility_query(current_user)

    if visibility_query:
        cursor = find_assets(
            query=visibility_query,
            skip=0,
            limit=100000,
            sort_field="_id",
            sort_order=-1,
        )
    else:
        cursor = find_assets_for_counts()

    types = {}

    for item in cursor:
        raw_type = item.get("type") or item.get("category") or ""
        type_value = normalize_type_code(raw_type)

        if not type_value:
            continue

        types[type_value] = types.get(type_value, 0) + 1

    return {
        "items": [
            {
                "value": type_name,
                "count": count,
            }
            for type_name, count in sorted(types.items())
        ]
    }


# tìm người dùng để cấp phát tài sản
# có thể tìm bằng user_id, employee_code hoặc email
def find_user_for_assign(data):
    data = data or {}

    # frontend có thể gửi 1 trong 3 thông tin này để tìm user
    user_id = data.get("user_id") or data.get("id")
    employee_code = data.get("employee_code")
    email = data.get("email")

    # ưu tiên tìm theo user_id nếu là ObjectId hợp lệ
    if user_id and ObjectId.is_valid(user_id):
        return users_collection.find_one({
            "_id": ObjectId(user_id)
        })

    if employee_code:
        return users_collection.find_one({
            "employee_code": employee_code
        })

    if email:
        return users_collection.find_one({
            "email": email
        })

    return None


# cấp phát tài sản cho 1 người dùng
# sau khi cấp phát thì trạng thái tài sản chuyển thành using
def assign_asset(asset_id, data):
    # tìm tài sản cần cấp phát
    asset_query = build_asset_id_query(asset_id)
    asset = find_asset_by_query(asset_query)

    if not asset:
        return {
            "success": False,
            "message": "Không tìm thấy tài sản",
            "status_code": 404,
        }

    # tìm người dùng sẽ nhận tài sản
    user = find_user_for_assign(data)

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy người dùng để cấp phát",
            "status_code": 404,
        }

    # không cấp phát cho user đã ngưng hoạt động
    if user.get("status") == "NGUNG_HOAT_DONG":
        return {
            "success": False,
            "message": "Người dùng đã ngưng hoạt động, không thể cấp phát tài sản",
            "status_code": 400,
        }

    now = datetime.utcnow()

    # lưu thông tin người nhận vào tài sản
    update_data = {
        "user_id": str(user.get("_id")),
        "employee_code": user.get("employee_code") or "",
        "user": user.get("full_name") or "",
        "receiver": user.get("full_name") or "",
        "department": user.get("department") or "",
        "location": user.get("floor") or "",
        "status": "using",
        "assigned_at": now,
        "returned_at": "",
        "updated_at": now,
    }

    # cập nhật tài sản rồi lấy lại dữ liệu mới nhất
    update_asset_by_query(asset_query, update_data)

    updated_asset = find_asset_by_query(asset_query)

    return {
        "success": True,
        "message": "Cấp phát tài sản thành công",
        "item": normalize_asset(updated_asset),
        "status_code": 200,
    }


# thu hồi tài sản khỏi người đang sử dụng
# sau khi thu hồi thì tài sản chuyển về available
def unassign_asset(asset_id):
    asset_query = build_asset_id_query(asset_id)
    asset = find_asset_by_query(asset_query)

    if not asset:
        return {
            "success": False,
            "message": "Không tìm thấy tài sản",
            "status_code": 404,
        }

    now = datetime.utcnow()

    # xóa thông tin người nhận khỏi tài sản
    update_data = {
        "user_id": "",
        "employee_code": "",
        "user": "",
        "receiver": "",
        "department": "",
        "location": "",
        "status": "available",
        "returned_at": now,
        "updated_at": now,
    }

    update_asset_by_query(asset_query, update_data)

    updated_asset = find_asset_by_query(asset_query)

    return {
        "success": True,
        "message": "Thu hồi tài sản thành công",
        "item": normalize_asset(updated_asset),
        "status_code": 200,
    }


# tính phần trăm, nếu tổng bằng 0 thì trả về 0 để tránh lỗi chia cho 0
def _percent(value, total):
    if not total:
        return 0

    return round((value / total) * 100)


# lấy dữ liệu tổng quan tài sản để hiển thị trên dashboard
def get_dashboard_assets_overview(limit=4, current_user=None):
    # cố gắng ép limit về số nguyên
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 4

    limit = max(1, min(limit, 20))

    visibility_query = build_asset_visibility_query(current_user)

    # lấy số lượng tài sản theo trạng thái để tính thống kê
    counts = get_asset_filter_counts(current_user=current_user)
    status_counts = counts.get("status", {})

    total = status_counts.get("all", 0)
    using = status_counts.get("using", 0)
    available = status_counts.get("available", 0)
    maintenance = status_counts.get("maintenance", 0)
    broken = status_counts.get("broken", 0)

    problem = maintenance + broken

    # lấy vài tài sản mới nhất để hiển thị trên dashboard
    raw_items = find_assets(
        query=visibility_query,
        skip=0,
        limit=limit,
        sort_field="_id",
        sort_order=-1,
    )

    recent_assets = []

    # chuẩn hóa từng tài sản gần đây trước khi trả về
    for item in raw_items:
        asset = normalize_asset(item)
        status = asset.get("status") or "pending"

        recent_assets.append({
            "id": asset.get("id"),
            "asset_name": asset.get("asset_name") or asset.get("asset") or "",
            "asset_code": asset.get("asset_code") or "",
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "status_class": STATUS_BADGE_CLASSES.get(status, "status-free"),
            "user": (
                asset.get("user")
                or asset.get("receiver")
                or asset.get("department")
                or "—"
            ),
        })

    return {
        "stats": {
            "total": total,
            "using": using,
            "available": available,
            "maintenance": maintenance,
            "broken": broken,
            "problem": problem,
            "using_percent": _percent(using, total),
            "available_percent": _percent(available, total),
            "problem_percent": _percent(problem, total),
        },
        "recent_assets": recent_assets,
    }
# cấu hình các hành động được phép đổi trạng thái tài sản
# mỗi action có trạng thái bắt đầu, trạng thái sau khi đổi và câu thông báo
ASSET_STATUS_ACTIONS = {
    "send_maintenance": {
        "from": ["broken"],
        "to": "maintenance",
        "message": "Đã chuyển tài sản sang trạng thái Bảo trì",
    },
    "reject_broken": {
        "from": ["broken"],
        "to": "broken",
        "message": "Đã từ chối, tài sản vẫn ở trạng thái Hỏng",
    },
    "maintenance_done": {
        "from": ["maintenance"],
        "to": "available",
        "message": "Đã hoàn thành bảo trì, tài sản chuyển sang Chưa sử dụng",
    },
    "maintenance_not_done": {
        "from": ["maintenance"],
        "to": "maintenance",
        "message": "Bảo trì chưa hoàn thành, tài sản vẫn ở trạng thái Bảo trì",
    },
}


# đổi trạng thái tài sản theo action đã được cấu hình sẵn
def update_asset_status_action(asset_id, action, current_user=None):
    # lấy rule tương ứng với action frontend gửi lên
    rule = ASSET_STATUS_ACTIONS.get(action)

    if not rule:
        return {
            "success": False,
            "message": "Action không hợp lệ",
            "status_code": 400,
        }

    asset_id_query = build_asset_id_query(asset_id)
    visibility_query = build_asset_visibility_query(current_user)

    find_query = merge_asset_queries(
        asset_id_query,
        visibility_query,
    )

    asset = find_asset_by_query(find_query)

    if not asset:
        return {
            "success": False,
            "message": "Không tìm thấy tài sản",
            "status_code": 404,
        }

    # chỉ cho đổi trạng thái nếu tài sản đang ở trạng thái được phép
    current_status = normalize_status_code(asset.get("status"))

    if current_status not in rule["from"]:
        return {
            "success": False,
            "message": f"Không thể thực hiện action này khi tài sản đang ở trạng thái {STATUS_LABELS.get(current_status, current_status)}",
            "status_code": 400,
        }

    now = datetime.utcnow()

    # dữ liệu cập nhật chỉ gồm trạng thái mới và thời gian cập nhật
    update_data = {
        "status": rule["to"],
        "updated_at": now,
    }

    update_query = {
        "_id": asset.get("_id")
    }

    update_asset_by_query(update_query, update_data)

    updated_asset = find_asset_by_query(update_query)

    return {
        "success": True,
        "message": rule["message"],
        "item": normalize_asset(updated_asset),
        "old_status": current_status,
        "new_status": rule["to"],
        "action": action,
        "status_code": 200,
    }