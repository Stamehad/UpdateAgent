from typing import TypedDict, Optional, Dict

class Post(TypedDict, total=False):
    id: str
    kind: str            # "blog" | "video" | "paper" | "tweet"
    source_key: str
    title: str
    url: str
    published: str       # ISO8601-ish
    author: Optional[str]
    text: str
    metadata: Dict