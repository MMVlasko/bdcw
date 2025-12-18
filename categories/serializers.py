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

    def to_representation(self, instance):
        return CategorySerializer(instance, context=self.context).data


class CategoryPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'name', 'description'
        ]

    def to_representation(self, instance):
        return CategorySerializer(instance, context=self.context).data


class BatchCategoryCreateSerializer(serializers.Serializer):
    categories = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
        max_length=10000
    )

    batch_size = serializers.IntegerField(
        required=False,
        default=100,
        min_value=1,
        max_value=5000
    )
