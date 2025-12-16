from rest_framework import serializers

from categories.models import Category
from challenges.models import Challenge
from core.models import User


class GetUsersByCompletedGoalsSerializer(serializers.ModelSerializer):
    achievements_count = serializers.IntegerField()
    avg_progress_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=1
    )
    total_goals = serializers.IntegerField()
    rank = serializers.IntegerField()

    class Meta:
        model = User
        fields = ['id', 'username', 'achievements_count', 'avg_progress_percent', 'total_goals', 'rank']


class GetUsersByHabitsConsistencySerializer(serializers.ModelSerializer):
    habit_consistency_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=1)
    active_habits = serializers.IntegerField()
    total_habits = serializers.IntegerField()
    rank = serializers.IntegerField()

    class Meta:
        model = User
        fields = ['id', 'username', 'habit_consistency_percent',
                  'active_habits', 'total_habits', 'rank']


class GetUsersBySubscribersCountSerializer(serializers.ModelSerializer):
    subscribers_count = serializers.IntegerField()
    subscribing_count = serializers.IntegerField()
    subscribers_rank = serializers.IntegerField( )

    class Meta:
        model = User
        fields = ['id', 'username', 'subscribers_count',
                  'subscribing_count', 'subscribers_rank']


class GetCategoriesByPopularitySerializer(serializers.ModelSerializer):
    total_goals = serializers.IntegerField()
    total_habits = serializers.IntegerField()
    unique_users = serializers.IntegerField()
    activity_score = serializers.DecimalField(
        max_digits=5,
        decimal_places=1
    )

    rank = serializers.IntegerField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'total_goals',
                  'total_habits', 'unique_users', 'activity_score', 'rank']


class GetChallengesByPopularitySerializer(serializers.ModelSerializer):
    participants_count = serializers.IntegerField()
    goals_count = serializers.IntegerField()
    avg_progress_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=1
    )

    popularity_rank = serializers.IntegerField()

    class Meta:
        model = Challenge
        fields = ['id', 'name', 'participants_count',
                  'goals_count', 'is_active', 'avg_progress_percent', 'popularity_rank']
