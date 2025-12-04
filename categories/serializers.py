from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'created_at', 'updated_at'
        ]


class CategoryCreateAndUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'name', 'description'
        ]
        extra_kwargs = {
            'name': {'required': True},
            'description': {'required': True, 'allow_null': True}
        }


class CategoryPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'name', 'description'
        ]
