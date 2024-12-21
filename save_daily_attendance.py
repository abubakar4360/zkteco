from fastapi import FastAPI, HTTPException
from datetime import datetime, time, timedelta
import pandas as pd
import asyncio
import uvicorn
from sqlalchemy import func
from datetime import timedelta, date
from src.attendance import get_attendance_data, process_all_records
from src.utils import calculate_extra_time
from src.db import SessionLocal
from src.save_attendance_db import insert_attendance_records_in_db
import logging
from src.model import AttendanceModel

logging.basicConfig(level=logging.INFO)

app = FastAPI()

def get_last_attendance_date(db):
    try:
        last_date = db.query(func.max(AttendanceModel.date)).scalar()
        return last_date  # Return as is, since it's already a `datetime.date` object
    except Exception as e:
        logging.error(f"Error fetching last attendance date: {str(e)}")
        raise HTTPException(status_code=500, detail="Database query failed")

def fetch_and_process_missing_dates(db, last_date, current_date):
    try:
        if not last_date or last_date >= current_date:
            logging.info("No missing dates to process.")
            return  # Nothing to backfill

        # Calculate missing dates excluding weekends
        missing_dates = [last_date + timedelta(days=i) 
                         for i in range(1, (current_date - last_date).days + 1) 
                         if (last_date + timedelta(days=i)).weekday() < 5]  # Skip weekends

        if not missing_dates:
            logging.info("No weekday dates to backfill.")
            return

        all_data = []
        for missing_date in missing_dates:
            attnd, employee_data, employee_ids = get_attendance_data()
            df, data = process_all_records(attnd, employee_data, employee_ids)

            for user_id, user_info in data.items():
                if not any(user_info['Check-in']) and not any(user_info['Check-out']):
                    continue

                date_filtered_df = pd.DataFrame({
                    'employee_id': [user_id] * len(user_info['Check-in']),
                    'name': [user_info['Name']] * len(user_info['Check-in']),
                    'date': df['Date'],
                    'check_in': user_info['Check-in'],
                    'check_out': user_info['Check-out'],
                    'extra_time': [
                        calculate_extra_time(ci, co) if ci and co else '00:00'
                        for ci, co in zip(user_info['Check-in'], user_info['Check-out'])
                    ]
                }).query('date == @missing_date')

                if not date_filtered_df.empty:
                    all_data.append(date_filtered_df)

        if all_data:
            all_df = pd.concat(all_data).sort_values(by=['employee_id', 'date']).reset_index(drop=True)
            insert_attendance_records_in_db(all_df, db)
            logging.info(f"Backfilled attendance records for {len(missing_dates)} days.")
        else:
            logging.info("No data to backfill.")
    except Exception as e:
        logging.error(f"Error processing missing dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def update_daily_attendance():
    current_date = datetime.now().date()
    db = SessionLocal()
    try:
        # Get the last attendance date from the database
        last_date = get_last_attendance_date(db)
        if last_date:
            fetch_and_process_missing_dates(db, last_date, current_date)

        # Process today's data
        attnd, employee_data, employee_ids = get_attendance_data()
        df, data = process_all_records(attnd, employee_data, employee_ids)

        all_data = []
        for user_id, user_info in data.items():
            if not any(user_info['Check-in']) and not any(user_info['Check-out']):
                continue

            date_filtered_df = pd.DataFrame({
                'employee_id': [user_id] * len(user_info['Check-in']),
                'name': [user_info['Name']] * len(user_info['Check-in']),
                'date': df['Date'],
                'check_in': user_info['Check-in'],
                'check_out': user_info['Check-out'],
                'extra_time': [
                    calculate_extra_time(ci, co) if ci and co else '00:00'
                    for ci, co in zip(user_info['Check-in'], user_info['Check-out'])
                ]
            }).query('date == @current_date')

            if not date_filtered_df.empty:
                all_data.append(date_filtered_df)

        if not all_data:
            logging.info(f"No attendance records found for {current_date}.")
            return {'message': f"No attendance records found for {current_date}."}

        all_df = pd.concat(all_data).sort_values(by=['employee_id', 'date']).reset_index(drop=True)
        logging.info(all_df)

        insert_attendance_records_in_db(all_df, db)
        logging.info("Attendance records updated successfully.")

        return {'message': 'Attendance records updated successfully'}
    except Exception as e:
        logging.error(f"Error updating attendance records: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def process_and_save_records():
    db = SessionLocal()
    try:
        attnd, employee_data, employee_ids = get_attendance_data()
        df, data = process_all_records(attnd, employee_data, employee_ids)

        all_data = []
        for user_id, user_info in data.items():
            if not any(user_info['Check-in']) and not any(user_info['Check-out']):
                continue

            user_df = pd.DataFrame({
                'employee_id': [user_id] * len(df),
                'name': [user_info['Name']] * len(df),
                'date': df['Date'],
                'check_in': [ci if ci else None for ci in user_info['Check-in']],
                'check_out': [co if co else None for co in user_info['Check-out']]
            })
            user_df['extra_time'] = [
                calculate_extra_time(ci, co) if ci and co else '00:00'
                for ci, co in zip(user_info['Check-in'], user_info['Check-out'])
            ]
            all_data.append(user_df)

        if all_data:
            all_df = pd.concat(all_data).sort_values(by=['employee_id', 'date']).reset_index(drop=True)
            
            # Insert into database
            insert_attendance_records_in_db(all_df, db)
            logging.info("Attendance records updated successfully.")
        else:
            raise HTTPException(status_code=404, detail="Attendance not found")
    
    except Exception as e:
        logging.error(f"Error updating attendance records: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
    

async def schedule_daily_tasks():
    while True:
        now = datetime.now()
        if now.minute == 40:
            update_daily_attendance()
        await asyncio.sleep(60)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(schedule_daily_tasks())

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8010)
