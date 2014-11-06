def es_format_address_list(addresses):
    if addresses is None:
        return []
    return [email for name, email in addresses]


def es_format_tags_list(tags):
    if tags is None:
        return []
    return [tag.name for tag in tags]
