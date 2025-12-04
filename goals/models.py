from django.db import models
from core.models import User
from categories.models import Category


class Goal(models.Model):
    class Meta:
        db_table = 'goals'

    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='goals'
    )

    title = models.CharField(
        'Заголовок',
        max_length=255
    )

    description = models.TextField('Описание цели', null=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='goals'
    )

    target_value = models.DecimalField('Целевой показатель', max_digits=10, decimal_places=3)
    deadline = models.DateField('Дедлайн')
    is_completed = models.BooleanField('Завершено', default=False)
    is_public = models.BooleanField('Общедоступно', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)


class GoalProgress(models.Model):
    class Meta:
        db_table = 'goal_progresses'

    id = models.BigAutoField(primary_key=True)

    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='goal_progresses'
    )

    progress_date = models.DateField('Текущая дата')
    current_value = models.DecimalField('Текущий показатель', max_digits=10, decimal_places=3)
    notes = models.TextField('Примечания', null=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
