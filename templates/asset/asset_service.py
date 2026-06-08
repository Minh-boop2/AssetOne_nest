# file này chứa phần xử lý chính cho chức năng quản lý tài sản
# API sẽ gọi các hàm trong file này để tìm, thêm, sửa, xóa và cấp phát tài sản
from bson import ObjectId
from datetime import datetime, timedelta
import math
import re

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


# dùng users_collection để tìm người dùng khi cấp phát tài sản và tìm người nhận notification
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
    update_many_assets_by_query,
)


# import các hàm gửi notification cho nhân viên khi bảo trì hoàn tất / chưa hoàn tất
from templates.notification.notification_service import (
    notify_admins,
    notify_staff_asset_maintenance_completed,
    notify_staff_asset_maintenance_not_completed,
    notify_staff_asset_warranty_expiring,
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


# THÊM: danh sách phòng ban cố định của hệ thống
# dùng để dropdown Phòng ban luôn hiển thị đủ, không phụ thuộc tài sản có đang gắn phòng hay không
DEFAULT_DEPARTMENTS = [
    "Phòng Hành Chính",
    "Phòng Kỹ Thuật",
    "Phòng IT",
    "Phòng Thiết Kế",
    "Phòng Kế Toán",
    "Phòng Nhân Sự",
]


# số ngày trước khi hết hạn bảo hành thì hệ thống gửi thông báo
WARRANTY_REMINDER_DAYS_BEFORE = 30

# múi giờ dùng để tính hạn bảo hành theo ngày hiện tại ở Việt Nam
VIETNAM_TIMEZONE = "Asia/Ho_Chi_Minh"

# mã tài sản tự sinh khi tạo mới nếu frontend không gửi asset_code
ASSET_CODE_PREFIX = "Assets-"
ASSET_CODE_DIGITS = 5


# lấy thời gian hiện tại theo Việt Nam
# trả về datetime không kèm timezone để đồng bộ với dữ liệu đang lưu dạng datetime.utcnow()
def get_vietnam_now():
    if ZoneInfo:
        return datetime.now(ZoneInfo(VIETNAM_TIMEZONE)).replace(tzinfo=None)

    return datetime.utcnow() + timedelta(hours=7)


# lấy ngày hiện tại theo Việt Nam
def get_vietnam_today():
    return get_vietnam_now().date()


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


# chuẩn hóa field ngày từ frontend
# chỉ chấp nhận dạng YYYY-MM-DD, đúng format của input type="date"
def normalize_date_field(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    value = str(value).strip()

    if not value:
        return ""

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None

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


# THÊM: chuẩn hóa danh sách loại tài sản khi filter chọn nhiều
# hỗ trợ cả dạng list ["laptop", "pc"] và chuỗi "laptop,pc"
def parse_asset_types_filter(asset_types=None):
    if not asset_types:
        return []

    if isinstance(asset_types, (list, tuple, set)):
        values = asset_types
    else:
        values = str(asset_types).split(",")

    clean_values = []

    for value in values:
        value = str(value or "").strip()

        if value and value != "Tất cả" and value not in clean_values:
            clean_values.append(value)

    return clean_values


# THÊM: lấy toàn bộ alias của nhiều loại tài sản
# dùng cho filter chọn nhiều loại trong trang tài sản
def aliases_for_types(asset_types=None):
    selected_types = parse_asset_types_filter(asset_types)

    if not selected_types:
        return None

    alias_values = []

    for asset_type in selected_types:
        values = aliases_for_type(asset_type) or []

        for value in values:
            if value not in alias_values:
                alias_values.append(value)

    return alias_values


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
    row["warranty_reminder_sent"] = bool(row.get("warranty_reminder_sent"))
    row["warranty_reminder_sent_at"] = serialize_datetime(row.get("warranty_reminder_sent_at"))
    row["spec"] = row.get("spec") or row.get("notes") or ""
    row["notes"] = row.get("notes") or row.get("spec") or ""

    row["assigned_at"] = serialize_datetime(row.get("assigned_at"))
    row["returned_at"] = serialize_datetime(row.get("returned_at"))
    row["created_at"] = serialize_datetime(row.get("created_at"))
    row["updated_at"] = serialize_datetime(row.get("updated_at"))

    # bỏ _id gốc vì ObjectId không trả JSON trực tiếp đẹp bằng string id
    row.pop("_id", None)

    return row


# tự sinh mã tài sản dạng Assets-00001, Assets-00002, ...
def generate_asset_code(reserved_codes=None):
    reserved_codes = set(reserved_codes or [])

    pattern = f"^{re.escape(ASSET_CODE_PREFIX)}[0-9]{{{ASSET_CODE_DIGITS}}}$"

    latest_assets = find_assets(
        query={
            "asset_code": {
                "$regex": pattern
            }
        },
        skip=0,
        limit=1,
        sort_field="asset_code",
        sort_order=-1,
    )

    latest_number = 0

    for asset in latest_assets:
        asset_code = asset.get("asset_code") or ""
        number_text = asset_code.replace(ASSET_CODE_PREFIX, "", 1)

        if number_text.isdigit():
            latest_number = int(number_text)

    max_number = int("9" * ASSET_CODE_DIGITS)

    for number in range(latest_number + 1, max_number + 1):
        asset_code = f"{ASSET_CODE_PREFIX}{number:0{ASSET_CODE_DIGITS}d}"

        if asset_code in reserved_codes:
            continue

        if not asset_code_exists(asset_code):
            return asset_code

    raise ValueError("Không thể sinh mã tài sản mới")


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

    data["warranty"] = normalize_date_field(data.get("warranty"))
    data["warranty_reminder_sent"] = bool(data.get("warranty_reminder_sent", False))
    data["warranty_reminder_sent_at"] = data.get("warranty_reminder_sent_at") or ""
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

    if data.get("warranty") is None:
        errors["warranty"] = "Ngày bảo hành phải đúng định dạng YYYY-MM-DD"

    return errors


# tạo query lọc danh sách tài sản theo tìm kiếm, loại, nhiều loại, phòng ban và trạng thái
def build_asset_query(
    search="",
    asset_type="Tất cả",
    asset_types=None,
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

    # THÊM: ưu tiên lọc nhiều loại nếu frontend gửi types=laptop,pc,...
    # nếu không có types thì vẫn dùng logic cũ asset_type như trước
    multi_type_values = aliases_for_types(asset_types)

    if multi_type_values:
        conditions.append({
            "$or": [
                {
                    "type": {
                        "$in": multi_type_values
                    }
                },
                {
                    "category": {
                        "$in": multi_type_values
                    }
                },
            ]
        })
    else:
        type_values = aliases_for_type(asset_type)

        if type_values:
            conditions.append({
                "$or": [
                    {
                        "type": {
                            "$in": type_values
                        }
                    },
                    {
                        "category": {
                            "$in": type_values
                        }
                    },
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

    # THÊM: nạp đủ phòng ban mặc định vào filter
    # phòng nào chưa có tài sản vẫn hiển thị với số lượng 0
    for dept in DEFAULT_DEPARTMENTS:
        department_counts[dept] = 0

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
    asset_types=None,
    department="Tất cả",
    status="Tất cả",
    current_user=None,
):
    # ép page và per_page về giới hạn an toàn
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))

    # THÊM: hỗ trợ lọc nhiều loại tài sản bằng asset_types
    # nếu asset_types có dữ liệu thì build_asset_query sẽ ưu tiên lọc nhiều loại
    filter_query = build_asset_query(
        search=search,
        asset_type=asset_type,
        asset_types=asset_types,
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

    selected_types = parse_asset_types_filter(asset_types)

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
            # THÊM: trả thêm danh sách loại đang lọc để frontend / dashboard có thể dùng lại
            "selected_types": selected_types,
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
# có chuẩn hóa dữ liệu, tự sinh mã tài sản, validate và kiểm tra trùng mã tài sản
def add_asset(data):
    data = normalize_asset_payload(data)

    # Nếu frontend không gửi mã tài sản thì backend tự sinh dạng Assets-00001.
    if not data.get("asset_code"):
        try:
            data["asset_code"] = generate_asset_code()
        except ValueError as error:
            return {
                "created": False,
                "message": str(error),
                "status_code": 500,
            }

    errors = validate_asset_payload(data)

    if errors:
        return {
            "created": False,
            "message": "Dữ liệu không hợp lệ",
            "errors": errors,
            "status_code": 400,
        }

    if asset_code_exists(data["asset_code"]):
        return {
            "created": False,
            "message": "Mã tài sản đã tồn tại",
            "status_code": 409,
        }

    result = insert_asset(data)
    created_item = find_asset_by_query({
        "_id": result.inserted_id
    })

    warranty_notification = safe_notify_asset_warranty_if_expiring_soon(
        asset=created_item,
        current_user=None,
        notify_owner=True,
    )

    return {
        "created": True,
        "message": "Tạo tài sản thành công",
        "item": normalize_asset(created_item),
        "warranty_notification": warranty_notification,
        "status_code": 201,
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

    # cập nhật ngày bảo hành, chỉ nhận dạng YYYY-MM-DD
    if "warranty" in data:
        warranty = normalize_date_field(data.get("warranty"))

        if warranty is None:
            return None, {
                "warranty": "Ngày bảo hành phải đúng định dạng YYYY-MM-DD"
            }

        update_data["warranty"] = warranty
        update_data["warranty_reminder_sent"] = False
        update_data["warranty_reminder_sent_at"] = ""

    # các field này không bắt buộc, có thì cập nhật, không có thì bỏ qua
    optional_text_fields = [
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

    # lưu lại trạng thái cũ để biết có phải vừa hoàn thành bảo trì hay không
    old_status = normalize_status_code(asset.get("status"))

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
    normalized_asset = normalize_asset(updated_asset)

    # Frontend hiện tại đang gọi PUT /api/assets/<id>, không gọi update_asset_status_action().
    # Vì vậy cần bắt trạng thái bảo trì ngay tại update_asset() để vẫn gửi notification.
    new_status = normalize_status_code(updated_asset.get("status"))
    maintenance_action = None

    if "status" in update_data and old_status == "maintenance":
        # Frontend đang gửi trạng thái "Hoàn thành", normalize_status_code sẽ đổi thành "using".
        # Vì vậy hoàn thành bảo trì có thể là using hoặc available.
        if new_status in ["using", "available"]:
            maintenance_action = "maintenance_done"

        # Frontend đang gửi "Không hoàn thành" thành trạng thái broken.
        # Vì vậy broken cũng phải hiểu là bảo trì chưa hoàn tất.
        elif new_status in ["broken", "maintenance"]:
            maintenance_action = "maintenance_not_done"

    if maintenance_action:
        notify_staff_after_maintenance_action(
            asset=asset,
            action=maintenance_action,
            current_user=current_user
        )

    warranty_notification = None

    # nếu vừa sửa ngày bảo hành và ngày đó nằm trong khoảng từ hôm nay đến 30 ngày tới
    # thì gửi notification ngay, không cần chờ job quét định kỳ
    if "warranty" in update_data:
        warranty_notification = safe_notify_asset_warranty_if_expiring_soon(
            asset=updated_asset,
            current_user=current_user,
            notify_owner=True,
        )

    return {
        "success": True,
        "message": "Cập nhật tài sản thành công",
        "item": normalized_asset,
        "warranty_notification": warranty_notification,
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

    normalized_items = []
    skipped_items = []
    seen_asset_codes = set()

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            skipped_items.append({
                "index": index,
                "reason": "Item không phải object JSON",
            })
            continue

        normalized = normalize_asset_payload(item)

        # Nếu file import không có mã tài sản thì tự sinh mã dạng Assets-00001.
        if not normalized.get("asset_code"):
            try:
                normalized["asset_code"] = generate_asset_code(
                    reserved_codes=seen_asset_codes
                )
            except ValueError as error:
                skipped_items.append({
                    "index": index,
                    "reason": str(error),
                })
                continue

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

        if asset_code in seen_asset_codes:
            skipped_items.append({
                "index": index,
                "asset_code": asset_code,
                "reason": "Mã tài sản bị trùng trong danh sách upload",
            })
            continue

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

    result = insert_many_assets(normalized_items)
    created_items = find_assets_by_ids(result.inserted_ids)

    warranty_notifications = []

    for created_item in created_items:
        warranty_notification = safe_notify_asset_warranty_if_expiring_soon(
            asset=created_item,
            current_user=None,
            notify_owner=True,
        )

        if warranty_notification and warranty_notification.get("notified"):
            warranty_notifications.append(warranty_notification)

    return {
        "created": True,
        "message": "Inserted successfully",
        "inserted_count": len(result.inserted_ids),
        "ids": [str(item_id) for item_id in result.inserted_ids],
        "items": [normalize_asset(item) for item in created_items],
        "skipped_items": skipped_items,
        "warranty_notifications": warranty_notifications,
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
    if user_id and ObjectId.is_valid(str(user_id)):
        return users_collection.find_one({
            "_id": ObjectId(str(user_id))
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


# tạo điều kiện tìm tất cả tài sản đang gắn với user bị ngưng hoạt động
# ưu tiên user_id và employee_code để tránh nhầm người trùng tên
def build_inactive_user_asset_query(user=None, user_id="", employee_code="", email="", full_name=""):
    user = user or {}

    user_id = str(
        user.get("_id")
        or user.get("id")
        or user.get("user_id")
        or user_id
        or ""
    ).strip()

    employee_code = (
        user.get("employee_code")
        or employee_code
        or ""
    ).strip()

    email = (
        user.get("email")
        or email
        or ""
    ).strip()

    full_name = (
        user.get("full_name")
        or user.get("name")
        or full_name
        or ""
    ).strip()

    owner_conditions = []

    # tìm theo user_id là chính xác nhất
    if user_id:
        owner_conditions.append({
            "user_id": user_id
        })

    # tìm theo mã nhân viên để hỗ trợ dữ liệu cũ chưa lưu user_id
    if employee_code:
        owner_conditions.append({
            "employee_code": employee_code
        })

    # tìm theo email nếu tài sản cũ có lưu email
    if email:
        owner_conditions.append({
            "email": email
        })

    # chỉ fallback theo tên khi không có user_id / employee_code / email
    # cách này giúp hạn chế nhầm người nếu công ty có nhân viên trùng tên
    if not owner_conditions and full_name:
        owner_conditions.extend([
            {
                "receiver": full_name
            },
            {
                "user": full_name
            },
        ])

    if not owner_conditions:
        return None

    return {
        "$or": owner_conditions
    }


# thu hồi toàn bộ tài sản khi tài khoản user bị ngưng hoạt động
# hàm này chỉ update thêm trạng thái tài sản, không xóa tài sản và không xóa dữ liệu lịch sử cũ
def release_assets_when_user_inactive(user=None, user_id="", employee_code="", email="", full_name=""):
    asset_query = build_inactive_user_asset_query(
        user=user,
        user_id=user_id,
        employee_code=employee_code,
        email=email,
        full_name=full_name,
    )

    if not asset_query:
        return {
            "success": False,
            "message": "Thiếu thông tin người dùng để thu hồi tài sản",
            "matched_count": 0,
            "modified_count": 0,
            "items": [],
            "status_code": 400,
        }

    # chỉ lấy những tài sản còn đang gắn thông tin người dùng
    # nếu tài sản đã trống sẵn thì không cần cập nhật lại
    assigned_query = {
        "$and": [
            asset_query,
            {
                "$or": [
                    {
                        "user_id": {
                            "$ne": ""
                        }
                    },
                    {
                        "employee_code": {
                            "$ne": ""
                        }
                    },
                    {
                        "user": {
                            "$ne": ""
                        }
                    },
                    {
                        "receiver": {
                            "$ne": ""
                        }
                    },
                    {
                        "status": {
                            "$in": STATUS_ALIASES["using"]
                        }
                    },
                ]
            },
        ]
    }

    assigned_assets = find_assets(
        query=assigned_query,
        skip=0,
        limit=100000,
        sort_field="_id",
        sort_order=-1,
    )

    if not assigned_assets:
        return {
            "success": True,
            "message": "Người dùng không còn tài sản nào cần thu hồi",
            "matched_count": 0,
            "modified_count": 0,
            "items": [],
            "status_code": 200,
        }

    now = datetime.utcnow()

    asset_ids = [
        item.get("_id")
        for item in assigned_assets
        if item.get("_id")
    ]

    # tài khoản ngưng hoạt động thì tài sản quay về trạng thái chưa sử dụng
    # đồng thời xóa thông tin người đang nhận để tránh hiển thị sai ở trang tài sản
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

    update_query = {
        "_id": {
            "$in": asset_ids
        }
    }

    result = update_many_assets_by_query(
        update_query,
        update_data,
    )

    updated_assets = find_assets_by_ids(asset_ids)

    return {
        "success": True,
        "message": "Đã thu hồi tài sản của tài khoản ngưng hoạt động",
        "matched_count": result.matched_count,
        "modified_count": result.modified_count,
        "items": [normalize_asset(item) for item in updated_assets],
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


# lấy id của người đang thao tác để lưu vào created_by của notification
def get_current_actor_id(current_user=None):
    if not current_user:
        return None

    actor_id = (
        current_user.get("_id")
        or current_user.get("id")
        or current_user.get("user_id")
        or ""
    )

    if not actor_id:
        return None

    return str(actor_id)


# tìm user nhận notification từ dữ liệu asset
# Ưu tiên user_id. Nếu user_id rỗng thì tìm bằng employee_code, email, hoặc tên người nhận.
def find_notification_recipient_user_id_from_asset(asset):
    if not asset:
        return None

    user_id = asset.get("user_id")

    if user_id and ObjectId.is_valid(str(user_id)):
        user = users_collection.find_one({
            "_id": ObjectId(str(user_id)),
            "status": {"$ne": "NGUNG_HOAT_DONG"}
        })

        if user:
            return str(user.get("_id"))

    employee_code = asset.get("employee_code")

    if employee_code:
        user = users_collection.find_one({
            "employee_code": employee_code,
            "status": {"$ne": "NGUNG_HOAT_DONG"}
        })

        if user:
            return str(user.get("_id"))

    email = asset.get("email")

    if email:
        user = users_collection.find_one({
            "email": email,
            "status": {"$ne": "NGUNG_HOAT_DONG"}
        })

        if user:
            return str(user.get("_id"))

    receiver_name = (
        asset.get("receiver")
        or asset.get("user")
        or ""
    ).strip()

    if receiver_name:
        user = users_collection.find_one({
            "full_name": receiver_name,
            "status": {"$ne": "NGUNG_HOAT_DONG"}
        })

        if user:
            return str(user.get("_id"))

    return None


# gửi notification cho nhân viên khi bảo trì hoàn tất hoặc chưa hoàn tất
def notify_staff_after_maintenance_action(asset, action, current_user=None):
    if not asset:
        return None

    recipient_user_id = find_notification_recipient_user_id_from_asset(asset)

    if not recipient_user_id:
        return None

    asset_id = asset.get("_id") or asset.get("asset_code")
    asset_name = (
        asset.get("asset_name")
        or asset.get("asset")
        or asset.get("asset_code")
        or "tài sản"
    )
    actor_id = get_current_actor_id(current_user)

    if action == "maintenance_done":
        return notify_staff_asset_maintenance_completed(
            recipient_user_id=recipient_user_id,
            asset_id=asset_id,
            asset_name=asset_name,
            completed_by=actor_id
        )

    if action == "maintenance_not_done":
        return notify_staff_asset_maintenance_not_completed(
            recipient_user_id=recipient_user_id,
            asset_id=asset_id,
            asset_name=asset_name,
            checked_by=actor_id
        )

    return None

# lấy thông tin cơ bản của tài sản để đưa vào notification bảo hành
def build_warranty_notification_asset_data(asset):
    asset = asset or {}

    asset_id = asset.get("_id") or asset.get("id") or asset.get("asset_code")
    asset_code = asset.get("asset_code") or ""
    asset_name = (
        asset.get("asset_name")
        or asset.get("asset")
        or asset_code
        or "tài sản"
    )
    warranty_date = asset.get("warranty") or ""

    owner_name = (
        asset.get("receiver")
        or asset.get("user")
        or asset.get("employee_code")
        or ""
    )

    return {
        "asset_id": str(asset_id) if asset_id else None,
        "asset_code": asset_code,
        "asset_name": asset_name,
        "warranty_date": warranty_date,
        "owner_name": owner_name,
    }


# đổi ngày bảo hành dạng YYYY-MM-DD thành date để so sánh
def parse_warranty_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    value = str(value).strip()

    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# kiểm tra ngày bảo hành có nằm từ hôm nay đến N ngày tới theo giờ Việt Nam hay không
def is_asset_warranty_expiring_soon(asset, days_before=WARRANTY_REMINDER_DAYS_BEFORE):
    try:
        days_before = int(days_before)
    except (TypeError, ValueError):
        days_before = WARRANTY_REMINDER_DAYS_BEFORE

    days_before = max(1, min(days_before, 365))

    warranty_date = parse_warranty_date((asset or {}).get("warranty"))

    if not warranty_date:
        return False

    today = get_vietnam_today()
    target_date = today + timedelta(days=days_before)

    return today <= warranty_date <= target_date


# gửi notification bảo hành cho toàn bộ ADMIN
# không cần tài sản phải có user_id / employee_code / receiver
def notify_admins_after_warranty_expiring(asset, current_user=None):
    if not asset:
        return []

    data = build_warranty_notification_asset_data(asset)
    actor_id = get_current_actor_id(current_user)

    message = (
        f"Tài sản {data['asset_name']} "
        f"sẽ hết hạn bảo hành vào ngày {data['warranty_date']}."
    )

    if data.get("asset_code"):
        message += f" Mã tài sản: {data['asset_code']}."

    if data.get("owner_name"):
        message += f" Người đang sở hữu: {data['owner_name']}."

    return notify_admins(
        title="Tài sản sắp hết hạn bảo hành",
        message=message,
        notification_type="asset_warranty_expiring_admin",
        data={
            "asset_id": data.get("asset_id"),
            "asset_code": data.get("asset_code"),
            "asset_name": data.get("asset_name"),
            "warranty_date": data.get("warranty_date"),
            "owner_name": data.get("owner_name"),
            "status": "warranty_expiring",
            "visible_for_roles": ["ADMIN"],
        },
        created_by=actor_id,
    )


# gửi thêm notification cho người đang sở hữu tài sản nếu tìm được user
# phần này chỉ là bổ sung, không ảnh hưởng việc báo cho ADMIN
def notify_owner_after_warranty_expiring(asset, current_user=None):
    if not asset:
        return None

    recipient_user_id = find_notification_recipient_user_id_from_asset(asset)

    if not recipient_user_id:
        return None

    data = build_warranty_notification_asset_data(asset)

    return notify_staff_asset_warranty_expiring(
        recipient_user_id=recipient_user_id,
        asset_id=data.get("asset_id"),
        asset_name=data.get("asset_name"),
        warranty_date=data.get("warranty_date"),
        created_by=get_current_actor_id(current_user),
    )


# gửi notification cho 1 tài sản nếu ngày bảo hành còn từ hôm nay đến N ngày tới theo giờ Việt Nam
# hàm này dùng cho cả tạo mới, cập nhật và job quét toàn bộ
def notify_asset_warranty_if_expiring_soon(
    asset,
    current_user=None,
    days_before=WARRANTY_REMINDER_DAYS_BEFORE,
    notify_owner=True,
    force=False,
):
    if not asset:
        return {
            "notified": False,
            "reason": "Không có dữ liệu tài sản",
        }

    if not asset.get("_id"):
        return {
            "notified": False,
            "asset_code": asset.get("asset_code") or "",
            "reason": "Thiếu _id tài sản",
        }

    if asset.get("warranty_reminder_sent") is True and not force:
        return {
            "notified": False,
            "asset_id": str(asset.get("_id")),
            "asset_code": asset.get("asset_code") or "",
            "reason": "Tài sản đã gửi notification bảo hành trước đó",
        }

    if not is_asset_warranty_expiring_soon(asset, days_before=days_before):
        return {
            "notified": False,
            "asset_id": str(asset.get("_id")),
            "asset_code": asset.get("asset_code") or "",
            "warranty": asset.get("warranty") or "",
            "reason": "Ngày bảo hành không nằm trong khoảng cần thông báo",
        }

    asset_data = build_warranty_notification_asset_data(asset)

    admin_notifications = notify_admins_after_warranty_expiring(
        asset=asset,
        current_user=current_user,
    )

    if not admin_notifications:
        return {
            "notified": False,
            "asset_id": str(asset.get("_id")),
            "asset_code": asset_data.get("asset_code") or "",
            "asset_name": asset_data.get("asset_name") or "",
            "warranty": asset_data.get("warranty_date") or "",
            "reason": "Không tìm thấy ADMIN để nhận notification",
        }

    owner_notification = None

    if notify_owner:
        owner_notification = notify_owner_after_warranty_expiring(
            asset=asset,
            current_user=current_user,
        )

    now = get_vietnam_now()

    update_asset_by_query(
        {
            "_id": asset.get("_id")
        },
        {
            "warranty_reminder_sent": True,
            "warranty_reminder_sent_at": now,
            "updated_at": now,
        }
    )

    return {
        "notified": True,
        "asset_id": str(asset.get("_id")),
        "asset_code": asset_data.get("asset_code") or "",
        "asset_name": asset_data.get("asset_name") or "",
        "warranty": asset_data.get("warranty_date") or "",
        "owner_name": asset_data.get("owner_name") or "",
        "admin_notification_count": len(admin_notifications),
        "owner_notified": owner_notification is not None,
    }


# gọi notification bảo hành an toàn để lỗi notification không làm fail API tạo/sửa tài sản
def safe_notify_asset_warranty_if_expiring_soon(
    asset,
    current_user=None,
    days_before=WARRANTY_REMINDER_DAYS_BEFORE,
    notify_owner=True,
    force=False,
):
    try:
        return notify_asset_warranty_if_expiring_soon(
            asset=asset,
            current_user=current_user,
            days_before=days_before,
            notify_owner=notify_owner,
            force=force,
        )
    except Exception as error:
        return {
            "notified": False,
            "asset_id": str((asset or {}).get("_id") or ""),
            "asset_code": (asset or {}).get("asset_code") or "",
            "reason": "Gửi notification bảo hành bị lỗi nhưng tài sản vẫn được tạo/cập nhật thành công",
            "error": str(error),
        }


# kiểm tra tất cả tài sản còn tối đa 30 ngày nữa hết bảo hành theo ngày hiện tại Việt Nam
# quét cả tài sản mới tạo và tài sản đang có sẵn trong hệ thống
# mặc định luôn gửi cho toàn bộ ADMIN, có thể gửi thêm cho người đang sở hữu bằng notify_owner=True
def check_assets_warranty_expiring_soon(
    current_user=None,
    days_before=WARRANTY_REMINDER_DAYS_BEFORE,
    notify_owner=True,
):
    try:
        days_before = int(days_before)
    except (TypeError, ValueError):
        days_before = WARRANTY_REMINDER_DAYS_BEFORE

    days_before = max(1, min(days_before, 365))

    today = get_vietnam_today()
    target_date = today + timedelta(days=days_before)

    today_text = today.strftime("%Y-%m-%d")
    target_text = target_date.strftime("%Y-%m-%d")

    query = {
        "$and": [
            {
                "warranty": {
                    "$gte": today_text,
                    "$lte": target_text
                }
            },
            {
                "warranty": {
                    "$ne": ""
                }
            },
            {
                "warranty_reminder_sent": {
                    "$ne": True
                }
            },
        ]
    }

    assets = find_assets(
        query=query,
        skip=0,
        limit=100000,
        sort_field="warranty",
        sort_order=1,
    )

    notified_items = []
    skipped_items = []
    admin_notified_count = 0
    owner_notified_count = 0

    for asset in assets:
        result = notify_asset_warranty_if_expiring_soon(
            asset=asset,
            current_user=current_user,
            days_before=days_before,
            notify_owner=notify_owner,
        )

        if result.get("notified"):
            notified_items.append(result)
            admin_notified_count += result.get("admin_notification_count", 0)

            if result.get("owner_notified"):
                owner_notified_count += 1
        else:
            skipped_items.append(result)

    return {
        "success": True,
        "message": "Đã quét tất cả tài sản sắp hết hạn bảo hành",
        "timezone": VIETNAM_TIMEZONE,
        "from_date": today_text,
        "to_date": target_text,
        "days_before": days_before,
        "notify_owner": bool(notify_owner),
        "asset_notified_count": len(notified_items),
        "admin_notified_count": admin_notified_count,
        "owner_notified_count": owner_notified_count,
        "skipped_count": len(skipped_items),
        "notified_items": notified_items,
        "skipped_items": skipped_items,
        "status_code": 200,
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
    normalized_asset = normalize_asset(updated_asset)

    # Gửi notification cho nhân viên khi admin/quản lý bấm Hoàn thành hoặc Không hoàn thành bảo trì.
    # Hàm này có fallback tìm user theo employee_code / email / receiver nếu asset.user_id bị rỗng.
    notify_staff_after_maintenance_action(
        asset=asset,
        action=action,
        current_user=current_user
    )

    return {
        "success": True,
        "message": rule["message"],
        "item": normalized_asset,
        "old_status": current_status,
        "new_status": rule["to"],
        "action": action,
        "status_code": 200,
    }