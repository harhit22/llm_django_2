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
import cv2
import firebase_admin
import numpy as np
import pandas as pd
import requests
from PIL import Image
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.http import JsonResponse
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
from .models import TripValidationReport, FuelValidationReport, EmployeeSOPReport, SkipLinesReport

from automatedsop.services.gemini_service import GeminiService
from automatedsop.services.email_service import EmailMessage
from automatedsop.services import email_service
from automatedsop.Prompt_creation_methods.promts_methods import ask_question, ask_question_fe
from automatedsop.Filter_methods.filter_firebase_service import filter_data, filter_data2

# os.environ['FLAGS_use_mkldnn'] = '0'
# os.environ['OMP_NUM_THREADS'] = '1'
# os.environ['MKL_NUM_THREADS'] = '1'
gemini = GeminiService()
email = EmailMessage()
ROLE_MAPPINGS = {
    "field executive": ["fe", "field exec", "field executive"],
    "service executive": ["se", "service exec", "service executive"],
    "transportation executive": ["te", "transportation exec", "transportation executive"]
}
ocr = PaddleOCR(use_angle_cls=False, lang='en')


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
            filename = f"{formatted_site_name}_field_exe_login_logout_sop_{date}.xlsx"
            filepath = os.path.join(report_path, filename)
            df.to_excel(filepath, index=False)
            print('sending mail')
            # Send email
            mail = EmailMessage(
                subject=f"{site_name} - field exe - {date}",
                body="Please find attached the field exe status report.",
                from_email="harshitshrimalee.wevois@gmail.com",
                to=["Wevoisdinesh@gmail.com", "harshitshrimalee22@gmail.com"],
            )
            mail.attach_file(filepath)
            mail.send()

            # Optional: Remove the file after sending
            os.remove(filepath)

        return Response({"status": "Done sending reports to all sites."})


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

                try:
                    cred = credentials.Certificate("sops/cert.json")
                    app = initialize_app(cred, {
                        'databaseURL': f'https://{db_name}.firebaseio.com/',
                        'storageBucket': f'{db_name}.appspot.com'
                    }, name=app_name)
                except Exception as init_err:
                    print(f"❌ Failed to init app for {site_name}: {init_err}")
                    continue
                print('i am here 1')
                if site_name == 'sonipath':
                    employee_data = db.reference('Employees/GeneralDetails', app=app).get()
                else:
                    employee_data = db.reference('EmployeeDetailData', app=app).get()
                print('i am here 2')
                filtered_data = filter_data(employee_data, app)
                print('i am here 3')
                # Get SOP steps
                sop_steps = SopStep.objects.filter(sop_id=2)
                sop_detail = "\n".join([step.description for step in sop_steps])

                # Ask Gemini
                response = ask_question(filtered_data, sop_detail)
                response_data = json.loads(response)
                print(response_data)
                records = response_data if isinstance(response_data, list) else [response_data]

                def parse_time_safe(time_str):
                    try:
                        return datetime.strptime(time_str, "%H:%M:%S").time()
                    except (ValueError, TypeError):
                        return None

                for record in records:
                    try:
                        emp_id = record.get("Employee ID", "")
                        record_date = datetime.strptime(record.get("Date", date), "%Y-%m-%d").date()

                        # ✅ Avoid duplicate: check if this record already exists
                        if EmployeeSOPReport.objects.filter(employee_id=emp_id, date=record_date).exists():
                            print(f"⏩ Skipping duplicate: {record.get('Employee Name')} ({emp_id}) on {record_date}")
                            continue

                        # Safe time parsing

                        # Create record
                        EmployeeSOPReport.objects.create(
                            site_name=site_name,
                            employee_id=emp_id,
                            employee_name=record.get("Employee Name", ""),
                            date=record_date,
                            arrival_time=parse_time_safe(record.get("Arrival Time")),
                            departure_time=parse_time_safe(record.get("Departure Time")),
                            mobile_number=record.get("employee mobile number", ""),
                            violation=record.get("Violation", ""),
                            is_sop_followed=str(record.get("is_sop_follow", "True")).lower() == "true"
                        )

                    except Exception as save_err:
                        print(f"⚠️ Error saving record for {record.get('Employee Name')}: {save_err}")
                report_url = f"http://35.209.151.196:8001/auto/sop-te-reports/?site={site_name}&date={date}"
                subject = f"SOP Report - {site_name.title()} - {date}"
                body = (
                    f"Hello,\n\n"
                    f"The SOP report for *{site_name.title()}* on *{date}* has been generated.\n\n"
                    f"You can view it at the following link:\n{report_url}\n\n"
                    f"Best regards,\nSOP Automation System"
                )
                email_list = "harshitshrimalee22@gmail.com, wevoisdinesh@gmail.com".replace(" ", "").split(",")

                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=email_list,
                )

                email.send()
                print(f"✅ Email sent to {email}")

            return Response({"status": "Done sending reports to all sites."})

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            date_obj = datetime.today() - timedelta(days=1)
            date = date_obj.strftime("%Y-%m-%d")

            for site in site_info:
                site_name = site["site_name"]
                db_name = site['firebase_db']
                folder_name = site['folder_name']
                email = site["email"]
                formatted_site_name = site_name.lower().replace(" ", "-")
                app_name = f"{formatted_site_name}-app"

                print(f"\n📍 Processing site: {site_name}")

                try:
                    if app_name in _apps:
                        app = _apps[app_name]
                    else:
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

                entries_ref = db.reference(f"/DieselEntriesData/{year}/{month_name}/{date}", app=app)
                entries_data = entries_ref.get()
                print(entries_data)

                if not entries_data:
                    continue

                ocr = PaddleOCR(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False)
                bucket = storage.bucket(app=app)

                results = []

                for key, value in entries_data.items():
                    if key == 'lastEntry':
                        continue

                    created_key = value['createdBy']
                    driver_ref = db.reference(f"/Employees/{created_key}/GeneralDetails", app=app)
                    driver_data = driver_ref.get()
                    print(driver_data)
                    driver_name = driver_data['name']
                    mobile_no = driver_data['mobile']

                    expected_amount = str(value.get("amount", ""))
                    expected_volume = str(value.get("quantity", ""))
                    vehicle = str(value.get("vehicle", ""))

                    blob_path = f"{folder_name}/DieselEntriesImages/{year}/{month_name}/{date}/{key}/amountSlipImage"
                    blob = bucket.blob(blob_path)

                    try:
                        time.sleep(1.5)
                        image_data = blob.download_as_bytes()
                        image = Image.open(io.BytesIO(image_data)).convert('RGB')
                        result = ocr.ocr(np.array(image))
                        extracted_text = " ".join([line[1][0] for block in result for line in block])
                        print(result)

                        prompt = f"""
                        You are given the following extracted text from an image, along with the expected amount and volume values.

                        Your task is to check if the expected amount and volume are clearly present in the extracted text.

                        If the expected value appears in a jumbled, noisy, or unclear way (e.g. OCR errors, garbled numbers), consider it as *false*, and mention that in a remark.

                        Return the result strictly in this JSON format:
                        Note: if there is no amount in extracted_text and rate is present then multiply rate by volume then check amount to the original
                        if amount is little bit off like 9.00 and extracted is 9.0 both are 9 this is ok according to SOP but 9.3 and 9.5 are not ok

                        {{
                            "amount_match": <true/false>,
                            "expected_amount": "{expected_amount}",
                            "extracted_amount": "...",
                            "volume_match": <true/false>,
                            "expected_volume": "{expected_volume}",
                            "extracted_volume": "...",
                            "remark": "<brief reason>"
                        }}

                        Extracted Text:
                        {extracted_text}
                        """

                        result_raw = GeminiService.call_api(prompt)
                        print(result_raw)
                        result = json.loads(result_raw)

                        # Save to DB
                        if True:
                            FuelValidationReport.objects.create(
                                site_name=site_name,
                                vehicle=vehicle,
                                key=key,
                                expected_amount=expected_amount,
                                expected_volume=expected_volume,
                                extracted_text=extracted_text,
                                amount_match=result.get('amount_match', False),
                                volume_match=result.get('volume_match', False),
                                image_path=f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{blob_path.replace('/', '%2F')}?alt=media",
                                date=date,

                            )

                        results.append(result)


                    except Exception as e:
                        print(e)
                        results.append({"key": key, "status": "Error processing image", "error": str(e)})

                # Optional report export (if needed)
                report_url = f"http://35.209.151.196:8001/auto/fuel-report/?date={date}&site_name={site_name}"

                mail = EmailMessage(
                    subject=f"{site_name} - fuel Validation Report - {date}",
                    body=f"The fuel validation report is ready. Click the link below to view it:\n\n{report_url}",
                    from_email="harshitshrimalee.wevois@gmail.com",
                    to=["harshitshrimalee22@gmail.com", "Wevoisdinesh@gmail.com"],
                )
                mail.send()

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
    already_processed = False

    def get(self, request):

        try:
            print(f"🔁 API called at: {datetime.now()} from {request.META.get('REMOTE_ADDR')}")
            date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
            # date = "2025-07-05"
            for site in site_info:

                site_name = site["site_name"]
                db_name = site["firebase_db"]
                email = site["email"]
                formatted_site_name = site_name.lower().replace(" ", "-")
                app_name = f"{formatted_site_name}-app"

                try:
                    cred = credentials.Certificate("sops/cert.json")
                    if app_name not in firebase_admin._apps:
                        app = initialize_app(cred, {
                            'databaseURL': f'https://{db_name}.firebaseio.com/',
                            'storageBucket': 'dtdnavigator.appspot.com'
                        }, name=app_name)
                    else:
                        app = firebase_admin.get_app(app_name)
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

                entries_ref = db.reference(f"/WardTrips/{year}/{month_name}/{date}", app=app)
                entries_data = entries_ref.get()
                if not entries_data:
                    continue

                model = YOLO("automatedsop/beest.pt")
                bucket = storage.bucket(app=app)
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
                            image_data = blob.download_as_bytes(timeout=30)
                            image = Image.open(io.BytesIO(image_data)).convert('RGB')
                            image = image.resize((416, 416))
                            detections = model(image)[0]
                            labels = [model.names[int(cls)] for cls in detections.boxes.cls]
                            state = classify_vehicle_state(labels)
                            return (img_key, state, labels)
                        else:
                            return (img_key, "unknown", [])
                    except Exception as e:
                        return (img_key, "image is not uploaded", [])

                for key, value in entries_data.items():
                    if key == 'lastEntry' or not isinstance(value, list):
                        continue

                    for sub_key, sub_value in enumerate(value):
                        if not isinstance(sub_value, dict):
                            continue

                        image_states = {}
                        raw_labels = {}

                        image_paths = {
                            "image01": f"{site['folder_name']}/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/tripFullImage.jpg",
                            "image02": f"{site['folder_name']}/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/tripFullImage2.jpg",
                            "image03": f"{site['folder_name']}/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/yardEmptyImage.jpg",
                            "image04": f"{site['folder_name']}/WardTrips/{year}/{month_name}/{date}/{key}/{sub_key}/yardFullImage.jpg",
                        }

                        with ThreadPoolExecutor(max_workers=4) as executor:
                            futures = {
                                executor.submit(fetch_and_process_image, img_key, img_path): img_key
                                for img_key, img_path in image_paths.items()
                            }

                            for future in futures:
                                img_key, state, labels = future.result()
                                image_states[img_key] = state
                                raw_labels[img_key] = labels

                        expected_order = [
                            "uncovered filled with trash",
                            "covered with tripal",
                            "empty no trash",
                            "uncovered filled with trash"
                        ]
                        detected_order = [
                            image_states.get("image01", "unknown"),
                            image_states.get("image02", "unknown"),
                            image_states.get("image03", "unknown"),
                            image_states.get("image04", "unknown")
                        ]

                        if detected_order == expected_order:
                            remark = f"Trip for zone {key}/{sub_key} is correct."
                        else:
                            incorrect_images = []
                            unknown_images = []

                            for idx, (detected, expected) in enumerate(zip(detected_order, expected_order)):
                                image_label = f"image{idx + 1}"
                                if detected == "unknown":
                                    unknown_images.append(image_label)
                                elif detected != expected:
                                    incorrect_images.append(image_label)

                            remark = f"Trip for zone {key} trip-{sub_key} is incorrect.\n"
                            if incorrect_images:
                                remark += f"Incorrect: {', '.join(incorrect_images)}.\n"
                            if unknown_images:
                                remark += f"Unknown: {', '.join(unknown_images)}."

                        print(sub_value)
                        try:

                            driver_refernce = db.reference(f"/Employees/{sub_value['driverId']}/GeneralDetails/",
                                                           app=app)
                            driver_data = driver_refernce.get()
                        except:
                            driver_data = {}
                        if 'is incorrect' in remark:
                            TripValidationReport.objects.create(
                                site_name=site_name,
                                zone=key,
                                trip_number=str(sub_key),
                                driver_id=sub_value.get("driverId", "N/A"),
                                driver_name=driver_data.get('name', ''),
                                driver_number=driver_data.get('mobile', ''),
                                image01_state=image_states.get("image01", "unknown"),
                                image02_state=image_states.get("image02", "unknown"),
                                image03_state=image_states.get("image03", "unknown"),
                                image04_state=image_states.get("image04", "unknown"),
                                image01_path=f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{image_paths['image01'].replace('/', '%2F')}?alt=media",
                                image02_path=f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{image_paths['image02'].replace('/', '%2F')}?alt=media",
                                image03_path=f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{image_paths['image03'].replace('/', '%2F')}?alt=media",
                                image04_path=f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{image_paths['image04'].replace('/', '%2F')}?alt=media",
                                image01_correct=(detected_order[0] == expected_order[0]),
                                image02_correct=(detected_order[1] == expected_order[1]),
                                image03_correct=(detected_order[2] == expected_order[2]),
                                image04_correct=(detected_order[3] == expected_order[3]),
                                date=date,
                                remark=remark
                            )
                        else:
                            continue
                report_url = f"http://35.209.151.196:8001/auto/tripal-report/?date={date}&site_name={site_name}"

                mail = EmailMessage(
                    subject=f"{site_name} - Tripal Validation Report - {date}",
                    body=f"The Tripal validation report is ready. Click the link below to view it:\n\n{report_url}",
                    from_email="harshitshrimalee.wevois@gmail.com",
                    to=["harshitshrimalee22@gmail.com"],
                )
                mail.send()

                if not results:
                    continue

                report_url = f"https://127.0.0.1:8000/auto/tripal-report/?date={date}"

                print("📧 Email with report link sent successfully")

            return Response({
                "date": date,
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
            "after_removing_trash_from_top_view": ["empty dustbin", "10 percent fill dustbin",
                                                   "30 percent fill dustbin", "50 percent fill dustbin",
                                                   "80 percent fill dustbin", "100 percent fill dustbin",
                                                   "120 percent fill dustbin"],
            "before_any_trash_detected_far_dustbin": ["outside trash dustbin", "outside no trash near dustbin"],
            "before_dustbin_fill_in_start_top_view": ["empty dustbin", "10 percent fill dustbin",
                                                      "30 percent fill dustbin", "50 percent fill dustbin",
                                                      "80 percent fill dustbin", "100 percent fill dustbin",
                                                      "120 percent fill dustbin"],
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
                    outside_clean = image_states.get(
                        "after_removed_trash_near_from_dustbin") == 'No trash detected outside near dustbin area'

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


class NoBotAskGeminiAPIViewSkipLines(APIView):
    def get(self, request):
        try:
            print(f"🔁 Skip Lines API called at: {datetime.now()} from {request.META.get('REMOTE_ADDR')}")

            # Get date range (yesterday and day before)
            today = datetime.today()
            dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 3)]
            current_date = dates[0]  # Yesterday's date

            month_name_map = {
                "01": "January", "02": "February", "03": "March", "04": "April",
                "05": "May", "06": "June", "07": "July", "08": "August",
                "09": "September", "10": "October", "11": "November", "12": "December"
            }

            # Process each site similar to tripal validation
            for site in site_info:
                site_name = site["site_name"]
                db_name = site["firebase_db"]
                email = site["email"]
                formatted_site_name = site_name.lower().replace(" ", "-")
                app_name = f"{formatted_site_name}-app"

                try:
                    cred = credentials.Certificate("sops/cert.json")
                    if app_name not in firebase_admin._apps:
                        app = initialize_app(cred, {
                            'databaseURL': f'https://{db_name}.firebaseio.com/',
                            'storageBucket': 'dtdnavigator.appspot.com'
                        }, name=app_name)
                    else:
                        app = firebase_admin.get_app(app_name)
                except Exception as init_err:
                    print(f"❌ Failed to init app for {site_name}: {init_err}")
                    continue

                bucket = storage.bucket(app=app)

                # Get ward keys from WasteCollectionInfo
                try:
                    ward_keys_ref = db.reference("WasteCollectionInfo", app=app)
                    ward_keys_data = ward_keys_ref.get(shallow=True)
                    ward_keys = list(ward_keys_data.keys()) if ward_keys_data else []
                except Exception as e:
                    print(f"❌ Failed to get ward keys for {site_name}: {e}")
                    continue

                final_results = {}
                records_created = 0

                for ward_key in ward_keys:
                    line_skips = {}
                    ward_summary = {"total": 0, "completed": 0, "skipped": 0}

                    for idx, date_str in enumerate(dates):
                        year, month_num, day = date_str.split("-")
                        month_name = month_name_map[month_num]

                        try:
                            path = f"WasteCollectionInfo/{ward_key}/{year}/{month_name}/{date_str}"
                            date_data = db.reference(path, app=app).get()
                            if not date_data:
                                continue

                            line_status_data = date_data.get("LineStatus", [])
                            worker_detail_data = date_data.get("WorkerDetails", {})

                            if not isinstance(line_status_data, list):
                                continue

                            ward_summary["total"] = len(line_status_data)

                            for line_no, line_info in enumerate(line_status_data):
                                if not isinstance(line_info, dict):
                                    continue

                                status = line_info.get("Status", "Unknown")
                                reason = line_info.get("reason", "No reason provided")

                                if status != "LineCompleted":
                                    if idx == 0:  # Current date (yesterday)
                                        # Get image URL
                                        image_path = f"{site['folder_name']}/SkipData/{ward_key}/{year}/{month_name}/{date_str}/{line_no}.jpg"
                                        blob = bucket.blob(image_path)
                                        try:
                                            if blob.exists():
                                                blob.make_public()
                                                image_url = f"https://storage.googleapis.com/{bucket.name}/{image_path}"
                                            else:
                                                image_url = None
                                        except Exception as img_err:
                                            print(f"⚠ Image error for {ward_key}/{line_no}: {img_err}")
                                            image_url = None

                                        # Get worker details
                                        driver_id = worker_detail_data.get("driver", "")
                                        driver_name = worker_detail_data.get("driverName", "")
                                        helper_id = worker_detail_data.get("helper", "")
                                        helper_name = worker_detail_data.get("helperName", "")
                                        vehicle = worker_detail_data.get("vehicle", "")

                                        # Get additional employee details
                                        driver_info = {}
                                        helper_info = {}
                                        try:
                                            if driver_id:
                                                driver_info = db.reference(f"/EmployeeDetailData/{driver_id}",
                                                                           app=app).get() or {}
                                        except:
                                            pass

                                        try:
                                            if helper_id:
                                                helper_info = db.reference(f"/EmployeeDetailData/{helper_id}",
                                                                           app=app).get() or {}
                                        except:
                                            pass

                                        driver_mobile_number = driver_info.get("mobile", "")
                                        helper_mobile_number = helper_info.get("mobile", "")

                                        line_skips[line_no] = {
                                            "reason": reason,
                                            "image_url": image_url,
                                            "driver_id": driver_id,
                                            "driver_name": driver_name,
                                            "helper_id": helper_id,
                                            "helper_name": helper_name,
                                            "driver_mobile": driver_mobile_number,
                                            "helper_mobile": helper_mobile_number,
                                            "vehicle": vehicle,
                                            "repeated": False
                                        }
                                        ward_summary["skipped"] += 1
                                    else:  # Previous day - check for repetition
                                        if line_no in line_skips:
                                            line_skips[line_no]["repeated"] = True
                                else:
                                    if idx == 0:  # Current date
                                        ward_summary["completed"] += 1

                        except Exception as err:
                            print(f"⚠ Error processing {ward_key} {date_str}: {err}")

                    # Save to database only if there are skipped lines
                    if line_skips:
                        for line_no, line_data in line_skips.items():
                            try:
                                # Create or update the skip lines record
                                skip_record, created = SkipLinesReport.objects.get_or_create(
                                    ward_key=ward_key,
                                    city=site_name,  # Using site_name as city
                                    line_no=line_no,
                                    date=current_date,
                                    defaults={
                                        'status': 'Skipped',
                                        'reason': line_data['reason'],
                                        'image_url': line_data['image_url'],
                                        'repeated': line_data['repeated'],
                                        'driver_id': line_data['driver_id'],
                                        'driver_name': line_data['driver_name'],
                                        'driver_mobile': line_data['driver_mobile'],
                                        'helper_id': line_data['helper_id'],
                                        'helper_name': line_data['helper_name'],
                                        'helper_mobile': line_data['helper_mobile'],
                                        'vehicle_number': line_data['vehicle'],
                                        'total': ward_summary['total'],
                                        'completed': ward_summary['completed'],
                                        'skipped': ward_summary['skipped']
                                    }
                                )

                                if created:
                                    records_created += 1
                                    print(f"✅ Created skip record for {site_name} - Ward {ward_key} - Line {line_no}")
                                else:
                                    # Update existing record
                                    skip_record.status = 'Skipped'
                                    skip_record.reason = line_data['reason']
                                    skip_record.image_url = line_data['image_url']
                                    skip_record.repeated = line_data['repeated']
                                    skip_record.driver_id = line_data['driver_id']
                                    skip_record.driver_name = line_data['driver_name']
                                    skip_record.driver_mobile = line_data['driver_mobile']
                                    skip_record.helper_id = line_data['helper_id']
                                    skip_record.helper_name = line_data['helper_name']
                                    skip_record.helper_mobile = line_data['helper_mobile']
                                    skip_record.vehicle_number = line_data['vehicle']
                                    skip_record.total = ward_summary['total']
                                    skip_record.completed = ward_summary['completed']
                                    skip_record.skipped = ward_summary['skipped']
                                    skip_record.save()
                                    print(f"🔄 Updated skip record for {site_name} - Ward {ward_key} - Line {line_no}")

                            except Exception as db_err:
                                print(f"❌ Database error for {ward_key}/{line_no}: {db_err}")
                                continue

                        final_results[ward_key] = {
                            "lines": line_skips,
                            "summary": ward_summary
                        }

                # Send email notification similar to tripal validation
                if final_results:
                    report_url = f"http://35.209.151.196:8001/auto/skip-lines-report/?date={current_date}&site_name={site_name}"

                    try:
                        mail = EmailMessage(
                            subject=f"{site_name} - Skip Lines Report - {current_date}",
                            body=f"The Skip Lines report is ready. Click the link below to view it:\n\n{report_url}\n\nTotal records created: {records_created}",
                            from_email="harshitshrimalee.wevois@gmail.com",
                            to=["harshitshrimalee22@gmail.com"],
                        )
                        mail.send()
                        print(f"📧 Email sent for {site_name} with {records_created} records")
                    except Exception as mail_err:
                        print(f"❌ Email sending failed for {site_name}: {mail_err}")

                print(f"✅ Processed {site_name}: {len(final_results)} wards, {records_created} records created")

            return JsonResponse({
                "message": "Skip lines data processed and saved to database",
                "date": current_date,
                "total_records_processed": records_created,
                "status": "success"
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ Main error: {e}")
            return JsonResponse({"error": str(e)}, status=500)


















# deepak
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
