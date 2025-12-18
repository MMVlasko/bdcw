from rest_framework import serializers
from .models import User, AuthToken
from .validators import validate_username, validate_password


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username',
            'first_name', 'last_name', 'description', 'role',
            'is_active', 'is_public', 'created_at', 'updated_at'
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True
    )
    confirm_password = serializers.CharField(
        write_only=True
    )

    class Meta:
        model = User
        fields = [
            'id', 'username', 'password', 'confirm_password',
            'first_name', 'last_name', 'description', 'is_public'
        ]

    def validate(self, data):
        validate_password(data['password'], data['confirm_password'])
        validate_username(data['username'])
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User(**validated_data)

        user.set_password(password)

        user.save()
        return user

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data


class UserPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username',
            'first_name', 'last_name', 'description',
            'is_active', 'is_public'
        ]

    def validate(self, data):
        if 'username' in data and data.get('username'):
            validate_username(data['username'], instance=self.instance)
        return data

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username',
            'first_name', 'last_name', 'description',
            'is_active', 'is_public'
        ]

        extra_kwargs = {
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'description': {'required': True, 'allow_null': True},
            'is_active': {'required': True},
            'is_public': {'required': True},
        }

    def validate(self, data):
        validate_username(data['username'], instance=self.instance)
        return data

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data


class UserChangePasswordSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True
    )
    confirm_password = serializers.CharField(
        write_only=True
    )

    class Meta:
        model = User
        fields = [
            'id', 'password', 'confirm_password'
        ]

    def validate(self, data):
        validate_password(data['password'], data['confirm_password'])
        return data

    def update(self, instance, validated_data):

        instance.set_password(validated_data['password'])

        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True
    )

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        try:
            user = User.objects.get(username=username)

            if not user.check_password(password):
                raise serializers.ValidationError('Неверный пароль')

            if not user.is_active:
                raise serializers.ValidationError('Пользователь неактивен')

            data['user'] = user
            return data

        except User.DoesNotExist:
            raise serializers.ValidationError('Пользователь не найден')


class LoginResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    token = serializers.CharField()
    expires_at = serializers.DateTimeField()
    user = UserSerializer()


class BatchUserCreateSerializer(serializers.Serializer):
    users = serializers.ListField(
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


class BatchOperationLogSerializer(serializers.Serializer):
    total_processed = serializers.IntegerField()

    successful = serializers.IntegerField()

    failed = serializers.IntegerField()

    batch_size = serializers.IntegerField()

    errors = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True
    )

    created_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    updated_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    batches_processed = serializers.IntegerField(
        required=False,
        default=0
    )
