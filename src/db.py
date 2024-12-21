from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.model import Base


engine = create_engine("postgresql://algoryc:algoryc%40789@89.39.107.124/attendance_db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
