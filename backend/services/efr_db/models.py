from pydantic import BaseModel, Field
from typing import List, Optional

class Farmer(BaseModel):
    name: str
    contact: str
    land_size: float
    crops: List[str]
    location: Optional[str] = None
