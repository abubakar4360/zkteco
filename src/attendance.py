import pandas as pd
from src.utils import create_empty_dataframe
from zk import ZK
from typing import Tuple, Dict, List, Optional

def get_attendance_data():
    """
    Connects to the attendance machine, retrieves, and returns attendance data for the specified month and year.
    """
    conn = None
    zk = ZK('192.168.18.10', port=4370, timeout=25, password=8, force_udp=False, ommit_ping=False)

    try:
        conn = zk.connect()
        print('Connection established')
        conn.disable_device()

        # Retrieve and sort users by user ID
        users = conn.get_users()
        user_data = {int(user.user_id): user.name for user in users}
        user_ids = sorted(user_data.keys())

        # Retrieve attendance records
        attnd = conn.get_attendance()
        conn.enable_device()
        return attnd, user_data, user_ids

    except Exception as e:
        print(f"Error retrieving attendance data: {e}")
        return [], {}, []

    finally:
        if conn:
            conn.disconnect()

def process_all_records(attnd, user_data, user_ids):
    """
    Processes raw attendance data into a structured format for all available dates.
    """
    # Create an empty DataFrame with all dates available in the data
    all_dates = {att.timestamp.date() for att in attnd}
    df = pd.DataFrame({'Date': sorted(all_dates)})

    # Initialize data structure for storing processed information
    data = {user_id: {'Name': '', 'Check-in': [''] * len(df), 'Check-out': [''] * len(df)} for user_id in user_ids}

    # Collect all timestamps for each user and date
    attendance_records = {}
    for att in attnd:
        record_date = att.timestamp.date()
        user_id = int(att.user_id)
        time_stamp = f'{att.timestamp.hour:02d}:{att.timestamp.minute:02d}:{att.timestamp.second:02d}'

        if user_id not in attendance_records:
            attendance_records[user_id] = {}

        if record_date not in attendance_records[user_id]:
            attendance_records[user_id][record_date] = {'Check-ins': [], 'Check-outs': []}

        if att.punch == 0:
            attendance_records[user_id][record_date]['Check-ins'].append(time_stamp)
        else:
            attendance_records[user_id][record_date]['Check-outs'].append(time_stamp)

        # Assign username
        if user_id in user_data:
            data[user_id]['Name'] = user_data[user_id]

    # Process the records to determine valid check-ins and check-outs
    for user_id, dates in attendance_records.items():
        for date, punches in dates.items():
            day_index = df.index[df['Date'] == date].tolist()
            if day_index:
                day_index = day_index[0]

                checkins = punches['Check-ins']
                checkouts = punches['Check-outs']

                # Determine valid check-in and check-out
                if not checkins and checkouts:
                    # If there's only one check-out, use it as the valid check-out
                    if len(checkouts) == 1:
                        data[user_id]['Check-out'][day_index] = checkouts[0]
                    else:
                        # Use first checkout as check-in and last as check-out
                        data[user_id]['Check-in'][day_index] = checkouts[0]
                        data[user_id]['Check-out'][day_index] = checkouts[-1]

                elif not checkouts and checkins:
                    # If there's only one check-in, use it as the valid check-in
                    if len(checkins) == 1:
                        data[user_id]['Check-in'][day_index] = checkins[0]
                    else:
                        # Use first check-in as check-in and last as check-out
                        data[user_id]['Check-in'][day_index] = checkins[0]
                        data[user_id]['Check-out'][day_index] = checkins[-1]

                else:
                    # Normal case: we have both check-ins and check-outs
                    if len(checkins) == 1:
                        data[user_id]['Check-in'][day_index] = checkins[0]
                    elif checkins:
                        data[user_id]['Check-in'][day_index] = checkins[0]

                    if len(checkouts) == 1:
                        data[user_id]['Check-out'][day_index] = checkouts[0]
                    elif checkouts:
                        data[user_id]['Check-out'][day_index] = checkouts[-1]

    return df, data


def process_attendance(attnd, user_data, user_ids, month, year):
    """
    Processes raw attendance data into structured format for specific month and year.
    """
    df, data = create_empty_dataframe(month, year, user_ids)

    # Collect all timestamps for each user and date
    attendance_records = {}
    for att in attnd:
        record_month = att.timestamp.month
        record_year = att.timestamp.year
        user_id = int(att.user_id)
        record_date = att.timestamp.date()

        if record_month == month and record_year == year:
            time_stamp = f'{att.timestamp.hour:02d}:{att.timestamp.minute:02d}:{att.timestamp.second:02d}'
            if user_id not in attendance_records:
                attendance_records[user_id] = {}

            if record_date not in attendance_records[user_id]:
                attendance_records[user_id][record_date] = {'Check-ins': [], 'Check-outs': []}

            if att.punch == 0:
                attendance_records[user_id][record_date]['Check-ins'].append(time_stamp)
            else:
                attendance_records[user_id][record_date]['Check-outs'].append(time_stamp)

            # Assign username
            data[user_id]['Name'] = user_data[user_id]

    # Process the records to determine valid check-ins and check-outs
    for user_id, dates in attendance_records.items():
        for date, punches in dates.items():
            day_index = df.index[df['Date'] == date].tolist()
            if day_index:
                day_index = day_index[0]

                checkins = punches['Check-ins']
                checkouts = punches['Check-outs']

                # Determine valid check-in and check-out
                if not checkins and checkouts:
                    # If there's only one check-out, use it as the valid check-out
                    if len(checkouts) == 1:
                        data[user_id]['Check-out'][day_index] = checkouts[0]
                    else:
                        # Use first checkout as check-in and last as check-out
                        data[user_id]['Check-in'][day_index] = checkouts[0]
                        data[user_id]['Check-out'][day_index] = checkouts[-1]

                elif not checkouts and checkins:
                    # If there's only one check-in, use it as the valid check-in
                    if len(checkins) == 1:
                        data[user_id]['Check-in'][day_index] = checkins[0]
                    else:
                        # Use first check-in as check-in and last as check-out
                        data[user_id]['Check-in'][day_index] = checkins[0]
                        data[user_id]['Check-out'][day_index] = checkins[-1]

                else:
                    # Normal case: we have both check-ins and check-outs
                    if len(checkins) == 1:
                        data[user_id]['Check-in'][day_index] = checkins[0]
                    elif checkins:
                        data[user_id]['Check-in'][day_index] = checkins[0]

                    if len(checkouts) == 1:
                        data[user_id]['Check-out'][day_index] = checkouts[0]
                    elif checkouts:
                        data[user_id]['Check-out'][day_index] = checkouts[-1]

    return df, data
