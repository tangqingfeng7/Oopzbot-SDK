def shorten_text(value: str, limit: int = 200) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]
