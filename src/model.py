from sqlalchemy import (Column, Integer, String, Date, Time,
                        Interval, Boolean, PrimaryKeyConstraint)
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class UserModel(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(150), nullable=False)
    is_verified = Column(Boolean, default=False)


class AttendanceModel(Base):
    __tablename__ = 'app_employeeattendance'
    employee_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(Time, nullable=True)
    check_out = Column(Time, nullable=True)
    extra_time = Column(Interval, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('employee_id', 'date'),
    )
