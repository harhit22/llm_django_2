from django.urls import path
from .views import CityApiView, ZoneApiView
from automatedsop import views
from .views import DynamicReportAPIView, FuelValidationReportAPIView, SkiplineValidationReportApiView
from . import views
urlpatterns = [
    path("cities/", CityApiView.as_view(), name="sop1"),
    path("zones/", ZoneApiView.as_view(), name="sop2"),
    path('reports/', DynamicReportAPIView.as_view(), name='dynamic-reports'),
    path('trip-validation-reports/', views.trip_validation_api, name='trip_validation_api'),
    path('trip-validation-stats/', views.trip_validation_stats_api, name='trip_validation_stats'),
    path("driver-trip-summary/", views.driver_incorrect_trip_report, name="driver_trip_summary"),
    path("fuel-validation-reports/", FuelValidationReportAPIView.as_view(), name="fuel-validation-reports-api"),
    path("skipline-validation-reports/" ,SkiplineValidationReportApiView.as_view(), name="skipline-validation-reports"),
]