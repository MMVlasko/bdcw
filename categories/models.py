from django.db import models


class Category(models.Model):
    class Meta:
        db_table = 'categories'

    id = models.BigAutoField(primary_key=True)

    name = models.CharField(
        'Имя категории',
        max_length=100,
        unique=True
    )
    description = models.TextField('Описание категории', null=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
