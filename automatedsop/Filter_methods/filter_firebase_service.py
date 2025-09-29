from firebase_admin import db
import datetime
def filter_data2(employee_data, app, role="Field Executive", expected_time="09:00"):
    from datetime import datetime

    # Step 1: Filter employees by role
    filtered_employees = []
    employee_names = {}

    for emp_id, emp in dict(employee_data).items():
        if isinstance(emp, dict):
            designation = emp.get("designation", "").lower()
            name = emp.get("name", "")
            if designation == role.lower():
                filtered_employees.append(emp_id)
                employee_names[emp_id] = name

    filtered_work = []
    date_obj = datetime.today()
    date_str = date_obj.strftime("%Y-%m-%d")
    year = date_obj.strftime("%Y")
    month = date_obj.strftime("%m")
    day = date_obj.strftime("%d")

    month_name_map = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December"
    }
    month_name = month_name_map[month]

    for emp_id in filtered_employees:
        try:

            firebase_path = f'Attendance/{emp_id}/{year}/{month_name}/{date_str}'
            # Get only the required date’s work data
            field_data = db.reference(firebase_path, app=app).get()
            if field_data == None:
                continue

            record = field_data

        except KeyError:
            continue  # No data for this date

        in_details = record.get("inDetails", {})
        out_details = record.get("outDetails", {})
        arrival_time = in_details.get("time", "").strip()

        if arrival_time:
            status = "On Time" if arrival_time <= expected_time else "Late"
        else:
            status = "No Entry"

        filtered_work.append({
            "date": date_str,
            "employee_id": emp_id,
            "employee_name": employee_names.get(emp_id, ""),
            "inDetails": in_details.get('time'),
            "outDetails": out_details.get('time'),
            "status": status
        })

    return {
        "filtered_work": filtered_work
    }


def filter_data(employee_file, app, role="Transportation Executive", expected_time="09:00", ):
    """
    Filters employee and work detail data to find records for Transport Executives for the previous day.
    """

    filtered_employees = []
    employee_names = {}
    employee_mobile_number = {}

    for emp_id, emp in dict(employee_file).items():
        if isinstance(emp, dict):
            designation = emp.get("designation", "").lower()
            name = emp.get("name", "")
            mobile_number = emp.get("mobile", "")
            if designation == role.lower():
                filtered_employees.append(emp_id)
                employee_names[emp_id] = name
                employee_mobile_number[emp_id] = mobile_number

    filtered_work = []

    # Calculate previous day's date
    date_obj = datetime.today()
    date_str = date_obj.strftime("%Y-%m-%d")
    year = date_obj.strftime("%Y")
    month = date_obj.strftime("%m")
    day = date_obj.strftime("%d")

    month_name_map = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December"
    }
    month_name = month_name_map[month]
    firebase_path = f'DailyWorkDetail/{year}/{month_name}/{date_str}'

    # Get only the required date’s work data
    work_file = db.reference(firebase_path, app=app).get()
    print(work_file.keys())

    for emp_id in filtered_employees:
        try:
            print(work_file)
            record = work_file[emp_id]
            print(record)
        except KeyError:
            continue  # No data for this employee on this day

        in_details = record.get("card-swap-entries", {})
        arrival_time = ""
        departure_time = ""

        for time_str, status in in_details.items():
            if status == "In":
                arrival_time = time_str.strip()
            elif status == "Out":
                departure_time = time_str.strip()

        filtered_work.append({
            "date": date_str,
            "employee_id": emp_id,
            "employee_name": employee_names.get(emp_id, ""),
            "employee_mobile_number": employee_mobile_number.get(emp_id, ""),
            "inDetails": arrival_time,
            "outDetails": departure_time,
        })

    return {
        "filtered_work": filtered_work
    }

def filterskiplinedata(skipline):
    today = datetime.today().strftime("%Y-%m-%d")
    filtered_data = {}

    for ward_name, ward_data in skipline.items():
        # Skip non-ward keys if any (like metadata)
        if not isinstance(ward_data, dict):
            continue

        if today in ward_data:
            date_info = ward_data.get(today, {})
            line_status = date_info.get("LineStatus", "NotFound")
            if line_status != 'LineCompleted':
                filtered_data[ward_name] = {
                    "date": today,
                    "LineStatus": line_status
                }

    return filtered_data