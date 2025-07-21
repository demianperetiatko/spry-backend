def get_member_permissions(member):
    return [
        "members:view",
        "members:create",
        "members:edit",
        "members:delete",
        "teams:view",
        "teams:create",
        "teams:edit",
        "teams:delete",
        "analytics-organization:view",
        "analytics-members:view"
        "costs:view",
    ]

def member_has_permissions(member, action):
    has_permissions = action in get_member_permissions(member)
    return has_permissions