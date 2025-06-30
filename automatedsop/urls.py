from django.urls import path
from .views import  NoBotAskGeminiAPIView, NoBotAskGeminiAPIViewTransportExec, \
    NoBotAskGeminiAPIViewSkipLines, OCRDieselSlipValidationAPIView, SendCitiesDataAPIView, SendSopDataApiView,\
    NoBotAskGeminiAPItripalstatus, NoBotAskGeminiAPIDustbinStatus, GetDataForMonitoringTeamWasteCollectionApi,\
    GetDataForMonitoringTeamWasteCollectionAllCityApi, PlanCreatedForDustbin, GetWasteCollectionDataView

urlpatterns = [
    path("sop1/", NoBotAskGeminiAPIView.as_view(), name="sop1"),
    path("sop2/", NoBotAskGeminiAPIViewTransportExec.as_view(), name="sop2"),
    path("sop21/", NoBotAskGeminiAPIViewSkipLines.as_view(), name="sop1"),
    path("sop26/", OCRDieselSlipValidationAPIView.as_view(), name="sop1"),
    path("sop13/", NoBotAskGeminiAPItripalstatus.as_view(), name="sop13"),
    path("sop29/", NoBotAskGeminiAPIDustbinStatus.as_view(), name="sop29"),
    path("sop29-plans/", PlanCreatedForDustbin.as_view(), name="sop29"),
    path('api/cities/', SendCitiesDataAPIView.as_view(), name='send-cities-data'),
    path('api/sops/', SendSopDataApiView.as_view(), name='send-sop-data'),
    path('get-waste-data/', GetDataForMonitoringTeamWasteCollectionApi.as_view(), name='get-waste-data'),
    path('get-waste-data-all-city/', GetDataForMonitoringTeamWasteCollectionAllCityApi.as_view(), name='get-waste-data'),
    path('get-waste/', GetWasteCollectionDataView.as_view(), name="get-waste")
]

