class NoBotAskGeminiAPIDustbinStatus(APIView):

    def post(self, request):

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
                    print('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
                    detections = model(image)[0]
                    labels = [model.names[int(cls)] for cls in detections.boxes.cls]
                    print(f"{img_key}: {labels}")
                    state = classify_state(labels)
                    return (img_key, state, labels)
                else:
                    print(f"Image not found in bucket: {img_path}")
                    return (img_key, "model currently unable to detect", [])
            except Exception as e:
                print(f"Error processing image {img_key}: {e}")
                return (img_key, "image not found", [])

        model = YOLO("sops/dustbin_best.pt")
        model.to("cuda")
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
            date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

            year, month_num, day = date.split("-")
            month_name_map = {
                "01": "January", "02": "February", "03": "March", "04": "April",
                "05": "May", "06": "June", "07": "July", "08": "August",
                "09": "September", "10": "October", "11": "November", "12": "December"
            }
            month_name = month_name_map.get(month_num)

            entries_ref = db.reference(f"/DustbinData/DustbinAssignment/{year}/{month_name}/{date}", app=app)

            entries_data = entries_ref.get()
            print(entries_data)
            if entries_data == None:
                continue
            plan_created = []
            for key, value in entries_data.items():
                if value['planName'] == '':
                    continue
                else:
                    plan_created.append({key: value})
            print(plan_created)
            for plan in plan_created:
                print(plan)

                for zone1, value in plan.items():
                    plan_name = value['planName']
                    pick_plan_ref = db.reference(
                        f'/DustbinData/DustbinPickingPlanHistory/{year}/{month_name}/{date}/{zone1}', app=app)
                    plan = pick_plan_ref.get()
                    print(plan)
                    assign_bin = plan['bins']
                    pick_bin = plan['pickedDustbin']

                    # Convert comma-separated strings to sorted sets of integers
                    assign_bin_set = set(int(x.strip()) for x in assign_bin.split(','))
                    pick_bin_set = set(int(x.strip()) for x in pick_bin.split(','))

                    # Check if both are equal
                    if assign_bin_set == pick_bin_set:
                        print("✅ All bins matched.")
                    else:
                        # Show differences
                        missing_bins = assign_bin_set - pick_bin_set
                        extra_bins = pick_bin_set - assign_bin_set

                        if missing_bins:
                            print(f"❌ Missing bins not picked: {missing_bins}")
                        if extra_bins:
                            print(f"❌ Extra bins picked but not assigned: {extra_bins}")
                    entries_ref = db.reference(f"/DustbinData/DustbinPickHistory/{year}/{month_name}/{date}", app=app)
                    pick_history_data = entries_ref.get()

                    filter_data = {}
                    for key, value in pick_history_data.items():
                        zone_value = list(value.keys())[0]
                        print(zone_value)
                        if str(zone_value) == zone1:
                            filter_data[key] = value
                    print(filter_data)


                    bucket = storage.bucket()
                    results = []
                    for key, value in filter_data.items():
                        if key == "lastEntry":
                            pass
                        print(key)

                        for sub_key, sub_value in value.items():
                            print(sub_value)

                            image_states = {}
                            raw_labels = {}
                            image_urls = {}
                            image_paths = {
                                "after_removed_trash_near_from_dustbin": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{sub_key}/emptyFarFromImage.jpg",
                                "after_removing_trash_from_inside": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{sub_key}/emptyTopViewImage.jpg",
                                "is_any_trash_detected_near_dustbin": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{sub_key}/filledFarFromImage.jpg",
                                "is_dustbin_fill_in_start_top_view": f"{site['folder_name']}/DustbinImages/DustbinPickHistory/{year}/{month_name}/{date}/{key}/{sub_key}/filledTopViewImage.jpg",
                            }

                            for img_key, img_path in image_paths.items():
                                img_key, state, labels = fetch_and_process_image(img_key, img_path)
                                print(img_key, state, labels, 'we are')
                                image_states[img_key] = state
                                raw_labels[img_key] = labels

                                # Detection Logic:
                            is_dustbin_fill_in_start = image_states.get("is_dustbin_fill_in_start_top_view")
                            print(is_dustbin_fill_in_start, 'xxxxxxxxxxxxxxx')

                            is_any_trash_detected_near_dustbin = image_states.get("is_any_trash_detected_near_dustbin")

                            after_removing_trash_from_inside = image_states.get("after_removing_trash_from_inside")
                            after_removed_trash_near_from_dustbin = image_states.get(
                                "after_removed_trash_near_from_dustbin")

                            print(after_removing_trash_from_inside, after_removed_trash_near_from_dustbin)

                            if after_removing_trash_from_inside == 'empty dustbin':
                                after_removing_trash_from_inside = 'Trash removed from inside properly'
                            else:
                                after_removing_trash_from_inside = 'Trash is not removed from inside properly'

                            if after_removed_trash_near_from_dustbin == 'No trash detected outside near dustbin area':
                                after_removed_trash_near_from_dustbin = 'Trash properly removed near 50 meter area'
                            else:
                                after_removed_trash_near_from_dustbin = 'Trash is not removed properly near 50 meter area'

                            if (after_removing_trash_from_inside == 'Trash removed from inside properly' and
                                    after_removed_trash_near_from_dustbin == 'Trash properly removed near 50 meter area'):
                                # Everything is fine, no remark needed
                                remark = "work done properly"

                            else:
                                # Prepare remark
                                if (after_removing_trash_from_inside != 'Trash removed from inside properly' and
                                        after_removed_trash_near_from_dustbin != 'Trash properly removed near 50 meter area'):
                                    remark = "Trash is not removed properly from inside and outside the 50 meter area."
                                elif after_removing_trash_from_inside != 'Trash removed from inside properly':
                                    remark = "Trash is not removed properly from inside the dustbin."
                                else:
                                    remark = "Trash is not removed properly near the 50 meter area."

                            address = sub_value.get("address", "")

                            try:
                                # Directly decode from UTF-8 if it's correctly encoded
                                address = address.encode('utf-8').decode('utf-8')
                            except UnicodeDecodeError:
                                pass

                            pickedBy = sub_value.get("pickedBy", "")
                            employee_data = db.reference('EmployeeDetailData', app=app).get()
                            pickedby_name = employee_data.get(pickedBy, {}).get("name", "")

                            result_json = {
                                "entry_id": f"{key}/{sub_key}",
                                'plan_name':plan_name,
                                'address': address,
                                "is_dustbin_fill_in_start": is_dustbin_fill_in_start,
                                "is_any_trash_detected_near_dustbin": is_any_trash_detected_near_dustbin,
                                "after_removing_trash_from_inside": after_removing_trash_from_inside,
                                "after_removed_trash_near_from_dustbin": after_removed_trash_near_from_dustbin,
                                "remark": remark,
                                "imageCaptureAddress": sub_value.get("imageCaptureAddress", ""),
                                "pickDateTime": sub_value.get("pickDateTime", ""),
                                "pickedBy": sub_value.get("pickedBy", ""),
                                "picked_by_name": pickedby_name,
                                "startTime": sub_value.get("startTime", ""),
                                "endTime": sub_value.get("endTime", ""),
                                "zone": sub_value.get("zone", ""),
                            }

                            results.append(result_json)
                    df = pd.DataFrame(results)

                    # Ensure reports directory exists
                    report_path = os.path.join(settings.BASE_DIR, "reports")
                    os.makedirs(report_path, exist_ok=True)

                    # Define filename and path
                    excel_filename = f"dustbin_status_report_{date}.xlsx"
                    excel_filepath = os.path.join(report_path, excel_filename)

                    # Save to Excel
                    df.to_excel(excel_filepath, index=False)
                    # Compose the email
                    email = EmailMessage(
                        subject=f"Dustbin Status Report - {date}",
                        body="Please find attached the dustbin status report.",
                        from_email="harshitshrimalee.wevois@gmail.com",
                        to=["harshitshrimalee22@gmail.com"],  # Add actual recipient
                    )

                    # Attach the Excel file
                    email.attach_file(excel_filepath)

                    # Send the email
                    email.send()
                    # Optionally remove the file after sending
                    os.remove(excel_filepath)

        return Response({
            "date": date,
            "total_entries": len(results),
            "results": results
        })
