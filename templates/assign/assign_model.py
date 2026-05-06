from mongo import assets_collection


def count_assign_assets(query=None):
    return assets_collection.count_documents(query or {})


def find_assign_assets(
    query=None,
    skip=0,
    limit=10,
    sort_field="_id",
    sort_order=-1,
):
    return list(
        assets_collection
        .find(query or {})
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
    )


def find_assign_assets_for_counts(query=None):
    return assets_collection.find(query or {})


def find_assign_asset_by_query(query):
    return assets_collection.find_one(query)


def delete_assign_asset_by_query(query):
    return assets_collection.delete_one(query)


def update_assign_asset_by_query(query, update_data):
    return assets_collection.update_one(query, update_data)