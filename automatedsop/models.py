from django.db import models

class DustbinCity(models.Model):
    city = models.CharField(max_length=159)


class Zone(models.Model):
    name = models.CharField(max_length=144)
    city = models.ForeignKey(DustbinCity, on_delete=models.CASCADE)


class DetectImages(models.Model):
    name = models.CharField(max_length=255)
    related_zone = models.ForeignKey(Zone, on_delete=models.CASCADE)

    is_dustbin_fill_in_start_top_view = models.ImageField(upload_to='uploads/')
    is_dustbin_fill_in_start_top_view_ok = models.BooleanField(default=False)

    is_any_trash_detected_near_dustbin = models.ImageField(upload_to='uploads/')
    is_any_trash_detected_near_dustbin_ok = models.BooleanField(default=False)

    after_removing_trash_from_inside = models.ImageField(upload_to='uploads/')
    after_removing_trash_from_inside_ok = models.BooleanField(default=False)

    after_removed_trash_near_from_dustbin = models.ImageField(upload_to='uploads/')
    after_removed_trash_near_from_dustbin_ok = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)


class TripValidationReport(models.Model):
    site_name = models.CharField(max_length=100)
    zone = models.CharField(max_length=100)
    trip_number = models.CharField(max_length=20)
    driver_id = models.CharField(max_length=100)
    driver_name = models.CharField(max_length=100)
    driver_number = models.CharField(max_length=100)
    image01_state = models.CharField(max_length=100)
    image02_state = models.CharField(max_length=100)
    image03_state = models.CharField(max_length=100)
    image04_state = models.CharField(max_length=100)

    image01_path = models.URLField()
    image02_path = models.URLField()
    image03_path = models.URLField()
    image04_path = models.URLField()

    # ✅ New fields to track correctness
    image01_correct = models.BooleanField(default=False)
    image02_correct = models.BooleanField(default=False)
    image03_correct = models.BooleanField(default=False)
    image04_correct = models.BooleanField(default=False)

    remark = models.TextField()
    date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.site_name} - {self.zone} Trip-{self.trip_number}"


class FuelValidationReport(models.Model):
    site_name = models.CharField(max_length=100)
    vehicle = models.CharField(max_length=100)
    key = models.CharField(max_length=100)

    expected_amount = models.FloatField(null=True, blank=True)
    expected_volume = models.FloatField(null=True, blank=True)
    extracted_text = models.TextField()

    amount_match = models.BooleanField(default=False)
    volume_match = models.BooleanField(default=False)

    image_path = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.site_name} - {self.vehicle}"


class EmployeeSOPReport(models.Model):
    site_name = models.CharField(max_length=255, null=True, blank=True)
    employee_id = models.CharField(max_length=50)
    employee_name = models.CharField(max_length=100)
    date = models.DateField()
    arrival_time = models.TimeField(blank=True, null=True)
    departure_time = models.TimeField(blank=True, null=True)
    mobile_number = models.CharField(max_length=15)
    violation = models.TextField(blank=True)
    is_sop_followed = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.employee_name} - {self.date}"


from django.db import models


class SkipLinesReport(models.Model):
    # Ward details
    ward_key = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    # Line details
    line_no = models.IntegerField()
    date = models.DateField()
    STATUS_CHOICES = [
        ("LineCompleted", "Completed"),
        ("Skipped", "Skipped"),
        ("Unknown", "Unknown"),
    ]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Unknown")
    reason = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    repeated = models.BooleanField(default=False)

    # Driver details
    driver_id = models.CharField(max_length=100, blank=True, null=True)
    driver_name = models.CharField(max_length=200, blank=True, null=True)
    driver_mobile = models.CharField(max_length=15, blank=True, null=True)

    # Helper details
    helper_id = models.CharField(max_length=100, blank=True, null=True)
    helper_name = models.CharField(max_length=200, blank=True, null=True)
    helper_mobile = models.CharField(max_length=15, blank=True, null=True)

    # Vehicle details
    vehicle_number = models.CharField(max_length=100, blank=True, null=True)

    # Ward summary fields
    total = models.IntegerField(default=0)
    completed = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)

    def __str__(self):
        return f"Ward {self.ward_key} - Line {self.line_no} ({self.date})"