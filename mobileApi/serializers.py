from rest_framework import serializers
from automatedsop.models import DustbinCity, Zone


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DustbinCity
        fields = ['id', 'city']


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = ['id', 'name', 'city']


class DriverReportSerializer(serializers.Serializer):
    driver_id = serializers.CharField()
    driver_name = serializers.CharField()
    driver_number = serializers.CharField()
    incorrect_trips = serializers.IntegerField()