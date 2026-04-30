from pydantic import BaseModel

class DeviceRegister(BaseModel):
    name: str
    public_key: str
