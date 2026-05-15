from mongo import assets_collection

# đếm số lượng tài sản, có thể theo điều kiện query
def count_assets(query=None):
    return assets_collection.count_documents(query or {})

# tìm danh sách tài sản với phân trang, sắp xếp
def find_assets(query=None, skip=0, limit=10, sort_field="_id", sort_order=-1):
    return list(
        assets_collection
        .find(query or {})
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
    )

# tìm các trường để thống kê loại, category, trạng thái, phòng ban, vị trí
def find_assets_for_counts():
    return assets_collection.find({}, {
        "type": 1,
        "category": 1,
        "status": 1,
        "department": 1,
        "location": 1,
    })

# tìm 1 tài sản theo query
def find_asset_by_query(query):
    return assets_collection.find_one(query)

# xóa 1 tài sản theo query
def delete_asset_by_query(query):
    return assets_collection.delete_one(query)

# thêm 1 tài sản mới
def insert_asset(data):
    return assets_collection.insert_one(data)

# thêm nhiều tài sản cùng lúc
def insert_many_assets(items):
    return assets_collection.insert_many(items)

# tìm nhiều tài sản theo danh sách _id
def find_assets_by_ids(ids):
    return list(assets_collection.find({
        "_id": {"$in": ids}
    }))

# kiểm tra mã tài sản đã tồn tại hay chưa
def asset_code_exists(asset_code):
    return assets_collection.find_one({
        "asset_code": asset_code
    }) is not None

# cập nhật 1 tài sản theo query
def update_asset_by_query(query, update_data):
    return assets_collection.update_one(
        query,
        {
            "$set": update_data
        }
    )