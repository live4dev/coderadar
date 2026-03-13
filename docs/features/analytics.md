---
name: Analytics treemap module
overview: "Аналитический модуль с treemap-визуализацией: какие иерархии и метрики можно строить на имеющихся данных (проекты, репозитории, разработчики, сканы, языки), предложение по одному–двум вариантам данных и эндпоинту для графика."
todos: []
isProject: false
---

# Аналитический модуль: treemap по проектам, репозиториям и разработчикам

## Какие данные уже есть

- **Проекты** ([ProjectSummaryOut](app/schemas/project.py)): `id`, `name`, `total_loc`, `total_files`, `repo_count`, `repos_with_completed_scan`, `avg_score`, `last_scan_at`. Агрегаты по последним завершённым сканам репозиториев.
- **Репозитории в проекте** ([RepositoryWithLatestScanOut](app/schemas/repository.py)): `id`, `name`, `project_id`, `latest_scan`: `total_loc`, `total_files`, `primary_language`, `overall_score`, `completed_at`/`started_at`. По одному последнему завершённому скану на репо.
- **Разработчики** ([DeveloperListOut](app/schemas/developer.py)): при запросе с `project_id` — агрегат по проекту: `total_commits`, `total_insertions`, `total_deletions`, `files_changed`, `active_days`. Без проекта — глобальный агрегат по всем сканам.
- **Скан → разработчики** ([GET /scans/{id}/developers](app/api/v1/scans.py)): по одному скану — список разработчиков с `developer_id`, `commit_count`, `insertions`, `deletions`, `files_changed`, `active_days`.
- **Скан → языки** ([ScanLanguageOut](app/schemas/scan.py), GET /scans/{id}/languages): по скану — `language`, `file_count`, `loc`, `percentage`.

Связи: Scan → Repository → Project; DeveloperContribution привязана к scan_id и profile_id (profile → developer). То есть «разработчик в репозитории» = контрибуции по последнему (или любому) скану этого репо.

## Варианты treemap (иерархия + метрика размера)


| Вариант | Уровни                             | Метрика размера                 | Источник данных                                                                                                                                                   |
| ------- | ---------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A       | Проект → Репозиторий               | LOC или число файлов            | `GET /projects/summary` + `GET /projects/{id}/repositories/with-latest-scan`; размер репо = `latest_scan.total_loc` / `total_files`.                              |
| B       | Проект → Репозиторий → Разработчик | Число коммитов (или insertions) | По каждому репо — `latest_scan` → scan_id → контрибуции (как в get_scan_developers); размер листа = `commit_count` (или insertions) по разработчику в этом скане. |
| C       | Один проект: Репозиторий → Язык    | LOC по языку                    | По каждому репо — последний скан → `GET /scans/{id}/languages`; размер = `loc` по языку.                                                                          |
| D       | Проект → Разработчик               | Коммиты в проекте               | `GET /developers?project_id={id}` — уже есть агрегат по проекту; размер = `total_commits`.                                                                        |


Варианты A и D можно реализовать без новых API: данные собираются на клиенте из существующих эндпоинтов. Варианты B и C требуют по одному новому эндпоинту (или одного общего «дерева для treemap»), чтобы не дергать N запросов по сканам/языкам с фронта.

## Рекомендуемый первый шаг

- **Treemap «LOC по проектам и репозиториям» (вариант A)**  
  - Уровень 1: проекты (размер = `total_loc` или `total_files` из summary).  
  - Уровень 2: репозитории проекта (размер = `latest_scan.total_loc` или `total_files`).  
  - Данные: один запрос `GET /projects/summary` и по одному `GET /projects/{id}/repositories/with-latest-scan` на каждый проект (или один новый эндпоинт, возвращающий всё дерево разом).
- **Опционально: один API для дерева под treemap**  
  - Например: `GET /api/v1/analytics/treemap?metric=loc|files|commits&group_by=projects_repos|projects_repos_developers|repos_languages`.  
  - Ответ — одна JSON-структура вида: `{ "name": "root", "value": ..., "children": [ { "name": "Project X", "value": ..., "id": "...", "children": [ ... ] } ] }`, чтобы фронт только отрисовывал treemap (например, через ECharts, D3 или Plotly).

## Что можно использовать для отображения

- **Метрики размера прямоугольников**: `total_loc`, `total_files`, `total_commits`, `insertions` (или комбинация).  
- **Подписи/тултипы**: имена проектов, репо, разработчиков; при желании — процент от родителя или от общего итога.  
- **Фильтры** (позже): один проект, «только с сканами», теги — сужают выборку до того же формата дерева.

## Итог

- Данных достаточно для treemap по **проектам → репозиториям** (LOC/files), а при добавлении одного агрегирующего эндпоинта — и по **проектам → репо → разработчики** (commits/insertions), и по **репо → языки** (LOC).  
- Имеет смысл начать с варианта A на существующих API и, при необходимости, ввести один эндпоинт аналитики, возвращающий готовое дерево для выбранного `metric` и `group_by`, плюс страницу/вид «Analytics» с одной или несколькими treemap-визуализациями.

