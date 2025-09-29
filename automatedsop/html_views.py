from django.shortcuts import render
from .models import TripValidationReport, FuelValidationReport, EmployeeSOPReport
from datetime import datetime


def tripal_report_view(request):
    date = request.GET.get('date')
    site_name = request.GET.get('site_name')

    filters = {}
    if date:
        filters['date'] = date
    if site_name:
        filters['site_name'] = site_name

    reports = TripValidationReport.objects.filter(**filters).order_by(
        'created_at') if filters else TripValidationReport.objects.all().order_by('-created_at')[:100]

    return render(request, "tripal_report.html", {
        "reports": reports,
        "filter_date": date,
        "filter_site_name": site_name
    })


def fuel_report_view(request):
    date = request.GET.get("date")
    site_name = request.GET.get("site_name")

    reports = FuelValidationReport.objects.all()

    if date:
        reports = reports.filter(date=date)

    if site_name:
        reports = reports.filter(site_name__iexact=site_name)

    # Get unique site names for dropdown options
    all_sites = FuelValidationReport.objects.values_list("site_name", flat=True).distinct()

    return render(request, "fuel.html", {
        "reports": reports,
        "filter_date": date,
        "filter_site": site_name,
        "all_sites": all_sites,
    })


def sop_te_report_view(request):
    selected_site = request.GET.get('site')
    selected_date = request.GET.get('date')

    reports = EmployeeSOPReport.objects.all().order_by('-date')

    if selected_site:
        reports = reports.filter(site_name__iexact=selected_site)

    if selected_date:
        try:
            parsed_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
            reports = reports.filter(date=parsed_date)
        except ValueError:
            pass  # Invalid date, ignore the filter

    all_sites = EmployeeSOPReport.objects.values_list('site_name', flat=True).distinct()

    return render(request, 'sop_te.html', {
        'reports': reports,
        'all_sites': all_sites,
        'selected_site': selected_site,
        'selected_date': selected_date,
    })
