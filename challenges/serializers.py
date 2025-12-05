from rest_framework import serializers
from .models import Challenge, GoalChallenge, ChallengeCategory


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = [
            'id', 'name', 'description', 'target_value', 'start_date', 'end_date',
            'is_active', 'created_at', 'updated_at'
        ]


class ChallengeCreateAndUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = [
            'name', 'description', 'target_value', 'start_date', 'end_date',
            'is_active'
        ]
        extra_kwargs = {
            'name': {'required': True},
            'description': {'required': True, 'allow_null': True},
            'target_value': {'required': True},
            'deadline': {'required': True},
            'start_date': {'required': True},
            'end_date': {'required': True},
            'is_active': {'required': True},
        }

    def to_representation(self, instance):
        return ChallengeSerializer(instance, context=self.context).data


class ChallengePartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = [
            'name', 'description', 'target_value', 'start_date', 'end_date',
            'is_active'
        ]

    def to_representation(self, instance):
        return ChallengeSerializer(instance, context=self.context).data


class AppendCategoryToChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengeCategory
        fields = ['challenge', 'category']


class AppendGoalToChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalChallenge
        fields = ['goal', 'challenge']


class GoalChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalChallenge
        fields = ['goal', 'challenge', 'joined_at']
