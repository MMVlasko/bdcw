import re
from rest_framework import serializers
from .models import User

USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')
PASSWORD_PATTERN = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)')


def validate_username(username, instance=None):
    if len(username) < 3:
        raise serializers.ValidationError({
            'username': 'Имя должно содержать не менее 3 символов'
        })
    if not USERNAME_PATTERN.match(username):
        raise serializers.ValidationError({
            'username': 'Имя пользователя должно содержать только латинские буквы, цифры и подчеркивание'
        })
    if instance is not None:
        if User.objects.filter(username=username).exclude(id=instance.id).exists():
            raise serializers.ValidationError({
                'username': 'Пользователь с таким именем уже существует'
            })
    else:
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError({
                'username': 'Пользователь с таким именем уже существует'
            })


def validate_password(password, confirm_password):
    if password != confirm_password:
        raise serializers.ValidationError({
            'confirm_password': 'Пароли не совпадают'
        })
    if len(password) < 5:
        raise serializers.ValidationError({
            'password': 'Пароль должен длиной не менее 5 символов'
        })
    if not PASSWORD_PATTERN.match(password):
        raise serializers.ValidationError({
            'username': 'Имя пользователя должно содержать только латинские буквы, цифры и подчеркивание'
        })
