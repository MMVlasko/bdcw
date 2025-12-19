from django.db import models
from categories.models import Category
from goals.models import Goal


class Challenge(models.Model):
    class Meta:
        db_table = 'challenges'

    id = models.BigAutoField(primary_key=True)

    name = models.CharField(
        'Название',
        max_length=255
    )

    description = models.TextField('Описание', null=True)

    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата начала')
    is_active = models.BooleanField('Активен', default=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)


class GoalChallenge(models.Model):
    class Meta:
        db_table = 'goal_challenges'

    pk = models.CompositePrimaryKey('goal', 'challenge')

    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='goal_challenges'
    )

    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name='goal_challenges'
    )

    joined_at = models.DateTimeField('Дата присоединения', auto_now_add=True)


class ChallengeCategory(models.Model):
    class Meta:
        db_table = 'challenge_categories'

    pk = models.CompositePrimaryKey('challenge', 'category')

    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name='challenge_categories'
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='challenge_categories'
    )

