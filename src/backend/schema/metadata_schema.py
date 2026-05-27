from pydantic import BaseModel
from datetime import datetime

class MetadataBase(BaseModel):
    time: datetime
    size_data: int
    privilege_need: str | None = None
    tree_depth: int
    method: str

class MetadataResponse(MetadataBase):
    id: str
    is_anomaly: bool
    anomaly_reason: str | None = None
