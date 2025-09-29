from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import TripValidationReport, EmployeeSOPReport, DustbinCity, SkipLinesReport

@admin.register(EmployeeSOPReport)
class EmployeeSOPReportAdmin(admin.ModelAdmin):
    list_display = [field.name for field in EmployeeSOPReport._meta.fields]


@admin.register(TripValidationReport)
class TripValidationReportAdmin(admin.ModelAdmin):
    list_display = (
        'site_name', 'zone', 'trip_number', 'driver_name', 'driver_number',
        'image01_correct', 'image02_correct', 'image03_correct', 'image04_correct',
        'date', 'created_at', 'remark'
    )
    list_filter = ('site_name', 'zone', 'date', 'image01_correct', 'image02_correct', 'image03_correct', 'image04_correct')
    search_fields = ('site_name', 'zone', 'trip_number', 'driver_name', 'driver_number', 'remark')
    readonly_fields = ('created_at',)

    fieldsets = (
        ("Basic Info", {
            'fields': ('site_name', 'zone', 'trip_number', 'date')
        }),
        ("Driver Info", {
            'fields': ('driver_id', 'driver_name', 'driver_number')
        }),
        ("Image States", {
            'fields': (
                ('image01_state', 'image01_correct', 'image01_path'),
                ('image02_state', 'image02_correct', 'image02_path'),
                ('image03_state', 'image03_correct', 'image03_path'),
                ('image04_state', 'image04_correct', 'image04_path'),
            )
        }),
        ("Remarks and Metadata", {
            'fields': ('remark', 'created_at'),
        }),
    )

from .models import FuelValidationReport

@admin.register(FuelValidationReport)
class FuelValidationReportAdmin(admin.ModelAdmin):
    list_display = (
        'site_name', 'vehicle', 'key',
        'amount_match', 'volume_match',
        'expected_amount', 'expected_volume',
        'date'
    )
    search_fields = ('site_name', 'vehicle', 'key')
    list_filter = ('site_name', 'amount_match', 'volume_match', 'date')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image_path:
            return f'<img src="{obj.image_path}" width="300"/>'
        return "No image"
    image_preview.allow_tags = True
    image_preview.short_description = 'Slip Image'



@admin.register(SkipLinesReport)
class SkipLinesReportAdmin(admin.ModelAdmin):
    list_display = (
        'ward_key', 'city', 'line_no',
        'date', 'status',
        'driver_name', 'driver_mobile',
        'vehicle_number', 'completed', 'skipped', 'total',
    )
    list_filter = (
        'city', 'status', 'date',
        'vehicle_number', 'driver_name',
    )
    search_fields = (
        'ward_key', 'city',
        'driver_id', 'driver_name', 'driver_mobile',
        'helper_id', 'helper_name', 'helper_mobile',
        'vehicle_number',
    )


admin.site.register(DustbinCity)