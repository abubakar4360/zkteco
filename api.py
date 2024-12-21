from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
from passlib.context import CryptContext
import jwt
import pandas as pd
import calendar
import uvicorn
import logging
import asyncio
from src.schemas import UserCreateSchema, AttendanceRequest, EmployeeRequest
from src.model import UserModel, AttendanceModel
from src.save_attendance_db import insert_attendance_records_in_db
from src.verify_email import send_email
from src.attendance import (get_attendance_data, process_attendance,
                            process_all_records)
from src.utils import (calculate_extra_time, save_attendance_data,
                       create_access_token, SECRET_KEY, ALGORITHM,
                       VERIFICATION_SECRET_KEY)
from src.db import get_db, SessionLocal


app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
logging.basicConfig(level=logging.INFO)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception
        user = db.query(UserModel).filter(UserModel.name == username).first()
        if user is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    return user

@app.post("/process_attendances/")
def process_and_save_records(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
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
            
            # Save to Excel file
            file_path = 'attendance_records.xlsx'
            save_attendance_data(all_df, file_path)
            
            # Insert into database
            insert_attendance_records_in_db(all_df, db)
            
            return {"message": "Attendance records processed, saved to Excel, and saved to the database successfully"}
        else:
            raise HTTPException(status_code=404, detail="Attendance not found")
    
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@app.post('/signup')
def create_user(user: UserCreateSchema, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if db.query(UserModel).filter(UserModel.name == user.name).first():
        raise HTTPException(status_code=409, detail='Username already exists')
    elif db.query(UserModel).filter(UserModel.email == user.email).first():
        raise HTTPException(status_code=409, detail='Email already exists')

    new_user = UserModel(name=user.name, email=user.email, password=pwd_context.hash(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send verification email
    try:
        verification_token = jwt.encode({'sub': new_user.email, 'exp': datetime.utcnow() + timedelta(minutes=15)},
                                        VERIFICATION_SECRET_KEY, algorithm=ALGORITHM)
        verification_link = f"http://127.0.0.1:8000/verify_email?token={verification_token}"

        body = f"Click the link to verify your account: {verification_link}"
        background_tasks.add_task(send_email, '"Verify your account"', new_user.email, body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Admin created! Please verify your email."}


@app.post('/login')
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        existing_user = db.query(UserModel).filter(UserModel.name == form_data.username).first()

        if not existing_user or not pwd_context.verify(form_data.password, existing_user.password):
            raise HTTPException(status_code=401, detail='Incorrect username or password')
        if not existing_user.is_verified:
            raise HTTPException(status_code=401, detail='Email not verified!')

        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(data={"sub": existing_user.name}, expires_delta=access_token_expires)

        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/verify_email')
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, VERIFICATION_SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=400, detail="Invalid token")
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if not user or user.is_verified:
            raise HTTPException(status_code=400, detail="Invalid or already verified user")
        user.is_verified = True
        db.commit()
        return {"message": "Email verified successfully!"}
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid token")


@app.put('/admins/update-password/')
def update_password(current_password: str, new_password: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    try:
        admin = db.query(UserModel).filter(UserModel.id == current_user.id).first()

        if not pwd_context.verify(current_password, admin.password):
            raise HTTPException(status_code=400, detail='Current password is incorrect.')

        # Hash the new password
        hashed_password = pwd_context.hash(new_password)
        admin.password = hashed_password
        db.commit()
        db.refresh(admin)

        return {"message": "Password updated successfully."}
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid token")


@app.post('/monthly_attendance_record', response_class=FileResponse)
def monthly_attendance_record(request: AttendanceRequest, current_user: UserModel = Depends(get_current_user)):
    """
    Endpoint to generate a monthly attendance record for all employees.
    Returns an Excel file with attendance data.
    """
    try:
        attnd, employee_data, employee_ids = get_attendance_data()
        df, data = process_attendance(attnd, employee_data, employee_ids, request.month, request.year)

        all_data = []
        for user_id, user_info in data.items():
            # Skip users with no check-in/check-out records for the entire month
            if not any(user_info['Check-in']) and not any(user_info['Check-out']):
                continue

            employee_df = pd.DataFrame({
                'User ID': [user_id] * len(df),
                'Name': [user_info['Name']] * len(df),
                'Date': df['Date'],
                'Check-in': user_info['Check-in'],
                'Check-out': user_info['Check-out'],
                'Extra Time': [
                    calculate_extra_time(ci, co) if ci and co else '00:00'
                    for ci, co in zip(user_info['Check-in'], user_info['Check-out'])
                ]
            })
            all_data.append(employee_df)

        # Concatenate all data into a single DataFrame
        if all_data:
            monthly_df = pd.concat(all_data).sort_values(by=['User ID', 'Date']).reset_index(drop=True)
            filename = f'{calendar.month_name[request.month]}-{request.year}.xlsx'
            save_attendance_data(monthly_df, filename)
            return FileResponse(filename, filename=filename)
        else:
            raise HTTPException(status_code=404, detail=f"No attendance records found for {calendar.month_name[request.month]} {request.year}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing attendance records: {str(e)}")


@app.post('/employee_monthly_record', response_class=FileResponse)
def employee_monthly_record(request: EmployeeRequest, current_user: UserModel = Depends(get_current_user)):
    """
    Endpoint to generate a monthly attendance record for a specific employee.
    Returns an Excel file with the employee's attendance data.
    """
    try:
        attnd, employee_data, employee_ids = get_attendance_data()
        df, data = process_attendance(attnd, employee_data, employee_ids, request.month, request.year)

        if request.id not in data:
            raise HTTPException(status_code=404, detail=f"No data found for User ID {request.id}")

        employee_info = data[request.id]

        if not any(employee_info['Check-in']) and not any(employee_info['Check-out']):
            raise HTTPException(status_code=404, detail=f"No attendance records found for User ID {request.id} in {calendar.month_name[request.month]} {request.year}")

        employee_df = pd.DataFrame({
            'User ID': [request.id] * len(df),
            'Name': [employee_info['Name']] * len(df),
            'Date': df['Date'],
            'Check-in': employee_info['Check-in'],
            'Check-out': employee_info['Check-out'],
            'Extra Time': [
                calculate_extra_time(ci, co) if ci and co else '00:00'
                for ci, co in zip(employee_info['Check-in'], employee_info['Check-out'])
            ]
        })

        filename = f'{employee_info["Name"]}_{calendar.month_name[request.month]}-{request.year}.xlsx'
        save_attendance_data(employee_df, filename)
        return FileResponse(filename, filename=filename)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing employee records: {str(e)}")


@app.post('/user_extra_time', response_class=PlainTextResponse)
def user_extra_time(request: EmployeeRequest, current_user: UserModel = Depends(get_current_user)):
    """
    Endpoint to calculate the total extra time for a specific employee in a given month and year.
    Returns the total extra minutes as plain text.
    """
    try:
        attnd, employee_data, employee_ids = get_attendance_data()
        df, data = process_attendance(attnd, employee_data, employee_ids, request.month, request.year)

        if request.id not in data:
            raise HTTPException(status_code=404, detail=f"No data found for User ID {request.id}")

        employee_info = data[request.id]
        total_extra_minutes = 0

        for checkin, checkout in zip(employee_info['Check-in'], employee_info['Check-out']):
            if checkin and checkout:
                extra_time = calculate_extra_time(checkin, checkout)
                hours, minutes = map(int, extra_time.split(':'))
                total_extra_minutes += hours * 60 + minutes

        return f"{str(total_extra_minutes)} minutes"

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while calculating extra time: {str(e)}")


def update_daily_attendance():
    current_date = datetime.now().date()
    db = SessionLocal()
    try:
        attnd, employee_data, employee_ids = get_attendance_data()
        df, data = process_attendance(attnd, employee_data, employee_ids, current_date.month, current_date.year)

        all_data = []
        for user_id, user_info in data.items():
            if not any(user_info['Check-in']) and not any(user_info['Check-out']):
                continue

            # Filter records only for the current date
            date_filtered_df = pd.DataFrame({
                'employee_id': [user_id] * len(df),
                'name': [user_info['Name']] * len(df),
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

        if all_data:
            all_df = pd.concat(all_data).sort_values(by=['employee_id', 'date']).reset_index(drop=True)
            insert_attendance_records_in_db(all_df, db)
            logging.info("Attendance records updated successfully.")
            return {'message': 'Attendance records updated'}
        else:
            raise HTTPException(status_code=404, detail="Attendance records not found")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


async def schedule_daily_tasks():
    while True:
        now = datetime.now()
        if now.minute == 0:
            update_daily_attendance()
        await asyncio.sleep(60)


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(schedule_daily_tasks())

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
