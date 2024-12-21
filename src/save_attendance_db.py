from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.model import AttendanceModel

def insert_attendance_records_in_db(df, db):
    try:
        for _, row in df.iterrows():
            stmt = insert(AttendanceModel).values(
                employee_id=row['employee_id'],
                name=row['name'],
                date=row['date'],
                check_in=row['check_in'] or None,
                check_out=row['check_out'] or None,
                extra_time=row['extra_time'] or '00:00'
            ).on_conflict_do_update(
                index_elements=['employee_id', 'date'],  # Ensure these are indexed
                set_={
                    'check_in': row['check_in'] or None,
                    'check_out': row['check_out'] or None,
                    'extra_time': row['extra_time'] or '00:00'
                }
            )
            db.execute(stmt)

        # Commit the transaction
        db.commit()
        print("All records have been successfully inserted or updated in the database.")
    except IntegrityError as e:
        db.rollback()
        print(f"Integrity error: {e}")
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error inserting or updating records in the database: {e}")
    finally:
        db.close()
