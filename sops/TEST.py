import requests
import pandas as pd
import time
import json
import firebase_admin
from firebase_admin import credentials, db
import os
import ast

# Firebase initialization (if still needed elsewhere)
cred = credentials.Certificate("./cert.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://dtdchirawa.firebaseio.com/'
})

# Gemini API Config
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
API_KEY = "AIzaSyC4GFljfImdJ39uzkyj2vLZqbjqZ3fNGjg"



# File paths for your data
employee_data = db.reference('EmployeeDetailData').get()
print(employee_data)
work_detail_data = db.reference('DailyWorkDetail').get()
field_exec_data = db.reference('Attendance').get()

ROLE_MAPPINGS = {
    "field executive": ["fe", "field exec", "field executive"],
    "service executive": ["se", "service exec", "service executive"],
    "transportation executive": ["te", "transportation exec", "transportation executive"]
}


def load_json_file(file_path):
    """Load a JSON file and return its content."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_data(employee_file, work_file, date_to_check, role="Transportation Executive", expected_time="09:00"):
    """
    Filters the employee and work detail data to find records for transport executives on a given date.

    Assumptions:
    - Employee data is a list of dictionaries, each with keys: 'employee_id', 'name', 'role'
    - Work detail data is a list of dictionaries, each with keys: 'employee_id', 'date', 'arrival_time'
    - Time strings are in "HH:MM" 24-hour format.
    """
    # Load the data files
    # employee_data = load_json_file(employee_file)
    # work_data = load_json_file(work_file)

    # Filter employees for the given role (case insensitive)

    filtered_employees = []
    employee_data = dict(employee_file)  # Ensure it's a dictionary

    for emp_id, emp in employee_data.items():  # ✅ Iterate over key-value pairs
        # print(emp)  # This should now be a dictionary
        if type(emp) == str:
            continue
        designation = emp.get("designation", "").lower()  # Extract designation safely

        if designation == role.lower():
            filtered_employees.append(emp_id)
        #print(filtered_employees)

    employee_ids = filtered_employees

    filtered_work = []

    # Extract year and month from date_to_check
    year, month, day = date_to_check.split("-")
    month_name = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December"
    }.get(month, "")

    # Navigate to the specific date in work_data
    if year in work_file and month_name in work_file[year] and date_to_check in work_file[year][month_name]:
        daily_records = work_file[year][month_name][date_to_check]

        # Iterate through employee records for the specified date
        for emp_id, record in daily_records.items():
            # print(emp_id)
            if emp_id in employee_ids:  # Check if employee ID is in the given list
                filtered_work.append({"employee_id": emp_id, "details": record})

    # Print results
    print(filtered_work)

    # Mark each record as "On Time" or "Late" based on arrival time (if available)
    for record in filtered_work:
        details = record.get("details", {})  # ✅ Extract the details dictionary
        card_swap_entries = details.get("card-swap-entries", {})  # ✅ Get the time entries

        if card_swap_entries:
            arrival_time = min(card_swap_entries.keys())

        if arrival_time:
            # For simplicity, compare time strings (works if both are in "HH:MM" format)
            if arrival_time <= expected_time:
                record["status"] = "On Time"
            else:
                record["status"] = "Late"

    # Return the filtered and annotated data as a dictionary
    return {
        "filtered_employees": filtered_employees,
        "filtered_work": filtered_work
    }

def filter_data2(employee_file, field_file, date_to_check, role="Field Executive", expected_time="09:00"):
    """
    Filters the employee and work detail data to find records for transport executives on a given date.

    Assumptions:
    - Employee data is a list of dictionaries, each with keys: 'employee_id', 'name', 'role'
    - Field data is a list of dictionaries, each with keys: 'employee_id', 'date', 'inDetails','outDetails'
    - Time strings are in "HH:MM" 24-hour format.
    """
    # Load the data files
    employee_data = load_json_file(employee_file)
    field_data = load_json_file(field_file)

    # Filter employees for the given role (case insensitive)
    filtered_employees = []
    employee_data = dict(employee_data)  # Ensure it's a dictionary

    for emp_id, emp in employee_data.items():  # Iterate over key-value pairs
        # Skip if the value is not a dictionary
        if not isinstance(emp, dict):
            continue

        designation = emp.get("designation", "").lower()  # Extract designation safely

        if designation == role.lower():
            filtered_employees.append(emp_id)

    employee_ids = filtered_employees

    # Extract year, month, and day from date_to_check
    year, month, day = date_to_check.split("-")
    month_name = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December"
    }.get(month, "")

    filtered_work = []

    # Navigate to the specific date in work_data
    if year in field_data and month_name in field_data[year] and date_to_check in field_data[year][month_name]:
        daily_records = field_data[year][month_name][date_to_check]

        # Iterate through employee records for the specified date
        for emp_id, record in daily_records.items():
            if emp_id in employee_ids:  # Check if employee ID is in the given list
                in_details = record.get("inDetails", {})
                out_details = record.get("outDetails", {})

                # Determine status based on arrival time
                arrival_time = in_details.get("time", None).strip()

                if arrival_time:
                    if arrival_time <= expected_time:
                        status = "On Time"
                    else:
                        status = "Late"
                else:
                    status = "No Entry"

                filtered_work.append({
                    "employee_id": emp_id,
                    "inDetails": in_details,
                    "outDetails": out_details,
                    "status": status
                })
                print(filtered_work)

    # Return the filtered and annotated data as a dictionary
    return {
        "filtered_employees": employee_ids,
        "filtered_work": filtered_work
    }


def call_gemini_api(prompt, retries=5, delay=5):
    headers = {"Content-Type": "application/json"}
    params = {"key": API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(retries):
        try:
            response = requests.post(API_URL, headers=headers, params=params, json=payload)
            response.raise_for_status()
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429:
                print(f"Rate limit hit. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"HTTP error: {http_err}")
                return f"Error: {http_err}"
        except Exception as err:
            print(f"Unexpected error: {err}")
            return "Error: Unable to process the request."
    return "Error: Failed after retries."


import json


# Load SOP rules from a JSON file
def load_sop_rules(sop_file):
    try:
        with open(sop_file, "r", encoding="utf-8") as file:
            sop_rules = json.load(file)
        return sop_rules
    except Exception as e:
        print(f"Error loading SOP rules: {e}")
        return []


def ask_question(filtered_data, question, sop_file="translated_output04.json"):
    """
    Constructs a prompt using filtered data, SOP rules, and the user question,
    then sends it to Gemini.
    """
    # Convert filtered data to a JSON string
    data_str = json.dumps(filtered_data, indent=4)

    # Load SOP rules
    sop_rules = load_sop_rules(sop_file)
    sop_str = json.dumps(sop_rules, indent=4) if sop_rules else "No SOP rules available."
    # print(sop_str, "eee")

    # Construct the prompt
    prompt = f"""
            You are an expert in compliance and operational analysis.

            ### **Filtered Data:**
            {data_str}

            ### **Standard Operating Procedures (SOP) Rules:**
            {sop_str}

            Now, answer the following question based on the data only and SOP rules:

            **Question:** {question}

            answer format:
            "employee_id: not followed sop 1",
            "employee_id_2: not followed sop 2",
            """
    return call_gemini_api(prompt)


import json
import re


def extract_info_from_question(question):
    """Extracts role and date dynamically using Gemini API."""
    prompt = f"""
    Extract the role and date from the given question:
    Question: "{question}"
    Given the following predefined roles:
    - Field Executive
    - Operation Executive
    - Transportation Executive


    Respond in JSON format:
    {{
        "role": "detected role",
        "date": "YYYY-MM-DD" (if applicable, else null)
    }}
    """
    result = call_gemini_api(prompt)

    # If API response is an error message, return None
    if result.startswith("Error"):
        print("API Error:", result)
        return None, None

    # Remove Markdown formatting (```json ... ```)
    clean_result = re.sub(r"```json\n|\n```", "", result).strip()

    try:
        extracted_data = json.loads(clean_result)  # Now it should work fine!
        role = extracted_data.get("role")
        date = extracted_data.get("date")
        return role, date
    except json.JSONDecodeError:
        print("JSON Decode Error: Response is not valid JSON.")
        # print("Raw Response:", result)
        return None, None


def main():
    while True:
        question = input("\nAsk a question (or type 'exit' to quit): ")
        if question.lower() == "exit":
            break

        role, date = extract_info_from_question(question)

        if not role or not date:
            print("Couldn't determine role or date. Please rephrase.")
            continue

        # print(f"Detected Role: {role}, Detected Date: {date}")

        if role == "Transportation Executive":
            print(employee_data)
            filtered_data = filter_data(employee_data, work_detail_data, date)
        elif role == "Field Executive":
            filtered_data = filter_data2(employee_data, field_exec_data, date)
        # filtered_data = filter_data(EMPLOYEE_DATA_FILE, WORK_DETAIL_FILE, date)
        # filtered_data = filter_data2(EMPLOYEE_DATA_FILE, FIELD_EXEC_FILE, date)

        print(f"filtered_data {filtered_data}")
        answer = ask_question(filtered_data, question)

        print("Answer:", answer)


if __name__ == "__main__":
    main()


