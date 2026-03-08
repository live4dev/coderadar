# Техническое задание для Claude: CodeRadar MVP

## 1. Общее описание

Необходимо спроектировать и реализовать MVP системы **CodeRadar** — сервиса технического профилирования репозиториев.

Система должна подключаться к репозиториям в **Bitbucket**, выполнять сканирование кода и git-истории, строить технический профиль проекта и собирать аналитические данные по команде разработки.

Цель MVP:

* автоматически определять технический стек проекта
* собирать данные о зависимостях
* оценивать размер и сложность проекта
* определять базовые показатели качества разработки
* собирать данные по контрибьюторам
* определять, в каких языках и модулях разработчики участвуют
* выявлять базовые технические и организационные риски

---

## 2. Бизнес-цель системы

CodeRadar нужен как инструмент для:

* технического аудита проектов
* сравнения репозиториев между собой
* выявления инженерных рисков
* оценки зрелости разработки
* понимания распределения знаний по команде
* ускорения онбординга и due diligence

---

## 3. Основные сценарии использования

### 3.1. Анализ репозитория

Пользователь добавляет Bitbucket-репозиторий, запускает scan и получает:

* карточку проекта
* определённый стек
* список зависимостей
* размер проекта
* показатели сложности
* базовые quality scores
* список рисков

### 3.2. Анализ команды

Пользователь открывает страницу проекта и видит:

* список контрибьюторов
* количество коммитов
* вклад по языкам
* вклад по модулям
* основных владельцев модулей
* риски концентрации знаний

### 3.3. Сравнение сканов

Пользователь запускает повторный scan и может посмотреть:

* изменения размера проекта
* изменения quality score
* изменения по команде
* появление или исчезновение рисков

---

## 4. Ограничения MVP

Для первой версии:

* **Bitbucket** и **GitLab** (через абстрактный VCS-адаптер)
* только **SQLite**
* только **backend-first** реализация
* UI допускается минимальный, но должен быть достаточным для просмотра результатов
* без сложной real-time обработки
* без распределённой очереди
* без внешнего кластера БД
* без глубокой интеграции с PR comments, review analytics и issue tracker

---

## 5. Функциональные требования

## 5.1. Интеграция с VCS-провайдерами (Bitbucket и GitLab)

Система должна:

* реализовывать абстрактный `BaseVCSProvider` с единым интерфейсом
* иметь отдельные адаптеры `BitbucketProvider` и `GitLabProvider`
* уметь хранить настройки подключения к каждому провайдеру отдельно
* принимать URL репозитория и определять провайдер автоматически (по URL) или явно через поле `provider_type`
* получать доступ к репозиторию через git clone / git fetch
* поддерживать branch selection
* сохранять информацию о последнем анализируемом commit SHA

Поддерживаемые провайдеры:

| Провайдер  | Auth                              | CI config файл             |
|------------|-----------------------------------|----------------------------|
| Bitbucket  | App Password / OAuth              | `.bitbucket-pipelines.yml` |
| GitLab     | Personal Access Token / OAuth     | `.gitlab-ci.yml`           |

Минимально поддержать:

* clone репозитория
* fetch обновлений
* анализ выбранной ветки
* повторный scan по новому состоянию репозитория
* хранение `provider_type` в модели `repositories`

---

## 5.2. Анализ репозитория

Система должна собирать:

### 5.2.1. Общую информацию

* название проекта
* URL репозитория
* ветка
* commit SHA
* дата scan
* размер репозитория
* количество файлов
* суммарный LOC
* распределение LOC по языкам

### 5.2.2. Тип проекта

Определять тип проекта:

* backend service
* frontend application
* library/package
* CLI tool
* infra/config repository
* monolith
* monorepo

Допускается rule-based определение по структуре файлов и конфигурации.

### 5.2.3. Технологический стек

Система должна определять:

* основной язык
* дополнительные языки
* фреймворки
* package managers
* контейнеризацию
* CI/CD признаки
* инфраструктурные инструменты

Примеры источников:

* `package.json`
* `pnpm-lock.yaml`
* `requirements.txt`
* `pyproject.toml`
* `poetry.lock`
* `go.mod`
* `Cargo.toml`
* `pom.xml`
* `build.gradle`
* `Dockerfile`
* `docker-compose.yml`
* `.bitbucket-pipelines.yml`
* `helm/`
* `k8s/`
* `terraform/`

---

## 5.3. Анализ зависимостей

Система должна:

* находить dependency manifest files
* извлекать прямые зависимости
* по возможности отделять prod и dev/test dependencies
* считать количество зависимостей
* строить summary по типам зависимостей

Для MVP достаточно:

* прямые зависимости
* число зависимостей
* ключевые библиотеки
* наличие lockfile
* факт устаревших/подозрительных зависимостей можно оставить как расширение, если быстро реализуемо

---

## 5.4. Анализ размера проекта

Система должна считать:

* количество файлов
* количество директорий
* количество production source files
* количество test files
* количество config files
* LOC total
* LOC по языкам
* долю тестового кода
* размер репозитория в байтах

Нужно исключать или маркировать:

* vendored code
* generated files
* `.git`
* build artifacts
* `node_modules`
* `.venv`
* `dist`
* `build`
* бинарные файлы

---

## 5.5. Анализ сложности

Для MVP система должна считать:

* количество длинных файлов
* количество длинных функций
* количество длинных классов
* глубину вложенности
* базовую цикломатическую сложность там, где это доступно
* approximate structural complexity на уровне файлов/модулей

Если language-specific complexity сложно реализовать для всех языков, допускается:

* сделать rule-based complexity heuristics
* для части популярных языков реализовать более точный анализ
* для остальных использовать fallback-метрики

MVP-метрики сложности:

* average file length
* top N largest files
* number of files above threshold
* number of functions above threshold
* number of modules above threshold
* approximate dependency fan-out

---

## 5.6. Анализ качества проекта

Нужно считать score по нескольким доменам.

### 5.6.1. Code Quality

Критерии:

* наличие линтеров / форматтеров
* признаки code smell
* большие файлы
* большие функции
* высокая сложность
* дублирование на базовом уровне, если возможно

### 5.6.2. Test Quality

Критерии:

* наличие test directories / test files
* доля тестового кода
* наличие test frameworks
* наличие test execution в pipeline

### 5.6.3. Documentation Quality

Критерии:

* наличие README
* наличие setup/run instructions
* наличие architecture docs
* наличие changelog
* наличие operational docs / runbook

### 5.6.4. Delivery Quality

Критерии:

* наличие CI pipeline config:
  * `.bitbucket-pipelines.yml` (Bitbucket)
  * `.gitlab-ci.yml` (GitLab)
* наличие steps для test/lint/build
* наличие Dockerfile
* наличие environment/config conventions

### 5.6.5. Maintainability

Критерии:

* предсказуемая структура проекта
* наличие разделения по модулям
* умеренная сложность
* наличие тестов и документации
* отсутствие экстремальной концентрации изменений в одном месте

Итог:

* score каждого домена 0–100
* общий `radar_score` 0–100

---

## 5.7. Анализ разработчиков

Система должна анализировать git history и собирать:

* всех контрибьюторов проекта
* количество коммитов
* количество активных дней
* первый и последний вклад
* insertions / deletions
* files changed
* вклад по языкам
* вклад по модулям

Источником данных является git history репозитория.

---

## 5.9. Анализ вклада по языкам

Для каждого разработчика нужно считать:

* список языков, в которые он вносил изменения
* files changed by language
* LOC changed by language
* commit count by language
* основной язык
* secondary languages
* language distribution percentage

Пример:

* `d_ivanov`

  * Python — 54%
  * SQL — 20%
  * YAML — 14%
  * Bash — 12%

---

## 5.10. Анализ вклада по модулям

Для каждого разработчика нужно считать:

* в какие директории / модули он контрибьютил
* долю вклада по каждому модулю
* top modules
* main owners for each module

Модуль для MVP можно определять:

* как директорию верхнего или второго уровня
* либо как явно найденный service/module root

---

## 5.11. Риски

Система должна строить список рисков.

Типы рисков MVP:

* high complexity module
* no tests
* weak documentation
* no CI pipeline
* no lockfile
* oversized file/function/module
* knowledge concentration
* low bus factor
* orphan module
* mono-owner language or module

У риска должны быть:

* тип
* severity (`low`, `medium`, `high`, `critical`)
* краткий title
* description
* entity reference (project / module / developer / language)

---

## 5.12. История сканов

Система должна хранить результаты нескольких scan одного и того же репозитория, чтобы можно было:

* просмотреть список сканов
* открыть результаты конкретного scan
* сравнить scan текущий с предыдущим на уровне summary

---

## 6. Нефункциональные требования

* язык реализации: на усмотрение Claude, но предпочтительно **Python**
* ORM: **SQLAlchemy**
* БД: **SQLite**
* архитектура: modular monolith
* API: REST
* код должен быть пригоден к последующей миграции на PostgreSQL
* все основные сущности должны быть покрыты миграциями
* логирование должно быть структурированным
* ошибки scan не должны ронять всю систему
* сканирование должно быть идемпотентным относительно commit SHA

---

## 7. Предлагаемая архитектура

## 7.1. Компоненты системы

### 1. API Layer

Отвечает за:

* CRUD проектов и репозиториев
* запуск scan
* получение результатов
* получение аналитики по разработчикам

### 2. VCS Integration Layer

Отвечает за:

* абстрактный `BaseVCSProvider` и адаптеры `BitbucketProvider`, `GitLabProvider`
* clone/fetch репозиториев через соответствующий провайдер
* checkout branch/commit
* управление локальным mirror/cache репозиториев
* определение провайдера по URL или явному `provider_type`

### 3. Scan Orchestrator

Отвечает за:

* запуск пайплайна анализа
* фиксацию scan lifecycle
* обработку статусов
* сбор результатов модулей анализа

### 4. Static Analysis Engine

Отвечает за:

* languages
* stack detection
* dependencies
* file stats
* docs/pipeline/config detection
* complexity heuristics

### 5. Git Analytics Engine

Отвечает за:

* parsing git history
* author normalization
* developer stats
* language contribution mapping
* module contribution mapping

### 6. Scoring Engine

Отвечает за:

* quality scores
* radar score
* risk detection
* severity assignment

### 7. Persistence Layer

Отвечает за:

* модели SQLAlchemy
* SQLite schema
* repositories / DAOs

---

## 8. Модель данных

Нужно реализовать как минимум следующие сущности:

* `projects`
* `repositories`
* `scans`
* `developers`
* `developer_identities`
* `project_developers`
* `languages`
* `modules`
* `scan_languages`
* `dependencies`
* `developer_contributions`
* `developer_language_contributions`
* `developer_module_contributions`
* `scan_scores`
* `scan_risks`

---

## 9. Минимальные API endpoints

## 9.1. Projects

* `POST /projects`
* `GET /projects`
* `GET /projects/{id}`

## 9.2. Repositories

* `POST /repositories`
* `GET /repositories/{id}`
* `POST /repositories/{id}/scan`
* `GET /repositories/{id}/scans`

## 9.3. Scans

* `GET /scans/{id}`
* `GET /scans/{id}/summary`
* `GET /scans/{id}/languages`
* `GET /scans/{id}/dependencies`
* `GET /scans/{id}/scores`
* `GET /scans/{id}/risks`

## 9.4. Developers

* `GET /projects/{id}/developers`
* `GET /developers/{id}`
* `GET /developers/{id}/languages`
* `GET /developers/{id}/modules`

## 9.5. Modules

* `GET /repositories/{id}/modules`
* `GET /modules/{id}/ownership`

---

## 10. Ожидаемая логика scan pipeline

### Этап 1. Подготовка

* получить repository config
* clone/fetch repo from Bitbucket
* checkout target branch
* создать scan record со статусом `running`

### Этап 2. Анализ файловой структуры

* обойти дерево файлов
* определить типы файлов
* определить языки
* вычислить size/LOC/stats

### Этап 3. Анализ стека и зависимостей

* найти manifest files
* определить frameworks/tools
* извлечь dependencies
* определить project type

### Этап 4. Анализ качества и сложности

* найти docs
* найти CI/CD config
* найти test artifacts
* вычислить complexity heuristics
* сформировать предварительные quality metrics

### Этап 5. Анализ git history

* прочитать commit history
* извлечь author data
* нормализовать identities к `d_ivanov`
* собрать contribution metrics
* собрать language contribution metrics
* собрать module contribution metrics

### Этап 6. Расчёт score и рисков

* применить scoring rules
* сформировать scorecards
* определить risks
* записать результаты

### Этап 7. Завершение scan

* выставить статус `completed`
* сохранить timestamps
* сохранить aggregate summary

Если произошла ошибка:

* статус `failed`
* сохранить error message
* не удалять partial scan metadata

---

## 11. Правила нормализации identity

Реализовать отдельный сервис `IdentityNormalizer`.

### Вход

* author name
* author email

### Выход

* canonical username
* confidence score
* normalized fields

### Базовые правила

1. lowercase
2. transliteration of cyrillic to latin
3. cleanup punctuation
4. split first/last name
5. format: `first_initial + "_" + lastname`
6. если email помогает точнее извлечь username — использовать email as hint
7. если коллизия — добавлять ambiguity flag
8. alias records сохранять отдельно

### Примеры

* `Dmitry Ivanov` → `d_ivanov`
* `Дмитрий Иванов` → `d_ivanov`
* `d.ivanov@company.com` → `d_ivanov`
* `danil.ivanov@company.com` → `d_ivanov` только если rule set или manual mapping это подтверждает

Для MVP нужно предусмотреть **manual overrides**, например:

* таблица identity mapping
* возможность задать вручную соответствие alias → developer

---

## 12. Формулы и принципы scoring

### 12.1. Общий принцип

Каждый домен качества получает score 0–100 на основе rule-based оценки.

### 12.2. Примеры факторов

#### Code Quality

Плюс:

* понятная структура
* линтер/formatter config
* умеренный размер файлов
* умеренная сложность

Минус:

* крупные файлы
* длинные функции
* много сложных модулей

#### Test Quality

Плюс:

* test files present
* test framework present
* tests in pipeline

Минус:

* отсутствие тестов
* очень низкая доля тестового кода

#### Documentation Quality

Плюс:

* README
* setup instructions
* architecture docs

Минус:

* полное отсутствие документации

#### Delivery Quality

Плюс:

* CI pipeline (`.bitbucket-pipelines.yml` или `.gitlab-ci.yml`)
* build/test/lint stages
* Dockerfile

Минус:

* ничего из перечисленного нет

#### Maintainability

Плюс:

* сбалансированная структура
* несколько активных contributors
* отсутствие extreme ownership concentration

Минус:

* один человек держит критичные модули
* проект очень сложный и плохо документирован

---

## 13. Правила определения bus factor и concentration risk

### Для модулей

* если top contributor > 70% изменений → `high concentration`
* если top 2 contributors > 90% → `medium/high concentration`
* если только 1 активный contributor по критичному модулю → `bus factor risk`

### Для языков

* если язык критичен для проекта и в него стабильно коммитит только 1 человек → risk

### Для проекта

* если top 2 разработчика делают большую часть изменений → mark as concentration risk

---

## 14. Ожидаемые артефакты реализации

Claude должен подготовить:

### 1. Архитектурную структуру проекта

* каталоги
* модули
* ответственность слоёв

### 2. SQLAlchemy models

* все основные таблицы MVP

### 3. Alembic migrations

* initial schema for SQLite

### 4. Core services

* VCS provider service (BaseVCSProvider + BitbucketProvider + GitLabProvider)
* scan orchestrator
* stack detector
* dependency parser
* git analytics service
* identity normalizer
* scoring engine
* risk engine

### 5. REST API

* endpoints для проектов, репозиториев, сканов и developers

### 6. Seed / demo mode

* возможность прогнать локальный репозиторий для отладки

### 7. Документацию

* README
* как запускать
* как добавить репозиторий
* как выполнить scan
* как открыть результаты

---

## 15. Критерии готовности MVP

MVP считается готовым, если система умеет:

1. добавить Bitbucket repository
2. скачать репозиторий локально
3. запустить scan
4. определить языки и стек
5. собрать зависимости
6. посчитать размер проекта
7. посчитать базовые признаки сложности
8. собрать список разработчиков из git history
9. нормализовать разработчиков к виду `d_ivanov`
10. показать вклад разработчиков по языкам
11. показать вклад разработчиков по модулям
12. рассчитать базовые quality scores
13. построить список рисков
14. сохранить результаты в SQLite
15. отдать результаты через API

---

# Пошаговый план разработки

Ниже — рекомендуемая последовательность, чтобы не расползтись и как можно раньше получить работающий MVP.

## Этап 1. Каркас проекта

Сделать базовый backend skeleton:

* выбрать стек, например:

  * Python
  * FastAPI
  * SQLAlchemy
  * Alembic
  * Pydantic
* настроить структуру каталогов
* подключить SQLite
* настроить миграции
* настроить базовое логирование
* сделать health endpoint

**Результат этапа:** пустой, но запускаемый backend.

---

## Этап 2. Доменные модели и БД

Реализовать:

* projects
* repositories
* scans
* developers
* developer_identities
* languages
* modules
* contributions
* scores
* risks

Сразу заложить:

* timestamps
* status fields
* unique constraints
* foreign keys

**Результат этапа:** готовая схема данных MVP.

---

## Этап 3. Работа с репозиторием Bitbucket

Реализовать:

* сохранение repository config
* clone repo
* fetch repo
* checkout branch
* локальный cache/mirror

Практически лучше иметь сервис:

* `RepoWorkspaceManager`

**Результат этапа:** система умеет скачать и обновить репозиторий.

---

## Этап 4. Базовый scan orchestration

Реализовать:

* `POST /repositories/{id}/scan`
* создание scan record
* lifecycle statuses: `pending`, `running`, `completed`, `failed`
* базовый orchestrator, который по шагам вызывает анализаторы

**Результат этапа:** можно запускать scan вручную.

---

## Этап 5. Анализ файлов, языков и размера

Реализовать:

* обход файлового дерева
* классификацию файлов
* исключение мусорных директорий
* определение языка по расширению и known files
* подсчёт LOC
* подсчёт file statistics

Сохранять:

* total files
* total loc
* size bytes
* language distribution

**Результат этапа:** система строит базовый tech profile.

---

## Этап 6. Анализ стека и зависимостей

Реализовать parser-ы для:

* Python
* Node.js
* Go
* Java/Kotlin
* Docker
* Bitbucket Pipelines
* Terraform / k8s / Helm по наличию файлов

Нужно извлекать:

* frameworks
* dependency manifests
* dependency count
* project type hints

**Результат этапа:** CodeRadar понимает, что это за проект.

---

## Этап 7. Анализ git history

Реализовать:

* парсинг `git log`
* парсинг `numstat`
* выделение author identities
* агрегацию коммитов
* files changed
* insertions/deletions
* active days
* first/last contribution

**Результат этапа:** есть сырые developer analytics.

---

## Этап 8. Нормализация identities

Реализовать:

* `IdentityNormalizer`
* transliteration
* canonical username generation
* alias linking
* manual override table
* confidence scoring

Важно сразу отдельно покрыть это тестами, потому что это один из самых чувствительных блоков.

**Результат этапа:** разные email и имена связываются в единый developer profile.

---

## Этап 9. Вклад по языкам и модулям

Реализовать:

* определение языка каждого изменённого файла
* агрегацию вклада разработчика по языкам
* агрегацию по директориям/модулям
* вычисление top contributors per module

**Результат этапа:** видно, кто в каких частях системы работает.

---

## Этап 10. Базовый scoring engine

Реализовать rule-based scoring:

* code quality
* test quality
* documentation quality
* delivery quality
* maintainability
* overall radar score

Сделать scoring конфигурируемым через Python constants или YAML rules.

**Результат этапа:** у scan появляется scorecard.

---

## Этап 11. Risk engine

Реализовать:

* risk rules
* severity mapping
* привязку риска к entity
* сохранение риска в БД

Начать с 8–10 самых ценных рисков:

* no tests
* no readme
* no pipeline
* oversized modules/files
* high complexity
* knowledge concentration
* low bus factor
* mono-owner critical area

**Результат этапа:** появляется список actionable проблем.

---

## Этап 12. API выдачи результатов

Сделать endpoints для:

* summary
* languages
* dependencies
* developers
* developer language stats
* developer module stats
* scores
* risks

**Результат этапа:** фронт или внешний клиент уже может строить интерфейс.

---

## Этап 13. Минимальный UI или Swagger-first слой

Для MVP достаточно одного из двух вариантов:

### Вариант A

Оставить API + Swagger/OpenAPI

### Вариант B

Сделать минимальный web UI:

* список проектов
* список репозиториев
* запуск scan
* страница scan summary
* вкладка developers
* вкладка risks

**Результат этапа:** MVP можно показать пользователям.

---

## Этап 14. Тесты и стабилизация

Покрыть тестами:

* identity normalization
* stack detection
* dependency parsing
* scoring rules
* risk rules
* git analytics aggregation

Отдельно проверить:

* репозиторий с несколькими языками
* проект без тестов
* проект без README
* проект с несколькими aliases у одного разработчика

**Результат этапа:** MVP можно пилотировать.

---

# Рекомендуемая структура проекта

```text
coderadar/
  app/
    api/
    core/
    db/
    models/
    schemas/
    services/
      vcs/
        base.py
        bitbucket.py
        gitlab.py
      scanning/
      analysis/
      git_analytics/
      scoring/
      risks/
      identity/
    repositories/
    workers/
    utils/
  alembic/
  tests/
  scripts/
  README.md
```

---

# Что особенно важно для Claude

При реализации нужно отдельно следить за четырьмя вещами:

### 1. Не смешивать scan pipeline и API слой

Оркестрация анализа должна быть отдельным слоем.

### 2. Не зашивать Bitbucket-логику повсюду

Нужно выделить интеграционный адаптер, чтобы позже можно было добавить GitHub/GitLab.

### 3. Сразу делать identity normalization отдельным сервисом

Это отдельная предметная область, не нужно размазывать её по git parser.

### 4. Делать scoring rule-based и расширяемым

Нельзя хардкодить всё в одном giant service.

---

# Практический порядок реализации по спринтам

## Спринт 1

* каркас backend
* SQLite + SQLAlchemy + Alembic
* projects/repositories/scans (с полем `provider_type`)
* `BaseVCSProvider` + `BitbucketProvider` + `GitLabProvider`
* clone/fetch через выбранный провайдер
* запуск scan

## Спринт 2

* file tree analysis
* language detection
* LOC/size stats
* stack detection
* dependency extraction

## Спринт 3

* git analytics
* developers
* identity normalization
* contributions by language
* contributions by module

## Спринт 4

* scoring
* risks
* summary endpoints
* developers endpoints

## Спринт 5

* polishing
* tests
* demo UI or improved API docs
* pilot-ready packaging

---

# Короткая формулировка задачи для Claude

Если нужен более короткий блок, который можно вставить в начало промпта Claude, то вот он:

**Нужно спроектировать и реализовать MVP сервиса CodeRadar на Python с SQLite и SQLAlchemy. Сервис должен подключаться к репозиториям через абстрактный VCS-адаптер с поддержкой Bitbucket и GitLab, выполнять scan кода и git history, определять стек проекта, зависимости, размер, сложность и базовое качество разработки, а также анализировать разработчиков: агрегировать вклад по языкам и модулям, определять ownership и риски концентрации знаний. Архитектура должна быть modular monolith с REST API, миграциями Alembic и возможностью дальнейшей миграции на PostgreSQL.**
