import hashlib

def get_str_hash(text: str) -> str:
    text_bytes = text.encode("utf-8")

    hash_object = hashlib.sha256(text_bytes)

    return hash_object.hexdigest()