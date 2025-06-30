from rest_framework import serializers
from .models import City, Sops, SopStep


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['city', 'id']


class SopStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = SopStep
        fields = ['step_number', 'description']


class SopsSerializer(serializers.ModelSerializer):
    steps = SopStepSerializer(many=True, read_only=True)
    cities = CitySerializer(many=True, read_only=True)  # Include cities field

    class Meta:
        model = Sops
        fields = '__all__'  #