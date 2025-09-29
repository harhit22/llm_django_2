from automatedsop.models import FuelValidationReport, TripValidationReport, DustbinCity, Zone, DetectImages
from rest_framework.permissions import AllowAny
from .serializers import CitySerializer, ZoneSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.apps import apps
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.shortcuts import render
from automatedsop.models import TripValidationReport, SkipLinesReport
from datetime import datetime, timedelta
from django.db.models import Q, Count
from rest_framework.decorators import api_view
from .serializers import DriverReportSerializer
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt


class CityApiView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cities = DustbinCity.objects.all()
        serializer = CitySerializer(cities, many=True)
        return Response(serializer.data)


class ZoneApiView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get city_id from query params
        city_id = request.query_params.get('city_id')

        if city_id is not None:
            zones = Zone.objects.filter(city_id=city_id)
        else:
            return Response({"detail": "zones not found"}, status=404)

        serializer = ZoneSerializer(zones, many=True)
        return Response(serializer.data)


class DynamicReportAPIView(APIView):
    """Dynamic API that automatically detects all report models"""

    def get_report_models(self):
        """Automatically discover all models that end with 'Report' or contain report-like patterns"""
        app_models = apps.get_app_config(
            'automatedsop').get_models()  # Replace 'your_app_name' with your actual app name

        report_models = []
        report_keywords = ['report', 'log', 'record', 'detection', 'validation', 'analysis']

        for model in app_models:
            model_name_lower = model.__name__.lower()

            # Check if model name contains report keywords
            if any(keyword in model_name_lower for keyword in report_keywords):
                # Get model fields for better description
                fields = [f.name for f in model._meta.fields]

                report_models.append({
                    'model_name': model.__name__,
                    'table_name': model._meta.db_table,
                    'verbose_name': getattr(model._meta, 'verbose_name', model.__name__),
                    'fields': fields,
                    'field_count': len(fields)
                })

        return report_models

    def get(self, request):
        """Get all available report types dynamically"""
        try:
            report_models = self.get_report_models()

            formatted_reports = []
            for model_info in report_models:
                # Generate icon based on model name
                icon = self.get_model_icon(model_info['model_name'])

                formatted_reports.append({
                    'id': model_info['table_name'],
                    'name': model_info['verbose_name'],
                    'model_name': model_info['model_name'],
                    'description': f"Reports from {model_info['verbose_name']} with {model_info['field_count']} fields",
                    'icon': icon,
                    'fields': model_info['fields']
                })

            return Response({
                'success': True,
                'total_report_types': len(formatted_reports),
                'report_types': formatted_reports
            })

        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_model_icon(self, model_name):
        """Generate appropriate icon based on model name"""
        model_name_lower = model_name.lower()

        icon_mapping = {
            'dustbin': '🗑️',
            'trip': '🚛',
            'fuel': '⛽',
            'employee': '👨‍💼',
            'sop': '📋',
            'detect': '🔍',
            'validation': '✅',
            'image': '📸',
            'report': '📊'
        }

        for keyword, icon in icon_mapping.items():
            if keyword in model_name_lower:
                return icon

        return '📄'  # Default icon


def trip_validation_api(request):
    """API endpoint for React component"""
    try:
        # Get query parameters
        date = request.GET.get('date')
        site_name = request.GET.get('site_name')
        driver_name = request.GET.get('driver_name')
        only_incorrect = request.GET.get('only_incorrect', '').lower() == 'true'

        # Base queryset
        queryset = TripValidationReport.objects.all()

        # Apply filters
        if date:
            queryset = queryset.filter(date=date)

        if site_name:
            queryset = queryset.filter(site_name__icontains=site_name)

        if driver_name:
            queryset = queryset.filter(driver_name__icontains=driver_name)

        if only_incorrect:
            queryset = queryset.filter(
                Q(image01_correct=False) |
                Q(image02_correct=False) |
                Q(image03_correct=False) |
                Q(image04_correct=False)
            )

        # Order by created_at descending and limit results
        queryset = queryset.order_by('-created_at')[:100]

        # Convert to list of dictionaries
        reports_data = []
        for report in queryset:
            reports_data.append({
                'id': report.id,
                'site_name': report.site_name,
                'zone': report.zone,
                'trip_number': report.trip_number,
                'driver_name': report.driver_name,
                'driver_number': report.driver_number,
                'date': report.date.strftime('%Y-%m-%d') if report.date else None,
                'remark': report.remark,
                'image01_correct': report.image01_correct,
                'image01_path': report.image01_path,
                'image01_state': report.image01_state,
                'image02_correct': report.image02_correct,
                'image02_path': report.image02_path,
                'image02_state': report.image02_state,
                'image03_correct': report.image03_correct,
                'image03_path': report.image03_path,
                'image03_state': report.image03_state,
                'image04_correct': report.image04_correct,
                'image04_path': report.image04_path,
                'image04_state': report.image04_state,
                'created_at': report.created_at.isoformat() if report.created_at else None,
            })

        return JsonResponse({
            'success': True,
            'reports': reports_data,
            'total_count': len(reports_data)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def tripal_report_view(request):
    """Keep the existing HTML view for backward compatibility"""
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


# Additional API for statistics
def trip_validation_stats_api(request):
    """Get statistics for dashboard"""
    try:
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        total_trips = TripValidationReport.objects.count()

        incorrect_trips = TripValidationReport.objects.filter(
            Q(image01_correct=False) |
            Q(image02_correct=False) |
            Q(image03_correct=False) |
            Q(image04_correct=False)
        ).count()

        today_trips = TripValidationReport.objects.filter(date=today).count()

        week_trips = TripValidationReport.objects.filter(
            date__gte=week_ago
        ).count()

        return JsonResponse({
            'success': True,
            'stats': {
                'total': total_trips,
                'incorrect': incorrect_trips,
                'today': today_trips,
                'this_week': week_trips
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
def driver_incorrect_trip_report(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    city = request.GET.get("city")  # ✅ New city filter

    if not start_date:
        return Response({"error": "start_date is required"}, status=400)

    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_date = start_date
    except ValueError:
        return Response({"error": "Invalid date format, use YYYY-MM-DD"}, status=400)

    # Base queryset: filter by date range
    trips = TripValidationReport.objects.filter(
        date__date__gte=start_date.date(),
        date__date__lte=end_date.date()
    )

    # ✅ Apply city filter if provided
    if city:
        trips = trips.filter(site_name__icontains=city)

    # Group by driver and count incorrect trips
    driver_data = (
        trips.filter(
            Q(image01_correct=False) |
            Q(image02_correct=False) |
            Q(image03_correct=False) |
            Q(image04_correct=False)
        )
        .values("driver_id", "driver_name", "driver_number")
        .annotate(incorrect_trips=Count("id"))
        .order_by("-incorrect_trips")
    )

    serializer = DriverReportSerializer(driver_data, many=True)
    return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class FuelValidationReportAPIView(View):
    """
    API View for Fuel Validation Reports
    Supports GET requests with filtering options
    """

    def get(self, request):
        try:
            # Get query parameters
            date_filter = request.GET.get('date', None)
            site_filter = request.GET.get('site', None)
            city_filter = request.GET.get('city', None)
            print(date_filter)
            show_only_incorrect = request.GET.get('show_only_incorrect', 'false').lower() == 'true'

            # Base queryset
            queryset = FuelValidationReport.objects.all().order_by('-created_at')

            # Apply filters
            if date_filter:
                try:
                    filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                    queryset = queryset.filter(date__date=filter_date)
                except ValueError:
                    pass  # Invalid date format, skip filter

            if site_filter:
                queryset = queryset.filter(
                    site_name__icontains=site_filter
                )

            if city_filter:
                queryset = queryset.filter(
                    site_name__icontains=city_filter
                )

            if show_only_incorrect:
                queryset = queryset.filter(
                    Q(amount_match=False) | Q(volume_match=False)
                )

            # Prepare response data
            reports_data = []
            for report in queryset:
                # Get associated driver information (assuming you have a way to link this)
                driver_name = self.get_driver_name(report)
                driver_number = self.get_driver_number(report)

                report_data = {
                    'id': report.id,
                    'site_name': report.site_name,
                    'vehicle': report.vehicle,
                    'key': report.key,
                    'expected_amount': report.expected_amount,
                    'expected_volume': report.expected_volume,
                    'extracted_text': report.extracted_text,
                    'amount_match': report.amount_match,
                    'volume_match': report.volume_match,
                    'image_path': report.image_path,
                    'date': report.date.isoformat() if report.date else None,
                    'created_at': report.created_at.isoformat(),
                    'driver_name': driver_name,
                    'driver_number': driver_number,
                    'remark': self.generate_remark(report),
                }
                reports_data.append(report_data)

            # Calculate statistics
            total_reports = queryset.count()
            amount_mismatch = queryset.filter(amount_match=False).count()
            volume_mismatch = queryset.filter(volume_match=False).count()
            both_mismatch = queryset.filter(
                amount_match=False,
                volume_match=False
            ).count()

            # Today's reports
            today = timezone.now().date()
            today_reports = queryset.filter(date__date=today).count()

            # This week's reports
            week_start = today - timedelta(days=today.weekday())
            week_reports = queryset.filter(date__date__gte=week_start).count()

            response_data = {
                'success': True,
                'reports': reports_data,
                'stats': {
                    'total': total_reports,
                    'amount_mismatch': amount_mismatch,
                    'volume_mismatch': volume_mismatch,
                    'both_mismatch': both_mismatch,
                    'today': today_reports,
                    'this_week': week_reports,
                },
                'filters_applied': {
                    'date': date_filter,
                    'site': site_filter,
                    'city': city_filter,
                    'show_only_incorrect': show_only_incorrect,
                }
            }

            return JsonResponse(response_data)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'reports': [],
                'stats': {
                    'total': 0,
                    'amount_mismatch': 0,
                    'volume_mismatch': 0,
                    'both_mismatch': 0,
                    'today': 0,
                    'this_week': 0,
                }
            }, status=500)

    def get_driver_name(self, report):
        """
        Extract or lookup driver name for the fuel report
        You might need to modify this based on your data structure
        """
        # Option 1: If you have a separate Driver model linked to Vehicle
        # try:
        #     vehicle_obj = Vehicle.objects.get(vehicle_number=report.vehicle)
        #     return vehicle_obj.driver.name if vehicle_obj.driver else "N/A"
        # except Vehicle.DoesNotExist:
        #     return "N/A"

        # Option 2: If driver info is in extracted text
        # You could parse the extracted_text to find driver name

        # Option 3: Default return (modify as needed)
        return "Driver Name"  # Replace with actual logic

    def get_driver_number(self, report):
        """
        Extract or lookup driver phone number for the fuel report
        """
        # Similar logic as get_driver_name
        # Return actual phone number or None
        return None  # Replace with actual logic

    def generate_remark(self, report):
        """
        Generate appropriate remark based on validation results
        """
        remarks = []

        if not report.amount_match:
            remarks.append(f"Amount mismatch detected (Expected: ₹{report.expected_amount})")

        if not report.volume_match:
            remarks.append(f"Volume mismatch detected (Expected: {report.expected_volume}L)")

        if not remarks:
            return "All validations passed successfully."

        return " | ".join(remarks)


@method_decorator(csrf_exempt, name='dispatch')
class SkiplineValidationReportApiView(View):
    """
    API View for Skip Line Validation Reports
    Supports GET requests with filtering options
    """

    def get(self, request):
        try:
            # Get query parameters
            date_filter = request.GET.get('date', None)
            ward_filter = request.GET.get('ward', None)
            city_filter = request.GET.get('city', None)
            status_filter = request.GET.get('status', None)
            driver_filter = request.GET.get('driver', None)
            show_only_skipped = request.GET.get('show_only_skipped', 'false').lower() == 'true'
            show_only_repeated = request.GET.get('show_only_repeated', 'false').lower() == 'true'

            # Base queryset
            queryset = SkipLinesReport.objects.all().order_by('-date', '-line_no')

            # Apply filters
            if date_filter:
                try:
                    filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                    queryset = queryset.filter(date=filter_date)
                except ValueError:
                    pass  # Invalid date format, skip filter

            if ward_filter:
                queryset = queryset.filter(
                    ward_key__icontains=ward_filter
                )



            if status_filter:
                queryset = queryset.filter(
                    status__iexact=status_filter
                )

            if driver_filter:
                queryset = queryset.filter(
                    Q(driver_name__icontains=driver_filter) |
                    Q(driver_mobile__icontains=driver_filter) |
                    Q(driver_id__icontains=driver_filter)
                )

            if show_only_skipped:
                queryset = queryset.filter(status='Skipped')

            if show_only_repeated:
                queryset = queryset.filter(repeated=True)

            # Prepare response data
            reports_data = []
            for report in queryset:
                report_data = {
                    'id': report.id,
                    'ward_key': report.ward_key,
                    'city': report.city,
                    'line_no': report.line_no,
                    'date': report.date.isoformat(),
                    'status': report.status,
                    'status_display': report.get_status_display(),
                    'reason': report.reason,
                    'image_url': report.image_url,
                    'repeated': report.repeated,
                    'driver_details': {
                        'id': report.driver_id,
                        'name': report.driver_name,
                        'mobile': report.driver_mobile,
                    },
                    'helper_details': {
                        'id': report.helper_id,
                        'name': report.helper_name,
                        'mobile': report.helper_mobile,
                    },
                    'vehicle_number': report.vehicle_number,
                    'ward_summary': {
                        'total': report.total,
                        'completed': report.completed,
                        'skipped': report.skipped,
                        'completion_rate': self.calculate_completion_rate(report),
                    },
                    'remark': self.generate_remark(report),
                }
                reports_data.append(report_data)

            # Calculate statistics
            total_reports = queryset.count()
            skipped_lines = queryset.filter(status='Skipped').count()
            completed_lines = queryset.filter(status='LineCompleted').count()
            unknown_status = queryset.filter(status='Unknown').count()
            repeated_lines = queryset.filter(repeated=True).count()

            # Today's reports
            today = timezone.now().date()
            today_reports = queryset.filter(date=today).count()
            today_skipped = queryset.filter(date=today, status='Skipped').count()

            # This week's reports
            week_start = today - timedelta(days=today.weekday())
            week_reports = queryset.filter(date__gte=week_start).count()
            week_skipped = queryset.filter(date__gte=week_start, status='Skipped').count()

            # City-wise statistics
            city_stats = self.get_city_wise_stats(queryset)

            # Ward-wise statistics
            ward_stats = self.get_ward_wise_stats(queryset)

            response_data = {
                'success': True,
                'reports': reports_data,
                'stats': {
                    'total': total_reports,
                    'skipped': skipped_lines,
                    'completed': completed_lines,
                    'unknown': unknown_status,
                    'repeated': repeated_lines,
                    'skip_percentage': round((skipped_lines / total_reports * 100) if total_reports > 0 else 0, 2),
                    'completion_percentage': round((completed_lines / total_reports * 100) if total_reports > 0 else 0, 2),
                    'today': {
                        'total': today_reports,
                        'skipped': today_skipped,
                        'skip_rate': round((today_skipped / today_reports * 100) if today_reports > 0 else 0, 2),
                    },
                    'this_week': {
                        'total': week_reports,
                        'skipped': week_skipped,
                        'skip_rate': round((week_skipped / week_reports * 100) if week_reports > 0 else 0, 2),
                    },
                    'by_city': city_stats,
                    'by_ward': ward_stats[:10],  # Top 10 wards with most issues
                },
                'filters_applied': {
                    'date': date_filter,
                    'ward': ward_filter,
                    'city': city_filter,
                    'status': status_filter,
                    'driver': driver_filter,
                    'show_only_skipped': show_only_skipped,
                    'show_only_repeated': show_only_repeated,
                }
            }

            return JsonResponse(response_data)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'reports': [],
                'stats': {
                    'total': 0,
                    'skipped': 0,
                    'completed': 0,
                    'unknown': 0,
                    'repeated': 0,
                    'skip_percentage': 0,
                    'completion_percentage': 0,
                    'today': {'total': 0, 'skipped': 0, 'skip_rate': 0},
                    'this_week': {'total': 0, 'skipped': 0, 'skip_rate': 0},
                    'by_city': [],
                    'by_ward': [],
                }
            }, status=500)

    def calculate_completion_rate(self, report):
        """
        Calculate completion rate for a ward
        """
        if report.total > 0:
            return round((report.completed / report.total * 100), 2)
        return 0

    def generate_remark(self, report):
        """
        Generate appropriate remark based on skip line status and details
        """
        remarks = []

        if report.status == 'Skipped':
            remarks.append("Line was skipped")
            if report.reason:
                remarks.append(f"Reason: {report.reason}")

        if report.repeated:
            remarks.append("This is a repeated occurrence")

        if report.status == 'Unknown':
            remarks.append("Status unknown - requires investigation")

        # Ward performance insights
        if report.total > 0:
            skip_rate = (report.skipped / report.total * 100)
            if skip_rate > 20:
                remarks.append(f"High skip rate in ward: {skip_rate:.1f}%")
            elif skip_rate == 0:
                remarks.append("Perfect completion rate in this ward")

        if not remarks:
            return "Line completed successfully."

        return " | ".join(remarks)

    def get_city_wise_stats(self, queryset):
        """
        Get statistics grouped by city
        """
        from django.db.models import Count, Q

        city_stats = queryset.values('city').annotate(
            total=Count('id'),
            skipped=Count('id', filter=Q(status='Skipped')),
            completed=Count('id', filter=Q(status='LineCompleted')),
            repeated=Count('id', filter=Q(repeated=True))
        ).order_by('-skipped')

        result = []
        for city in city_stats:
            skip_rate = (city['skipped'] / city['total'] * 100) if city['total'] > 0 else 0
            result.append({
                'city': city['city'],
                'total': city['total'],
                'skipped': city['skipped'],
                'completed': city['completed'],
                'repeated': city['repeated'],
                'skip_rate': round(skip_rate, 2)
            })

        return result

    def get_ward_wise_stats(self, queryset):
        """
        Get statistics grouped by ward (sorted by issues)
        """
        from django.db.models import Count, Q

        ward_stats = queryset.values('ward_key', 'city').annotate(
            total=Count('id'),
            skipped=Count('id', filter=Q(status='Skipped')),
            completed=Count('id', filter=Q(status='LineCompleted')),
            repeated=Count('id', filter=Q(repeated=True))
        ).order_by('-skipped', '-repeated')

        result = []
        for ward in ward_stats:
            skip_rate = (ward['skipped'] / ward['total'] * 100) if ward['total'] > 0 else 0
            result.append({
                'ward_key': ward['ward_key'],
                'city': ward['city'],
                'total': ward['total'],
                'skipped': ward['skipped'],
                'completed': ward['completed'],
                'repeated': ward['repeated'],
                'skip_rate': round(skip_rate, 2),
                'issue_score': ward['skipped'] + (ward['repeated'] * 2)  # Weighted score for prioritization
            })

        return result

    def post(self, request):
        """
        Create a new skip line report entry
        """
        try:
            import json
            data = json.loads(request.body)

            # Validate required fields
            required_fields = ['ward_key', 'city', 'line_no', 'date', 'status']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)

            # Create new report
            report = SkipLinesReport.objects.create(
                ward_key=data['ward_key'],
                city=data['city'],
                line_no=data['line_no'],
                date=data['date'],
                status=data['status'],
                reason=data.get('reason', ''),
                image_url=data.get('image_url', ''),
                repeated=data.get('repeated', False),
                driver_id=data.get('driver_id', ''),
                driver_name=data.get('driver_name', ''),
                driver_mobile=data.get('driver_mobile', ''),
                helper_id=data.get('helper_id', ''),
                helper_name=data.get('helper_name', ''),
                helper_mobile=data.get('helper_mobile', ''),
                vehicle_number=data.get('vehicle_number', ''),
                total=data.get('total', 0),
                completed=data.get('completed', 0),
                skipped=data.get('skipped', 0),
            )

            return JsonResponse({
                'success': True,
                'message': 'Skip line report created successfully',
                'report_id': report.id
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)




