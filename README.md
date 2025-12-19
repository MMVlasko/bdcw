## Система трекинга целей и привычек

### Запуск

```
docker-compose build --no-cache
docker-compose up
```

### Управление
```
docker-compose exec web bash
> python manage.py <command>
```

### Наполнение базы данных
```
pip install requests faker
python generator.py
```

### Окружение
```
# .env

SECRET_KEY="<ключ Django>"
DEBUG=<True/False>

DB_NAME=<имя базы данных postgres>
DB_USER=<имя пользователя postgres>
DB_PASSWORD=<пароль пользователя postgres>
DB_HOST=<имя хоста базы данных postgres>
DB_PORT=<порт 
```