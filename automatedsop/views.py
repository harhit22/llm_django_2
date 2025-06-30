import calendar
import io
import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
import matplotlib.pyplot as plt
import cv2
import firebase_admin
import numpy as np
import pandas as pd
import requests
from PIL import Image
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from firebase_admin import credentials, initialize_app, db, _apps
from firebase_admin import storage
from paddleocr import PaddleOCR
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from ultralytics import YOLO

from sops.databaseurls import FIREBASE_DB_MAP
from sops.mailtowhom import site_info
from sops.models import SopStep, City, Sops
from sops.serializers import CitySerializer, SopsSerializer

# Gemini API Config
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
API_KEY = "AIzaSyC4GFljfImdJ39uzkyj2vLZqbjqZ3fNGjg"

ROLE_MAPPINGS = {
    "field executive": ["fe", "field exec", "field executive"],
    "service executive": ["se", "service exec", "service executive"],
    "transportation executive": ["te", "transportation exec", "transportation executive"]
}


def load_json_file(file_path):
    """Load a JSON file and return its content."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


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


class NoBotAskGeminiAPIView(APIView):
    def get(self, request):
        date_obj = datetime.today()
        date = date_obj.strftime("%Y-%m-%d")

        for site in site_info:
            site_name = site["site_name"]
            db_name = site['firebase_db']
            email = site["email"]
            formatted_site_name = site_name.lower().replace(" ", "-")
            app_name = f"{formatted_site_name}-app"

            try:
                cred = credentials.Certificate("sops/cert.json")
                app = initialize_app(cred, {
                    'databaseURL': f'https://{db_name}.firebaseio.com/',
                    'storageBucket': f'{db_name}.appspot.com'
                }, name=app_name)
            except Exception as init_err:
                print(f"❌ Failed to init app for {site_name}: {init_err}")
                continue

            employee_data = db.reference('EmployeeDetailData', app=app).get()

            filtered_data = filter_data2(employee_data, app=app)

            # Get SOP steps
            sop_steps = SopStep.objects.filter(sop_id=1)
            sop_detail = "\n".join([step.description for step in sop_steps])

            # Ask Gemini
            response = ask_question_fe(filtered_data, sop_detail)
            print(response)
            response_data = json.loads(response)
            df = pd.DataFrame(response_data if isinstance(response_data, list) else [response_data])

            # Save Excel report
            report_path = os.path.join(settings.BASE_DIR, "reports")
            os.makedirs(report_path, exist_ok=True)
            filename = f"{formatted_site_name}_dustbin_status_report_{date}.xlsx"
            filepath = os.path.join(report_path, filename)
            df.to_excel(filepath, index=False)
            print('sending mail')
            # Send email
            mail = EmailMessage(
                subject=f"{site_name} - Dustbin Status Report - {date}",
                body="Please find attached the dustbin status report.",
                from_email="harshitshrimalee.wevois@gmail.com",
                to=[email],
            )
            mail.attach_file(filepath)
            mail.send()

            # Optional: Remove the file after sending
            os.remove(filepath)

        return Response({"status": "Done sending reports to all sites."})


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


class NoBotAskGeminiAPIViewTransportExec(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            date_obj = datetime.today()
            date = date_obj.strftime("%Y-%m-%d")

            for site in site_info:
                site_name = site["site_name"]
                db_name = site['firebase_db']
                email = site["email"]
                formatted_site_name = site_name.lower().replace(" ", "-")
                app_name = f"{formatted_site_name}-app"

                print(f"\n📍 Processing site: {site_name}")

                # Initialize Firebase app
                print(_apps)
                try:
                    cred = credentials.Certificate("sops/cert.json")
                    app = initialize_app(cred, {
                        'databaseURL': f'https://{db_name}.firebaseio.com/',
                        'storageBucket': f'{db_name}.appspot.com'
                    }, name=app_name)
                except Exception as init_err:
                    print(f"❌ Failed to init app for {site_name}: {init_err}")
                    continue

                employee_data = db.reference('EmployeeDetailData', app=app).get()
                filtered_data = filter_data(employee_data, app)

                # Get SOP steps
                sop_steps = SopStep.objects.filter(sop_id=2)
                sop_detail = "\n".join([step.description for step in sop_steps])

                # Ask Gemini
                response = ask_question(filtered_data, sop_detail)
                print(response)
                response_data = json.loads(response)
                df = pd.DataFrame(response_data if isinstance(response_data, list) else [response_data])

                # Save Excel report
                report_path = os.path.join(settings.BASE_DIR, "reports")
                os.makedirs(report_path, exist_ok=True)
                filename = f"{formatted_site_name}_transport_{date}.xlsx"
                filepath = os.path.join(report_path, filename)
                df.to_excel(filepath, index=False)
                print('mail sending')
                # Send email
                mail = EmailMessage(
                    subject=f"{site_name} - tarnsport Report - {date}",
                    body="Please find attached the dustbin status report.",
                    from_email="harshitshrimalee.wevois@gmail.com",
                    to=["harshitshrimalee22@gmail.com"],
                )
                mail.attach_file(filepath)
                mail.send()

                # Optional: Remove the file after sending
                os.remove(filepath)

            return Response({"status": "Done sending reports to all sites."})

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def call_gemini_api(prompt, retries=5, delay=5):
    headers = {"Content-Type": "application/json"}
    params = {"key": API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    def clean_model_output(text):
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    for attempt in range(retries):
        try:
            response = requests.post(API_URL, headers=headers, params=params, json=payload)
            response.raise_for_status()
            result = response.json()
            raw_text = result['candidates'][0]['content']['parts'][0]['text']
            cleaned_text = clean_model_output(raw_text)
            # optional debug log
            return cleaned_text
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


def load_sop_rules(sop_file):
    try:
        with open(sop_file, "r", encoding="utf-8") as file:
            sop_rules = json.load(file)
        return sop_rules
    except Exception as e:
        print(f"Error loading SOP rules: {e}")
        return []


def ask_question_fe(filtered_data, sop_detail, sop_file="sops/translated_output04.json"):
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
    # print(data_str)
    print(sop_detail)

    # Construct the prompt
    prompt = f"""
    You are an expert in Operations and SOP (Standard Operating Procedure) Compliance Analysis.

    Your task is to:
    1. Analyze the attendance data *line by line*.
    2. Apply *each SOP rule strictly*.
    3. Return only the entries that are *non-compliant, clearly stating **which SOP rule(s)* were violated.
    4. winter september to april are winter month 

    ---

    ### SOP Rules:
    {str(sop_detail)}

    ### Filtered Attendance Data:
    {str(data_str)}

    ---

    ### Output Format:
    Answer in json format.
    [
      {{
        "Employee ID": "...",
        "Employee Name": "...",
        "Date": "...",
        "In-Time": "...",
        "Out-Time": "...",
        "Total working hours": "" # calculate based on in and out time
        "Violation": ".." which sops is violated give all 
      }},
      ...
    ]

    Only return entries that have any kind of SOP violation.
    Be precise, do not skip any rule, and avoid unnecessary explanation.
    """
    return call_gemini_api(prompt)


def ask_question(filtered_data, sop_detail, sop_file="sops/translated_output04.json"):
    print('i am called')
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
    # print(data_str)

    # Construct the prompt
    prompt = f"""
        You are an expert in Operations and SOP (Standard Operating Procedure) Compliance Analysis.

        Your task is to:
        1. Analyze the attendance and work details data line by line.
        2. Apply each SOP rule strictly.
        3. Return only the entries that are non-compliant, clearly stating **which SOP rule(s) were violated.
        4. Winter months are from September to April.

        ---

        ### SOP Rules:
        {str(sop_detail)}

        ### Filtered Attendance Data:
        {str(data_str)}

        ### Work Details Data (Extracted from Firebase):
        {{
            "Date": "YYYY-MM-DD",  # Work date in YYYY-MM-DD format
            "Employee ID": "...",  # Employee ID
            "Employee Name": "...",  # Employee Name
            "Arrival Time": "HH:MM:SS",  # Time when the employee arrived
            "Departure Time": "HH:MM:SS",  # Time when the employee left
            "employee mobile number":"..."

            # Add any other relevant fields as per the structure you expect from Firebase
        }}

        ---
        do not add ```json in the start
        ### Output Format:
        [
          {{
            "Employee ID": "...",
            "Employee Name": "...",
            "Date": "...",
            "Arrival Time": "HH:MM:SS",
            "Departure Time": "HH:MM:SS",
            "employee mobile number":"..."

            "Violation": "...",  # Full explanation of all SOP rules that were broken, with timestamps if necessary
          }},
          ...
        ]

        Only return entries that have any kind of SOP violation.
        Be precise, avoid unnecessary explanation.
    """
    return call_gemini_api(prompt)


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

        extracted_data = json.loads(clean_result)
        role = extracted_data.get("role")
        date = extracted_data.get("date")
        if not date:
            # Use current date in your preferred format, e.g. "2025-04-07"
            date = datetime.today().strftime("%Y-%m-%d")

        return role, date
    except json.JSONDecodeError:
        print("JSON Decode Error: Response is not valid JSON.")
        role = extracted_data.get("role")
        # print("Raw Response:", result)
        return None, None


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


class NoBotAskGeminiAPIViewSkipLines(APIView):
    def get(self, request):
        try:
            # Step 1: Get requested ward from query param
            ward_name = request.GET.get('ward')
            if not ward_name:
                return Response({"error": "Please provide a ward name via ?ward=ward_name"}, status=400)

            # Step 2: Fetch list of active wards from the JSON
            ward_list_url = "https://firebasestorage.googleapis.com/v0/b/dtdnavigator.appspot.com/o/Sikar%2FDefaults%2FAvailableWard.json?alt=media&token=f5f77078-bb85-4a8e-a6fb-4126934b4f60"
            ward_response = requests.get(ward_list_url)
            active_wards = ward_response.json()
            active_wards = [w for w in active_wards if w is not None]

            # Step 3: Check if ward is valid
            if ward_name not in active_wards:
                return Response({"error": f"Ward '{ward_name}' is not in the active list"}, status=400)
            today = datetime.today() - timedelta(days=1)
            year, month, day = today.strftime("%Y-%m-%d").split("-")
            print(year, month, today.strftime("%Y-%m-%d"))
            month_name_map = {
                "01": "January", "02": "February", "03": "March", "04": "April",
                "05": "May", "06": "June", "07": "July", "08": "August",
                "09": "September", "10": "October", "11": "November", "12": "December"
            }
            month_name = month_name_map.get(month)

            # Step 4: Fetch data only for this ward from Firebase
            ward_data = db.reference(
                f'WasteCollectionInfo/{ward_name}/{year}/{month_name}/{today.strftime("%Y-%m-%d")}').get()
            if not ward_data:
                return Response({"error": f"No data found for ward '{ward_name}'"}, status=404)

            # Step 5: SOP steps
            sop_steps = SopStep.objects.filter(sop_id=21)
            sop_detail = "\n".join([step.description for step in sop_steps])

            # Step 6: Filter and ask

            response1 = ask_question(ward_data, sop_detail)

            return Response({"response": response1})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OCRDieselSlipValidationAPIView(APIView):
    def post(self, request):
        try:
            # Get date from query param, fallback to yesterday
            date_param = request.GET.get('date')
            if date_param:
                date = date_param
            else:
                date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

            year, month_num, day = date.split("-")
            month_name_map = {
                "01": "January", "02": "February", "03": "March", "04": "April",
                "05": "May", "06": "June", "07": "July", "08": "August",
                "09": "September", "10": "October", "11": "November", "12": "December"
            }
            month_name = month_name_map.get(month_num)

            # Fetch data from Firebase
            entries_ref = db.reference(f"/DieselEntriesData/{year}/{month_name}/{date}")
            entries_data = entries_ref.get()
            print(entries_data)

            if not entries_data:
                return Response({"error": "No entries found for the given date."}, status=404)

            # Initialize PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='en')

            # Setup Firebase Storage
            bucket = storage.bucket()

            results = []
            i = 0

            for key, value in entries_data.items():
                i += 1
                if i == 2:
                    break

                if key == 'lastEntry':
                    continue

                expected_amount = str(value.get("amount", ""))
                print(expected_amount, key)
                expected_volume = str(value.get("quantity", ""))
                vehicle = str(value.get("vehicle", ""))

                # Define image path in storage
                blob_path = f"Sikar/DieselEntriesImages/{year}/{month_name}/{date}/{key}/amountSlipImage"
                blob = bucket.blob(blob_path)

                try:
                    time.sleep(1.5)
                    image_data = blob.download_as_bytes()
                    image = Image.open(io.BytesIO(image_data)).convert('RGB')
                    result = ocr.ocr(np.array(image))
                    extracted_text = " ".join([line[1][0] for block in result for line in block])

                    is_amount_valid = expected_amount in extracted_text
                    is_volume_valid = expected_volume in extracted_text

                    prompt = f"""
                    You are given the following extracted text from an image, along with the expected amount and volume values.

                    Your task is to check if the expected amount and volume are clearly present in the extracted text.

                    If the expected value appears in a jumbled, noisy, or unclear way (e.g. OCR errors, garbled numbers), consider it as *false*, and mention that in a remark.

                    Return the result strictly in this JSON format:
                    Note: if there is no amount in extracted_text and rate is present then multiply rate by volume then check amount to the original
                    if amount is little bit off like 9.00 and extracted is 9.0 both are 9 this is ok according to SOP but 9.3 and 9.5 are not ok

                    {{
                        "amount_match": <true/false>, expected_amount, extracted_amount
                        "volume_match": <true/false>, expected_volume, extracted_volume
                        "remark": "<brief reason if any value is false>"
                    }}

                    Expected values:
                    - expected_amount = {expected_amount}
                    - expected_volume = {expected_volume}

                    Extracted Text:
                    {extracted_text}
                    """
                    print(extracted_text)

                    result_raw = call_gemini_api(prompt)  # this should return a JSON string
                    result = json.loads(result_raw)
                    print(result)

                    results.append({
                        "key": key,
                        "vehicle": vehicle,
                        "amount_match": result['amount_match'],
                        "volume_match": result['volume_match'],
                        "expected_amount": expected_amount,
                        "expected_volume": expected_volume,
                        "extracted_text": extracted_text
                    })
                except Exception as e:
                    print(e)
                    results.append({
                        "key": key,
                        "status": "Error processing image",
                        "error": str(e)
                    })

            return Response({"date": date, "results": results})

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendCitiesDataAPIView(APIView):
    permission_classes = [AllowAny]  # Allows unauthenticated access

    def get(self, request):
        try:
            cities = City.objects.all()
            serializer = CitySerializer(cities, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendSopDataApiView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        city_id = request.query_params.get('city_id')

        queryset = Sops.objects.filter(in_working=True)
        city = City.objects.get(id=1)
        sop = Sops.objects.filter(cities=city)
        print(sop)

        if city_id:
            try:
                queryset = queryset.filter(cities__id=city_id)
            except City.DoesNotExist:
                return Response({"error": "City not found"}, status=status.HTTP_404_NOT_FOUND)

        # Serialize and return the data
        serializer = SopsSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NoBotAskGeminiAPItripalstatus(APIView):
    def post(self, request):
        try:
            date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
            for site in site_info:
                site_name = site["site_name"]
                db_name = site['firebase_db']
                email = site["email"]
                formatted_site_name = site_name.lower().replace(" ", "-")
                app_name = f"{formatted_site_name}-app"
                try:
                    cred = credentials.Certificate("sops/cert.json")
                    app = initialize_app(cred, {
                        'databaseURL': f'https://{db_name}.firebaseio.com/',
                        'storageBucket': f'dtdnavigator.appspot.com'
                    }, name=app_name)
                except Exception as init_err:
                    print(f"❌ Failed to init app for {site_name}: {init_err}")
                    continue

                year, month_num, day = date.split("-")
                month_name_map = {
                    "01": "January", "02": "February", "03": "March", "04": "April",
                    "05": "May", "06": "June", "07": "July", "08": "August",
                    "09": "September", "10": "October", "11": "November", "12": "December"
                }
                month_name = month_name_map.get(month_num)

                # Fetch data from Firebase
                entries_ref = db.reference(f"/WardTrips/{year}/{month_name}/{date}")
                entries_data = entries_ref.get()

                if not entries_data:
                    return Response({"error": "No entries found for the given date."}, status=404)

                # Load YOLO model
                model = YOLO("sops/best.pt")
                model.to("cuda")

                # Setup Firebase Storage
                bucket = storage.bucket()

                results = []

                def classify_vehicle_state(labels):
                    labels = [label.lower() for label in labels]
                    if "empty" in labels:
                        return "empty no trash"
                    elif "cover" in labels:
                        return "covered with tripal"
                    elif "uncover" in labels:
                        return "uncovered filled with trash"
                    else:
                        return "unknown"

                def fetch_and_process_image(img_key, img_path):
                    try:
                        blob = bucket.blob(img_path)
                        if blob.exists():
                            image_data = blob.download_as_bytes()
                            image = Image.open(io.BytesIO(image_data)).convert('RGB')
                            image = image.resize((640, 640))

                            detections = model(image)[0]
                            labels = [model.names[int(cls)] for cls in detections.boxes.cls]
                            state = classify_vehicle_state(labels)
                            return (img_key, state, labels)
                        else:
                            return (img_key, "unknown", [])
                    except Exception:
                        return (img_key, "unknown", [])

                for key, value in entries_data.items():

                    if key == 'lastEntry' or not isinstance(value, list):
                        continue

                    for sub_key, sub_value in enumerate(value):
                        if not isinstance(sub_value, dict):
                            continue

                        try:
                            image_states = {}
                            raw_labels = {}

                            # Define image paths
                            image_paths = {
                                "image01": f"Sikar/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/tripFullImage.jpg",
                                "image02": f"Sikar/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/tripFullImage2.jpg",
                                "image03": f"Sikar/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/yardEmptyImage.jpg",
                                "image04": f"Sikar/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/yardFullImage.jpg",
                            }

                            # Fetch images in parallel
                            with ThreadPoolExecutor(max_workers=4) as executor:
                                futures = {
                                    executor.submit(fetch_and_process_image, img_key, img_path): img_key
                                    for img_key, img_path in image_paths.items()
                                }

                                for future in futures:
                                    img_key, state, labels = future.result()
                                    image_states[img_key] = state
                                    raw_labels[img_key] = labels

                            # Format prompt using available image state data and ask Gemini to decide
                            prompt = f"""
                            You are analyzing a vehicle trip based on detections from 4 images. The expected detection sequence is:
                            1. uncover
                            2. covered
                            3. empty
                            4. uncover
    
                            Each image has been classified into one of these states: "uncovered", "covered", "empty", or "unknown" (means image missing).
    
                            Check if the detections match the expected order exactly. If all match, the trip is correct. If any mismatch or unknown exists, the trip is incorrect. Explain what went wrong in 'remark'.
    
                            Respond in the following JSON format:
                            {{
                              "key": "{key}/{sub_key}",
                              "detecteds_image01": "{image_states['image01']}", # this should be uncovered filled with trash
                              "detecteds_image02": "{image_states['image02']}", #  this should be covered with tripal
                              "detecteds_image03": "{image_states['image03']}", # this shuld be empty no trash
                              "detecteds_image04": "{image_states['image04']}", # this should be uncovered filled with trash
                              "remark": "<State 'Trip for zone {key}/{sub_key} is correct.' if all 4 match. Else state 'Trip for zone {key}/{sub_key} incorrect.' and mention which detecteds_image(s) are incorrect or missing.Always use the word 'missing' instead of 'unknown' in the remark.> and give reson why its incorrect"
                            }}
    
                            find key subkey from prompt
                            """

                            result_raw = call_gemini_api(prompt)
                            result = json.loads(result_raw)
                            print(result)

                            results.append({
                                "raw_detections": result['remark']
                            })

                        except Exception as e:
                            results.append({
                                "key": f"{key}/{sub_key}",
                                "status": "Error processing images",
                                "error": str(e)
                            })

            return Response({
                "date": date,
                "total_entries": len(results),
                "results": results
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PlanCreatedForDustbin(APIView):
    def post(self, request):
        # Get date from query param, fallback to yesterday
        date_param = request.GET.get('date')
        if date_param:
            date = date_param
        else:
            date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        year, month_num, day = date.split("-")
        month_name_map = {
            "01": "January", "02": "February", "03": "March", "04": "April",
            "05": "May", "06": "June", "07": "July", "08": "August",
            "09": "September", "10": "October", "11": "November", "12": "December"
        }
        month_name = month_name_map.get(month_num)

        # Fetch data from Firebase
        entries_ref = db.reference(f"/DustbinData/DustbinAssignment/{year}/{month_name}/{date}")
        entries_data = entries_ref.get()
        plan_created = []
        for key, value in entries_data.items():
            if value['planName'] == '':
                continue
            else:
                plan_created.append({key: value})
        print(plan_created)

        return Response({
            "date": date,
            "results": plan_created
        })


class NoBotAskGeminiAPIDustbinStatus(APIView):
    def send_dustbin_report_email(self, results, recipients, date=None):
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        subject = f"Dustbin Status Report - {date}"
        from_email = "muskan.wevois@gmail.com"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
                th {{ background-color: #f2f2f2; }}
                .image-links div {{ margin-bottom: 4px; }}
            </style>
        </head>
        <body>
            <h2>Dustbin Report for {date}</h2>
            <p>Total entries: {len(results)}</p>
            <table>
                <thead>
                    <tr>
                        <th>Entry ID</th>
                        <th>Pick DateTime</th>
                        <th>Picked By</th>
                        <th>Zone</th>
                        <th>Remark</th>
                        <th>Image Links</th>
                        <th>Results</th>
                        <th>Confirm (Yes/No)</th>
                    </tr>
                </thead>
                <tbody>
        """

        for entry in results:
            image_links_html = ""
            for label, url in entry["image_urls"].items():
                image_links_html += f'<div>🔹 <strong>{label.replace("_", " ").title()}</strong>: <a href="{url}" target="_blank">View</a></div>'

            html_content += f"""
                <tr>
                    <td>{entry.get("Bin/PlanId", "")}</td>
                    <td>{entry.get("pickDateTime", "")}</td>
                    <td>{entry.get("pickedBy_name", "")}</td>
                    <td>{entry.get("zone", "")}</td>
                    <td>{entry.get("remark", "")}</td>
                    <td>{image_links_html}</td>
                    <td>[Reply with Yes/No]</td>
                </tr>
            """

        html_content += """
                </tbody>
            </table>
            <p>Please reply to this email with "Yes" or "No" for each entry confirmation.</p>
        </body>
        </html>
        """

        msg = EmailMultiAlternatives(subject, "Dustbin Report attached below", from_email, recipients)
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    def get(self, request):

        IMAGE_RELEVANT_CLASSES = {
            "after_removed_trash_far_from_dustbin": ["outside trash dustbin", "outside no trash near dustbin"],
            "after_removing_trash_from_top_view": ["empty dustbin", "10 percent fill dustbin", "30 percent fill dustbin", "50 percent fill dustbin", "80 percent fill dustbin", "100 percent fill dustbin", "120 percent fill dustbin"],
            "before_any_trash_detected_far_dustbin": ["outside trash dustbin", "outside no trash near dustbin"],
            "before_dustbin_fill_in_start_top_view": ["empty dustbin", "10 percent fill dustbin", "30 percent fill dustbin", "50 percent fill dustbin", "80 percent fill dustbin", "100 percent fill dustbin", "120 percent fill dustbin"],
        }

        def classify_state(labels):
            labels = [label.lower().strip() for label in labels]
            if "outside no trash near dustbin" in labels:
                return "No trash detected outside near dustbin area"
            elif "outside trash dustbin" in labels:
                return "trash detected outside dustbin area"
            elif "120 percent fill dustbin" in labels:
                return "120 percent fill dustbin"
            elif "100 percent fill dustbin" in labels:
                return "100 percent fill dustbin"
            elif "80 percent fill dustbin" in labels:
                return "80 percent fill dustbin"
            elif "50 percent fill dustbin" in labels:
                return "50 percent fill dustbin"
            elif "30 percent fill dustbin" in labels:
                return "30 percent fill dustbin"
            elif "10 percent fill dustbin" in labels:
                return "10 percent fill dustbin"
            elif "empty dustbin" in labels:
                return "empty dustbin"
            elif "fill dustbin" in labels:
                return "100 percent fill dustbin"
            else:
                print("Unmatched labels:", labels)
                return "unknown"

        def fetch_and_process_image(img_key, img_path):
            try:
                blob = bucket.blob(img_path)
                if blob.exists():

                    image_data = blob.download_as_bytes()
                    image = Image.open(io.BytesIO(image_data)).convert('RGB')
                    image = image.resize((640, 640))

                    # Run inference
                    detections = model(image)[0]

                    # Draw and save detections locally
                    output_dir = f"media/detected_images/{datetime.now().strftime('%Y%m%d')}"
                    os.makedirs(output_dir, exist_ok=True)

                    # Save image with detections
                    output_path = os.path.join(output_dir, f"{uuid.uuid4()}.jpg")
                    detections.save(filename=output_path)

                    # Display image (optional)
                    img = cv2.imread(output_path)
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    labels = [model.names[int(cls)] for cls in detections.boxes.cls]

                    # Filter labels based on image type
                    relevant_classes = IMAGE_RELEVANT_CLASSES.get(img_key, [])
                    filtered_labels = [label for label in labels if label in relevant_classes]

                    state = classify_state(filtered_labels)
                    return (img_key, state, filtered_labels)
                else:
                    return (img_key, "image not found", [])
            except Exception as e:
                print(f"Error processing image {img_key}: {e}")
                return (img_key, "error processing image", [])

        model = YOLO("automatedsop/best.pt")
        for site in site_info:
            site_name = site["site_name"]
            db_name = site['firebase_db']
            email = site["email"]
            formatted_site_name = site_name.lower().replace(" ", "-")
            app_name = f"{formatted_site_name}-app"

            try:
                cred = credentials.Certificate("sops/cert.json")
                app = initialize_app(cred, {
                    'databaseURL': f'https://{db_name}.firebaseio.com/',
                    'storageBucket': f'dtdnavigator.appspot.com'
                }, name=app_name)
            except Exception as init_err:
                print(f"❌ Failed to init app for {site_name}: {init_err}")
                continue

            date = (datetime.today()).strftime("%Y-%m-%d")
            year, month_num, day = date.split("-")
            month_name = {
                "01": "January", "02": "February", "03": "March", "04": "April",
                "05": "May", "06": "June", "07": "July", "08": "August",
                "09": "September", "10": "October", "11": "November", "12": "December"
            }[month_num]

            employee_detail_data = db.reference("/EmployeeDetailData").get()
            ref = db.reference(f"/DustbinData/DustbinPickHistory/{year}/{month_name}/{date}", app=app)
            pick_data = ref.get()
            if not pick_data:
                continue

            bucket = storage.bucket(app=app)
            results = []

            for key, value in pick_data.items():
                if key == "lastEntry":
                    continue
                for zone_id, sub_val in value.items():
                    image_urls = {}
                    image_states = {}
                    raw_labels = {}

                    image_paths = {
                            "is_dustbin_fill_in_start_top_view": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{zone_id}/filledTopViewImage.jpg",
                            "is_any_trash_detected_near_dustbin": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{zone_id}/filledFarFromImage.jpg",
                            "after_removing_trash_from_inside": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{zone_id}/emptyTopViewImage.jpg",
                            "after_removed_trash_near_from_dustbin": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{zone_id}/emptyFarFromImage.jpg"
                    }


                    for img_key, img_path in image_paths.items():
                        url = value.get("Image", {}).get("Urls", {}).get(img_key, f"URL not found for {img_key}")
                        image_urls[img_key] = url
                        img_key, state, labels = fetch_and_process_image(img_key, img_path)
                        image_states[img_key] = state
                        raw_labels[img_key] = labels

                    # Analysis logic
                    inside_clean = image_states.get("after_removing_trash_from_inside") == 'empty dustbin'
                    outside_clean = image_states.get("after_removed_trash_near_from_dustbin") == 'No trash detected outside near dustbin area'

                    if inside_clean:
                        inside_remark = 'Trash removed from inside properly'
                    else:
                        inside_remark = 'Trash is not removed from inside properly'

                    if outside_clean:
                        outside_remark = 'Trash properly removed near 50 meter area'
                    else:
                        outside_remark = 'Trash is not removed properly near 50 meter area'

                    if inside_clean and outside_clean:
                        remark = 'work done properly'
                    elif not inside_clean and not outside_clean:
                        remark = 'Trash is not removed properly from inside and outside the 50 meter area.'
                    elif not inside_clean:
                        remark = 'Trash is not removed properly from inside the dustbin.'
                    else:
                        remark = 'Trash is not removed properly near the 50 meter area.'

                    if remark == 'work done properly':
                        continue
                    else:
                        address = sub_val.get("address", "")
                        pick_datetime = sub_val.get("pickDateTime", "")
                        pickedBy = sub_val.get("pickedBy", "")
                        pickedby_name = ""
                        for emp_id, emp in dict(employee_detail_data).items():
                            if emp_id == pickedBy:
                                pickedby_name = emp.get("name", "")
                                break
                        zone = sub_val.get("zone", "")

                        results.append({
                            "Bin/PlanId": key,
                            "address": address,
                            "pickDateTime": pick_datetime,
                            "pickedBy": pickedby_name,
                            "zone": zone,
                            "remark": remark,
                            "image_urls": image_urls
                        })

            if results:
                print("SENDING MAILS")
                self.send_dustbin_report_email(results, ["harshitshrimalee22@gmail.com"], date)
        return Response({"status": "Dustbin status report generated and emailed."})

class GetDataForMonitoringTeamWasteCollectionApi(APIView):
    permission_classes = [AllowAny]

    # Helper function to calculate work time

    def convert_to_12hr_format(self, time_str):
        try:
            # Try parsing the time assuming it's in HH:MM format (24-hour)
            time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.strftime("%I:%M %p")  # Convert to 12-hour format with AM/PM
        except ValueError:
            return time_str  # Return the original value if the format is invalid

    def calculate_work_time(self, duty_in_time, duty_out_time):
        if not duty_in_time or not duty_out_time:
            return ""
        fmt = "%H:%M"
        try:
            in_time = datetime.strptime(duty_in_time, fmt)
            out_time = datetime.strptime(duty_out_time, fmt)
            if out_time < in_time:
                out_time += timedelta(days=1)
            duration = out_time - in_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes = remainder // 60
            return f"{hours}h {minutes}m"
        except Exception:
            return ""

    def post(self, request, *args, **kwargs):
        # Default date: yesterday
        date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        city = request.data.get('city', 'nawa')
        date = request.data.get('date', date)

        if not city or city.lower() not in FIREBASE_DB_MAP:
            return Response({'error': 'Invalid or missing city'}, status=status.HTTP_400_BAD_REQUEST)

        db_name = FIREBASE_DB_MAP[city.lower()]
        database_url = f'https://{db_name}.firebaseio.com/'
        app_name = f'app_{db_name}'

        if not firebase_admin._apps.get(app_name):
            firebase_admin.initialize_app(cred, {
                'databaseURL': database_url
            }, name=app_name)

        app = firebase_admin.get_app(app_name)

        try:
            year, month_num, day = date.split("-")
        except ValueError:
            return Response({'error': "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        month_name_map = {
            "01": "January", "02": "February", "03": "March", "04": "April",
            "05": "May", "06": "June", "07": "July", "08": "August",
            "09": "September", "10": "October", "11": "November", "12": "December"
        }
        month_name = month_name_map.get(month_num)
        if not month_name:
            return Response({'error': 'Invalid month in date.'}, status=status.HTTP_400_BAD_REQUEST)

        formatted_data = []

        # Fetch all zones
        zones_ref_path = f'WasteCollectionInfo'
        zones_ref = db.reference(zones_ref_path, app=app)
        zones_list = zones_ref.get(shallow=True)  # ✅ Only keys, no big data

        if not zones_list:
            return Response([], status=status.HTTP_200_OK)

        for zone in zones_list.keys():
            # Now directly go to required path: zone/year/month/date
            date_ref_path = f'WasteCollectionInfo/{zone}/{year}/{month_name}/{date}'
            date_ref = db.reference(date_ref_path, app=app)
            date_details = date_ref.get()

            if not date_details:
                continue

            worker_details = date_details.get("WorkerDetails", {})
            line_status = date_details.get("LineStatus", {})
            summary = date_details.get("Summary", {})

            vehicle = worker_details.get("vehicle", "")
            driver_id = worker_details.get("driver", "")
            helper_id = worker_details.get("helper", "")
            second_helper_id = worker_details.get("secondHelper", "")

            duty_in_time = summary.get("dutyInTime", "")
            duty_out_time = summary.get("dutyOutTime", "")
            trip = summary.get('trip', '')

            work_time = self.calculate_work_time(
                summary.get("dutyInTime", ""), summary.get("dutyOutTime", "")
            )

            run_km = f'LocationHistory/{zone}/{year}/{month_name}/{date}/TotalCoveredDistance'
            run_km = db.reference(run_km, app=app)
            run_km = run_km.get()

            entry = {
                "Date": date,
                "City": city,
                "Zone": zone,
                "Start Time": self.convert_to_12hr_format(summary.get("dutyInTime", "")),
                "End Time": self.convert_to_12hr_format(summary.get("dutyOutTime", "")),
                "Vehicle": vehicle,
                "Driver Employee Id": driver_id,
                "Helper Employee Id": helper_id,
                'trip': trip,
                "Second Helper Employee Id": second_helper_id,
                "Work Time": work_time,
                "Work Percentage": summary.get("workPercentage", ""),
                "Run KM": f"{run_km / 1000} km" if run_km else "",  # Convert to kilometers
                "Zone Run KM": f"{summary.get('wardCoveredDistance', 0) / 1000} km" if summary.get(
                    "wardCoveredDistance") else "",  # Convert to kilometers
                "Remark": summary.get("remark", ""),

            }

            formatted_data.append(entry)

            # if isinstance(line_status, list):
            #     for trip_data in line_status:
            #         print(trip_data)
            #         if trip_data == None:
            #             continue
            #         # Assuming each entry is a dictionary, e.g., {'Status': 'LineCompleted', 'line-distance': '125'}
            #         entry = {
            #             "Date": date,
            #             "City": city,
            #             "Zone": zone,
            #             "Start Time": trip_data.get("start-time", ""),
            #             "End Time": trip_data.get("end-time", ""),
            #             "Vehicle": vehicle,
            #             "Driver Employee Id": driver_id,
            #             "Helper Employee Id": helper_id,
            #             "Second Helper Employee Id": second_helper_id,
            #             "Status": trip_data.get("Status", ""),
            #             "Line Distance": trip_data.get("line-distance", ""),
            #             "Work Time": work_time,
            #             "Work Percentage": summary.get("workPercentage", ""),
            #             "Run KM": summary.get("runKm", ""),
            #             "Zone Run KM": summary.get("zoneRunKm", ""),
            #             "Remark": summary.get("remark", ""),
            #             'trip':trip
            #         }
            #
            # else:
            #     # Log or skip if it's not a list
            #     print(f"Unexpected line_status type for zone {zone} on {date}: {type(line_status)}")

        return Response(formatted_data, status=status.HTTP_200_OK)


class GetDataForMonitoringTeamWasteCollectionAllCityApi(APIView):
    permission_classes = [AllowAny]

    # Helper function to calculate work time

    def convert_to_12hr_format(self, time_str):
        try:
            # Try parsing the time assuming it's in HH:MM format (24-hour)
            time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.strftime("%I:%M %p")  # Convert to 12-hour format with AM/PM
        except ValueError:
            return time_str  # Return the original value if the format is invalid

    def calculate_work_time(self, duty_in_time, duty_out_time):
        if not duty_in_time or not duty_out_time:
            return ""
        fmt = "%H:%M"
        try:
            in_time = datetime.strptime(duty_in_time, fmt)
            out_time = datetime.strptime(duty_out_time, fmt)
            if out_time < in_time:
                out_time += timedelta(days=1)
            duration = out_time - in_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes = remainder // 60
            return f"{hours}h {minutes}m"
        except Exception:
            return ""

    def post(self, request, *args, **kwargs):
        # Default date: yesterday
        date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        date = request.data.get('date', date)

        # If no city is specified, fetch data for all cities
        cities_to_fetch = FIREBASE_DB_MAP.keys()

        all_data = []

        for city in cities_to_fetch:
            db_name = FIREBASE_DB_MAP[city]
            database_url = f'https://{db_name}.firebaseio.com/'
            app_name = f'app_{db_name}'

            if not firebase_admin._apps.get(app_name):
                firebase_admin.initialize_app(cred, {
                    'databaseURL': database_url
                }, name=app_name)

            app = firebase_admin.get_app(app_name)

            try:
                year, month_num, day = date.split("-")
            except ValueError:
                return Response({'error': "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

            month_name_map = {
                "01": "January", "02": "February", "03": "March", "04": "April",
                "05": "May", "06": "June", "07": "July", "08": "August",
                "09": "September", "10": "October", "11": "November", "12": "December"
            }
            month_name = month_name_map.get(month_num)
            if not month_name:
                return Response({'error': 'Invalid month in date.'}, status=status.HTTP_400_BAD_REQUEST)

            formatted_data = []

            # Fetch all zones
            zones_ref_path = f'WasteCollectionInfo'
            zones_ref = db.reference(zones_ref_path, app=app)
            zones_list = zones_ref.get(shallow=True)  # ✅ Only keys, no big data

            if not zones_list:
                continue  # Skip if no zones are found

            for zone in zones_list.keys():
                # Now directly go to required path: zone/year/month/date
                date_ref_path = f'WasteCollectionInfo/{zone}/{year}/{month_name}/{date}'
                date_ref = db.reference(date_ref_path, app=app)
                date_details = date_ref.get()

                if not date_details:
                    continue
                print('hello')

                worker_details = date_details.get("WorkerDetails", {})
                line_status = date_details.get("LineStatus", {})
                summary = date_details.get("Summary", {})

                vehicle = worker_details.get("vehicle", "")
                driver_id = worker_details.get("driver", "")
                helper_id = worker_details.get("helper", "")
                second_helper_id = worker_details.get("secondHelper", "")

                duty_in_time = summary.get("dutyInTime", "")
                duty_out_time = summary.get("dutyOutTime", "")
                trip = summary.get('trip', '')

                work_time = self.calculate_work_time(
                    summary.get("dutyInTime", ""), summary.get("dutyOutTime", "")
                )

                run_km = f'LocationHistory/{zone}/{year}/{month_name}/{date}/TotalCoveredDistance'
                run_km = db.reference(run_km, app=app)
                run_km = run_km.get()

                entry = {
                    "Date": date,
                    "City": city,
                    "Zone": zone,
                    "Start Time": self.convert_to_12hr_format(summary.get("dutyInTime", "")),
                    "End Time": self.convert_to_12hr_format(summary.get("dutyOutTime", "")),
                    "Vehicle": vehicle,
                    "Driver Employee Id": driver_id,
                    "Helper Employee Id": helper_id,
                    'trip': trip,
                    "Second Helper Employee Id": second_helper_id,
                    "Work Time": work_time,
                    "Work Percentage": summary.get("workPercentage", ""),
                    "Run KM": f"{run_km / 1000} km" if run_km else "",  # Convert to kilometers
                    "Zone Run KM": f"{summary.get('wardCoveredDistance', 0) / 1000} km" if summary.get(
                        "wardCoveredDistance") else "",  # Convert to kilometers
                    "Remark": summary.get("remark", ""),
                }

                formatted_data.append(entry)

            all_data.extend(formatted_data)  # Add the data of the current city to the overall result

        return Response(all_data, status=status.HTTP_200_OK)


class GetWasteCollectionDataView(APIView):
    permission_classes = [AllowAny]

    def calculate_work_time(self, duty_in_time, duty_out_time):
        if not duty_in_time or not duty_out_time:
            return ""
        fmt = "%H:%M"
        try:
            in_time = datetime.strptime(duty_in_time, fmt)
            out_time = datetime.strptime(duty_out_time, fmt)
            if out_time < in_time:
                out_time += timedelta(days=1)
            duration = out_time - in_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes = remainder // 60
            return f"{hours}h {minutes}m"
        except Exception:
            return ""

    def get_days_in_month(self, year, month_name):
        month_num = list(calendar.month_name).index(month_name)
        if month_num == 0:
            return []
        days = calendar.monthrange(int(year), month_num)[1]
        return [f"{year}-{str(month_num).zfill(2)}-{str(day).zfill(2)}" for day in range(1, days + 1)]

    def get_months_in_year(self, year):
        return list(calendar.month_name[1:])  # Jan-Dec

    def get_years_for_zone(self, zone_filter, app):
        ref = db.reference(f"WasteCollectionInfo/{zone_filter}", app=app)
        years_data = ref.get()
        return years_data.keys() if years_data else []

    def get(self, request, *args, **kwargs):
        zone_filter = request.query_params.get("zone")
        all_zones = []

        db_url = 'https://dtdnavigator.firebaseio.com/'
        app_name = 'waste_app'

        if not firebase_admin._apps.get(app_name):
            firebase_admin.initialize_app(cred, {
                'databaseURL': db_url
            }, name=app_name)

        app_instance = firebase_admin.get_app(app_name)

        ref_root = db.reference("WasteCollectionInfo", app=app_instance)

        if zone_filter:
            all_zones = [zone_filter]
        else:
            zones_data = ref_root.get()
            if not zones_data:
                return Response({"error": "No zones found."}, status=status.HTTP_404_NOT_FOUND)
            all_zones = list(zones_data.keys())

        try:
            formatted_data = []

            for zone in all_zones:
                years_list = self.get_years_for_zone(zone, app_instance)

                if not years_list:
                    continue

                for year_filter in years_list:
                    month_list = self.get_months_in_year(year_filter)

                    for month_filter in month_list:
                        date_list = self.get_days_in_month(year_filter, month_filter)

                        ref = db.reference(f"WasteCollectionInfo/{zone}/{year_filter}/{month_filter}", app=app_instance)
                        month_data = ref.get()

                        if not month_data:
                            continue

                        for date_filter in date_list:
                            date_ref = db.reference(
                                f"WasteCollectionInfo/{zone}/{year_filter}/{month_filter}/{date_filter}",
                                app=app_instance)
                            date_details = date_ref.get()

                            if not date_details:
                                continue

                            worker_details = date_details.get("WorkerDetails", {})
                            line_status = date_details.get("LineStatus", {})
                            summary = date_details.get("Summary", {})

                            start_time = worker_details.get("start-time", "")
                            end_time = worker_details.get("end-time", "")
                            vehicle = worker_details.get("vehicle", "")
                            driver_id = worker_details.get("driver", "")
                            helper_id = worker_details.get("helper", "")
                            second_helper_id = worker_details.get("secondHelper", "")

                            work_time = self.calculate_work_time(
                                summary.get("dutyInTime", ""), summary.get("dutyOutTime", "")
                            )

                            if isinstance(line_status, list):
                                for trip_data in line_status:
                                    if isinstance(trip_data, dict):
                                        entry = {
                                            "Date": date_filter,
                                            "City": "",  # Placeholder
                                            "Zone": zone,
                                            "Start Time": trip_data.get("start-time", ""),
                                            "End Time": trip_data.get("end-time", ""),
                                            "Vehicle": vehicle,
                                            "Driver Employee Id": driver_id,
                                            "Helper Employee Id": helper_id,
                                            "Second Helper Employee Id": second_helper_id,
                                            "Work Time": work_time,
                                            "Work Percentage": summary.get("workPercentage", ""),
                                            "Run KM": summary.get("runKm", ""),
                                            "Zone Run KM": summary.get("zoneRunKm", ""),
                                            "Remark": summary.get("remark", "")
                                        }
                                        formatted_data.append(entry)

            return Response(formatted_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Create your views here.
