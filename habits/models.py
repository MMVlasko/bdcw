from django.db import models
from core.models import User
from categories.models import Category


class Habit(models.Model):
    class Meta:
        db_table = 'habits'

    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='habits'
    )

    title = models.CharField(
        'Заголовок',
        max_length=255
    )

    description = models.TextField('Описание цели', null=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='habits'
    )

    frequency_type = models.IntegerField('Длина временного промежутка')
    frequency_value = models.IntegerField('Частота')
    is_active = models.BooleanField('Выполняется', default=True)
    is_public = models.BooleanField('Общедоступно', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)


class HabitLog(models.Model):
    class LogStatus(models.TextChoices):
        COMPLETED = 'completed', 'Выполнено'
        SKIPPED = 'skipped', 'Пропущено'
        FAILED = 'failed', 'Провалено'

    class Meta:
        db_table = 'habit_logs'

    id = models.BigAutoField(primary_key=True)

    habit = models.ForeignKey(
        Habit,
        on_delete=models.CASCADE,
        related_name='habit_logs'
    )

    log_date = models.DateField('Текущая дата')
    status = models.CharField(
        'Роль',
        max_length=20,
        choices=LogStatus.choices,
        default=LogStatus.COMPLETED
    )

    notes = models.TextField('Примечания', null=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
