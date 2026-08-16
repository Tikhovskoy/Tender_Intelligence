# Миграции базы данных

Создание новой миграции после изменения ORM-моделей:

```bash
alembic revision --autogenerate -m "описание изменения"
```

Применение всех миграций:

```bash
alembic upgrade head
```

Откат последней миграции:

```bash
alembic downgrade -1
```
