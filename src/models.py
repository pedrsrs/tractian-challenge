import re
from typing import Optional, Dict, List
from pydantic import BaseModel, validator

class Part(BaseModel):
    part_number: str
    description: str
    quantity: int

    @validator("quantity", pre=True)
    def parse_quantity(cls, value):
        if isinstance(value, int):
            return value
        match = re.search(r"\d+(?:\.\d+)?", str(value))
        if match:
            return int(float(match.group()))
        raise ValueError(f"Invalid quantity format: {value}")

class Assets(BaseModel):
    manual: Optional[str]
    cad: Optional[str]
    image: Optional[str]

class ProductData(BaseModel):
    product_id: str
    name: str
    description: Optional[str]
    specs: Optional[Dict[str, str]]
    bom: Optional[List[Part]]
    assets: Optional[Assets]
