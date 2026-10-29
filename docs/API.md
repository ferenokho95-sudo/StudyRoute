# Локальный HTTP API

Base URL — адрес из консоли. Запросы POST принимают JSON с `Content-Type: application/json`.

| Метод | Путь | Пример тела | Результат |
|---|---|---|---|
| GET | /api/goals | — | Цели обучения |
| GET | /api/learners | — | Профили |
| GET | /api/profile?id=1 | — | Маршрут и история |
| GET | /api/quiz?id=1&phase=diagnostic | — | Диагностика без ключей ответов |
| GET | /api/quiz?id=1&phase=control&skill=python | — | Контрольная без ключей ответов |
| POST | /api/create | `{"name":"Лиза","goal":"ml_engineer"}` | Новый профиль |
| POST | /api/submit | `{"id":1,"phase":"control","skill":"python","answers":{"python_4":"b","python_5":"a","python_6":"c"}}` | Проверка, пояснения, обновлённый маршрут |
| GET | /health | — | Статус сервера |

Коды: 200 — успех; 400 — неверный ввод; 404 — нет маршрута/записи; 500 — ошибка программы (подробности в консоли). Максимум тела запроса 2 МБ. Сервер принимает Host и Origin только своего localhost-адреса. CORS для других сайтов не включён.
