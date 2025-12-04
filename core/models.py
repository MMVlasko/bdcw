import secrets

from django.db import models
from django.core.validators import MinLengthValidator, RegexValidator
import bcrypt


class User(models.Model):
    class UserRole(models.TextChoices):
        USER = 'user', 'Пользователь'
        ADMIN = 'admin', 'Администратор'

    class Meta:
        db_table = 'users'

    id = models.BigAutoField(primary_key=True)

    username = models.CharField(
        'Имя пользователя',
        max_length=50,
        unique=True,
        validators=[
            MinLengthValidator(3),
            RegexValidator(
                regex=r'^[a-zA-Z0-9_]+$',
                message='Только буквы, цифры и подчеркивания'
            )
        ]
    )

    password_hash = models.CharField(
        'Хэш пароля',
        max_length=255,
        help_text='BCrypt/Argon2 хэш пароля'
    )

    first_name = models.CharField('Имя', max_length=50)
    last_name = models.CharField('Фамилия', max_length=50)
    description = models.TextField('О себе', null=True)

    role = models.CharField(
        'Роль',
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER
    )

    is_active = models.BooleanField('Активен', default=True)
    is_public = models.BooleanField('Общедоступен', default=True)
    last_login = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)

    def set_password(self, raw_password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(
            raw_password.encode('utf-8'),
            salt
        ).decode('utf-8')

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        return bcrypt.checkpw(
            raw_password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )


class AuthToken(models.Model):
    key = models.CharField(
        primary_key=True,
        max_length=64,
        default=secrets.token_hex,
        editable=False
    )

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='auth_tokens'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'auth_tokens'

    @classmethod
    def create_token(cls, user, expires_hours=24):
        from django.utils import timezone
        import datetime

        token = cls(
            user=user,
            expires_at=timezone.now() + datetime.timedelta(hours=expires_hours)
        )
        token.save()
        return token

    def is_valid(self):
        from django.utils import timezone
        return self.is_active and self.expires_at > timezone.now()