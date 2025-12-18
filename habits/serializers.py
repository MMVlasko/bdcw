from rest_framework import serializers
from .models import Habit, HabitLog


class HabitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habit
        fields = [
            'id', 'user_id', 'title', 'description',
            'category_id', 'frequency_type', 'frequency_value', 'is_active',
            'is_public', 'created_at', 'updated_at'
        ]


class HabitCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habit
        fields = [
            'user', 'title', 'description',
            'category', 'frequency_type', 'frequency_value', 'is_active',
            'is_public'
        ]
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': True, 'allow_null': True},
            'frequency_type': {'required': True},
            'frequency_value': {'required': True},
            'is_active': {'required': True},
            'is_public': {'required': True},
        }

    def to_representation(self, instance):
        return HabitSerializer(instance, context=self.context).data


class HabitUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habit
        fields = [
            'title', 'description',
            'frequency_type', 'frequency_value', 'is_active',
            'is_public'
        ]
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': True, 'allow_null': True},
            'frequency_type': {'required': True},
            'frequency_value': {'required': True},
            'is_active': {'required': True},
            'is_public': {'required': True},
        }

    def to_representation(self, instance):
        return HabitSerializer(instance, context=self.context).data


class HabitPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habit
        fields = [
            'title', 'description',
            'frequency_type', 'frequency_value', 'is_active',
            'is_public'
        ]

    def to_representation(self, instance):
        return HabitSerializer(instance, context=self.context).data


class HabitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = [
            'id', 'habit_id', 'log_date', 'status',
            'notes', 'created_at', 'updated_at'
        ]


class HabitLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = [
            'habit', 'log_date', 'status',
            'notes'
        ]
        extra_kwargs = {
            'log_date': {'required': True},
            'status': {'required': True},
            'notes': {'required': True, 'allow_null': True}
        }

    def to_representation(self, instance):
        return HabitLogSerializer(instance, context=self.context).data


class HabitLogUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = [
            'log_date', 'status',
            'notes'
        ]
        extra_kwargs = {
            'log_date': {'required': True},
            'status': {'required': True},
            'notes': {'required': True, 'allow_null': True}
        }

    def to_representation(self, instance):
        return HabitLogSerializer(instance, context=self.context).data


class HabitLogPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = [
            'log_date', 'status',
            'notes'
        ]

    def to_representation(self, instance):
        return HabitLogSerializer(instance, context=self.context).data


class BatchHabitCreateSerializer(serializers.Serializer):
    habits = serializers.ListField(
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


class BatchHabitLogCreateSerializer(serializers.Serializer):
    habit_logs = serializers.ListField(
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
