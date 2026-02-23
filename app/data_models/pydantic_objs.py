from pydantic import BaseModel
from typing import Optional

class SearchResult(BaseModel):
    filename: str
    url: str
    score: float
    description: Optional[str]

    class Config:
        from_attributes = True