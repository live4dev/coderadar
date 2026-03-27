# Code Quality / Version Diff Metrics

Метрики для сравнения двух версий (сканов) репозитория.

## Метрики размера

| Метрика | Формула |
| --- | --- |
| LOC delta | `loc_new - loc_old` |
| LOC churn % | `(insertions + deletions) / loc_old * 100` |
| File count delta | `files_new - files_old` |
| Size delta (bytes) | `bytes_new - bytes_old` |

## Файловые изменения (из git diff)

- **Files added / modified / deleted / renamed** — прямой сигнал объёма изменений
- **Churned files %** — `changed_files / total_files * 100`
- **Entry points touched** — изменились ли ключевые файлы (main, config, API routes)

## Структурные метрики

- **Module boundary changes** — добавились/удалились директории верхнего уровня
- **Language distribution shift** — изменилась ли доля языков (Python 60% → 45%)
- **Tech stack diff** — новые/убранные фреймворки, CI, infra-tools

## Сложность кода

- **Cyclomatic complexity delta** — суммарное изменение по всем функциям
- **Average function length** — стал ли код длиннее/короче
- **Max nesting depth** — показатель запутанности

## Зависимости

- **Dependencies added / removed / updated** — из package.json, requirements.txt, go.mod
- **Dependency depth change** — транзитивные зависимости

## Качество

- **Duplication ratio** — % продублированных блоков (cloc/jscpd)
- **Comment density** — `comment_lines / code_lines`
- **Test/code ratio** — растёт ли покрытие тестами пропорционально коду

## Приоритетные для реализации в CodeRadar

Уже есть `Scan` (LOC/files/bytes) + `DeveloperContribution` (insertions/deletions):

1. **Churn score** = `(insertions + deletions) / prev_loc` — нормализованная интенсивность
2. **Churned files %** — из git diff `--stat`
3. **Tech stack diff** — сравнение `frameworks_json` между двумя сканами
4. **Dependency diff** — новые/убранные зависимости
