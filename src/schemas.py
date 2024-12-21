from pydantic import BaseModel, conint
from datetime import datetime


current_date = datetime.now()


class UserCreateSchema(BaseModel):
    # id: int
    name: str
    email: str
    password: str


class AttendanceRequest(BaseModel):
    month: conint(ge=1, le=12)
    year: conint(ge=2023, le=current_date.year)


class EmployeeRequest(BaseModel):
    month: conint(ge=1, le=12)
    year: conint(ge=2023, le=current_date.year)
    id: int
