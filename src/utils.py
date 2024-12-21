import pandas as pd
from openpyxl import load_workbook
import calendar
from datetime import timedelta, datetime
from collections import defaultdict
from typing import Tuple, Dict, List, Optional
import jwt
import secrets


SECRET_KEY = secrets.token_hex(32)
VERIFICATION_SECRET_KEY = secrets.token_hex(32)
ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def calculate_extra_time(checkin, checkout):
    try:
        checkin_time = datetime.strptime(checkin, '%H:%M:%S')
        checkout_time = datetime.strptime(checkout, '%H:%M:%S')
        duration = checkout_time - checkin_time
        standard_hours = timedelta(hours=9)

        if duration > standard_hours:
            extra_time = duration - standard_hours
            hours, remainder = divmod(extra_time.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            total_extra_minutes = hours*60 + minutes
            if total_extra_minutes > 40:
                return f'{hours:02d}:{minutes:02d}'
            else:
                return '00:00'
            return f'{hours:02d}:{minutes:02d}'
        else:
            return '00:00'
    except Exception as e:
        print(f"Error calculating extra time: {e}")
        return '00:00'


def set_column_widths(filename):
    column_widths = {
        'A': 12,  # User ID
        'B': 20,  # Name
        'C': 15,  # Date
        'D': 15,  # Check-in
        'E': 15,  # Check-out
        'F': 15  # Extra Time
    }

    try:
        workbook = load_workbook(filename)
        sheet = workbook.active

        for col, width in column_widths.items():
            sheet.column_dimensions[col].width = width

        workbook.save(filename)
        print(f"Column widths set for file: {filename}")
    except Exception as e:
        print(f"Error setting column widths for file '{filename}': {e}")


def save_attendance_data(attendance_data, filename):
    try:
        print(f"Saving data to file: {filename}")
        with pd.ExcelWriter(filename, engine='openpyxl', mode='w') as writer:
            attendance_data.to_excel(writer, sheet_name='Attendance', index=False)
        set_column_widths(filename)

        return filename
    except Exception as e:
        print(f"Error saving file '{filename}': {e}")

    
def create_empty_dataframe(month, year, user_ids):
    current_date = datetime.now()
    num_days = calendar.monthrange(year, month)[1]

    # Limit the number of days if the month and year are the current month and year
    if month == current_date.month and year == current_date.year:
        num_days = current_date.day

    # Create date range and filter out weekends
    date_range = pd.date_range(start=f'{year}-{month:02d}-01', periods=num_days)
    weekdays = [date.date() for date in date_range if date.weekday() < 5]  # 0-4 are Monday-Friday

    df = pd.DataFrame({'Date': weekdays})
    data = {user_id: {'Check-in': [None] * len(weekdays), 'Check-out': [None] * len(weekdays), 'Name': ''} for user_id
            in user_ids}

    return df, data
