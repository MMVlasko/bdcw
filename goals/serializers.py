from rest_framework import serializers
from .models import Goal, GoalProgress


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = [
            'id', 'user_id', 'title', 'description',
            'category_id', 'target_value', 'deadline', 'is_completed',
            'is_public', 'created_at', 'updated_at'
        ]


class GoalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = [
            'user', 'title', 'description',
            'category', 'target_value', 'deadline',
            'is_public'
        ]
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': True, 'allow_null': True},
            'target_value': {'required': True},
            'deadline': {'required': True},
            'is_public': {'required': True},
        }

    def to_representation(self, instance):
        return GoalSerializer(instance, context=self.context).data


class GoalUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = [
            'title', 'description', 'target_value', 'deadline', 'is_completed',
            'is_public'
        ]
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': True, 'allow_null': True},
            'target_value': {'required': True},
            'deadline': {'required': True},
            'is_completed': {'required': True},
            'is_public': {'required': True},
        }

    def to_representation(self, instance):
        return GoalSerializer(instance, context=self.context).data


class GoalPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = [
            'title', 'description', 'target_value', 'deadline', 'is_completed',
            'is_public'
        ]

    def to_representation(self, instance):
        return GoalSerializer(instance, context=self.context).data


class GoalProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalProgress
        fields = [
            'id', 'goal', 'progress_date', 'current_value',
            'notes', 'created_at', 'updated_at'
        ]


class GoalProgressCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalProgress
        fields = [
            'goal', 'progress_date', 'current_value', 'notes'
        ]
        extra_kwargs = {
            'progress_date': {'required': True},
            'current_value': {'required': True},
            'notes': {'required': True, 'allow_null': True}
        }

    def to_representation(self, instance):
        return GoalProgressSerializer(instance, context=self.context).data


class GoalProgressUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalProgress
        fields = [
            'progress_date', 'current_value', 'notes'
        ]
        extra_kwargs = {
            'progress_date': {'required': True},
            'current_value': {'required': True},
            'notes': {'required': True, 'allow_null': True}
        }

    def to_representation(self, instance):
        return GoalProgressSerializer(instance, context=self.context).data


class GoalProgressPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalProgress
        fields = [
            'progress_date', 'current_value', 'notes'
        ]

    def to_representation(self, instance):
        return GoalProgressSerializer(instance, context=self.context).data


class BatchGoalCreateSerializer(serializers.Serializer):
    goals = serializers.ListField(
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


class BatchGoalProgressCreateSerializer(serializers.Serializer):
    goal_progresses = serializers.ListField(
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
