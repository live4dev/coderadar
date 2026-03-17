---
name: Developer Rating module
overview: "Рейтинг разработчиков на основе существующих данных (коммиты, строки, активные дни, языки, модули): формула scoring, эндпоинт и варианты режимов."
todos: []
isProject: false
---

# Рейтинг разработчиков

## Какие данные используются

Все данные доступны без изменений в схеме БД:

- **DeveloperContribution**: `commit_count`, `insertions`, `deletions`, `files_changed`, `active_days`, `first_commit_at`, `last_commit_at` — агрегируются по всем профилям разработчика.
- **DeveloperLanguageContribution**: `language_id` — для подсчёта числа уникальных языков.
- **DeveloperModuleContribution**: `module_id` — для подсчёта числа уникальных модулей.

Опциональная фильтрация по `project_id` — через `Repository.project_id` → `Scan` → `DeveloperContribution`.

## Формула рейтинга (0–100)

```
score = 100 × (
    w_prod  × productivity
  + w_cons  × consistency
  + w_br    × breadth
  + w_ref   × refactoring
  + w_lon   × longevity
)
```

### Компоненты (каждый ∈ [0, 1])

| Компонент | Формула | Нормализация |
|---|---|---|
| `productivity` | `log(commits + 1) + log(insertions + 1)` | min-max по выборке |
| `consistency` | `active_days / max(span_days, 1)`, где `span = (last − first).days + 1` | уже [0, 1] |
| `breadth` | `unique_languages + unique_modules` | min-max по выборке |
| `refactoring` | `deletions / (insertions + deletions + 1)` | уже [0, 1] |
| `longevity` | `active_days` | min-max по выборке |

Нормализация min-max: `(val − min) / (max − min)`, при `max == min` → 0.

### Веса по режимам

| mode | productivity | consistency | breadth | refactoring | longevity |
|---|---|---|---|---|---|
| `default` | 0.30 | 0.25 | 0.20 | 0.15 | 0.10 |
| `volume` | 0.50 | 0.20 | 0.15 | 0.05 | 0.10 |
| `quality` | 0.20 | 0.25 | 0.15 | 0.35 | 0.05 |
| `breadth` | 0.20 | 0.20 | 0.40 | 0.10 | 0.10 |

## Эндпоинт

```
GET /api/v1/developers/rating
```

**Параметры:**

| Параметр | Тип | Описание |
|---|---|---|
| `project_id` | int, optional | Фильтр по проекту |
| `mode` | str, default=`default` | Режим весов: `default`, `volume`, `quality`, `breadth` |
| `limit` | int, default=50 | Максимум строк в ответе |

**Пример ответа:**

```json
[
  {
    "developer_id": 1,
    "display_name": "ivan.petrov",
    "rank": 1,
    "score": 87.4,
    "breakdown": {
      "productivity": 0.92,
      "consistency": 0.74,
      "breadth": 0.65,
      "refactoring": 0.41,
      "longevity": 0.88
    },
    "primary_language": "Python",
    "total_commits": 342,
    "active_days": 89
  }
]
```

## Реализация

- **Схемы**: `RatingBreakdown`, `DeveloperRatingOut` в `app/schemas/developer.py`.
- **Эндпоинт**: `GET /developers/rating` в `app/api/v1/developers.py` — до `/{developer_id}`, чтобы FastAPI не поймал строку `rating` как id.
- **Нет новых таблиц** — вся логика на существующих данных, вычисления на стороне Python.

## Итог

- Данных достаточно для полноценного рейтинга без изменений в сборщике.
- Режим `mode` позволяет адаптировать рейтинг под контекст: объём работы, качество кода, широту покрытия.
- `breakdown` даёт прозрачность: разработчик видит, за что получил оценку.
