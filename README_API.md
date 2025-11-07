# API для анализатора зон магазина

FastAPI приложение для работы с системой анализа видеозаписей через REST API.

## Содержание

- [Быстрый старт](#быстрый-старт)
- [Базовый URL](#базовый-url)
- [Эндпоинты](#эндпоинты)
  - [Загрузка видео](#1-загрузка-видео)
  - [Получение первого кадра](#2-получение-первого-кадра-видео)
  - [Работа с зонами](#3-работа-с-зонами)
  - [Запуск анализа](#4-запуск-анализа)
  - [Получение результатов](#5-получение-результатов)
  - [Управление задачами](#6-управление-задачами)
- [Примеры использования](#примеры-использования)
- [Структура данных](#структура-данных)
- [Обработка ошибок](#обработка-ошибок)
- [Ограничения и лимиты](#ограничения-и-лимиты)

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите сервер:
```bash
python api.py
```

Или с помощью uvicorn:
```bash
uvicorn api:app --host 0.0.0.0 --port 8888 --reload
```

3. Откройте документацию API:
- Swagger UI: http://localhost:8888/docs
- ReDoc: http://localhost:8888/redoc

## Базовый URL

По умолчанию API доступен по адресу:
```
http://localhost:8888
```

Для продакшена измените хост и порт в `api.py` или используйте переменные окружения.

## Эндпоинты

### 1. Загрузка видео

**POST** `/upload-video`

Загружает видеофайл на сервер.

**Параметры:**
- `file` (form-data): видеофайл (mp4, avi, mov, mkv, flv)

**Ответ:**
```json
{
  "video_id": "uuid-видео",
  "filename": "video.mp4",
  "path": "uploads/uuid-видео.mp4",
  "message": "Видео успешно загружено"
}
```

**Пример (curl):**
```bash
curl -X POST "http://localhost:8888/upload-video" \
  -F "file=@video.mp4"
```

**Пример (Python):**
```python
import requests

url = "http://localhost:8888/upload-video"
with open("video.mp4", "rb") as f:
    files = {"file": ("video.mp4", f, "video/mp4")}
    response = requests.post(url, files=files)
    
if response.status_code == 200:
    data = response.json()
    video_id = data["video_id"]
    print(f"Видео загружено: {video_id}")
else:
    print(f"Ошибка: {response.text}")
```

**Коды ответов:**
- `200` - Видео успешно загружено
- `400` - Неподдерживаемый формат файла или файл поврежден
- `500` - Ошибка сохранения файла

### 2. Получение первого кадра видео

**GET** `/videos/{video_id}/first-frame`

Получает первый кадр видео в формате изображения (JPEG). Полезно для предпросмотра и выделения зон.

**Параметры:**
- `video_id` (path): ID загруженного видео

**Ответ:** JPEG изображение

**Пример (curl):**
```bash
curl -X GET "http://localhost:8888/videos/{video_id}/first-frame" \
  --output first_frame.jpg
```

**Пример (Python):**
```python
import requests
from PIL import Image
import io

url = f"http://localhost:8888/videos/{video_id}/first-frame"
response = requests.get(url)

if response.status_code == 200:
    img = Image.open(io.BytesIO(response.content))
    img.save("first_frame.jpg")
    print("Первый кадр сохранен")
else:
    print(f"Ошибка: {response.status_code}")
```

**Коды ответов:**
- `200` - Изображение успешно получено
- `404` - Видео не найдено
- `400` - Не удалось прочитать кадр

### 3. Получение зон

**GET** `/zones`

Получает текущие установленные зоны.

**Ответ:**
```json
{
  "zones": {
    "Зона 1": {
      "top_left": [100, 50],
      "bottom_right": [300, 200]
    },
    "Зона 2": {
      "top_left": [400, 100],
      "bottom_right": [600, 300]
    }
  },
  "count": 2
}
```

### 4. Установка зон

**POST** `/zones`

Устанавливает зоны для анализа. Зоны сохраняются глобально и используются для всех последующих анализов.

**Тело запроса:**
```json
{
  "zones": {
    "Зона 1": {
      "top_left": [100, 50],
      "bottom_right": [300, 200]
    },
    "Зона 2": {
      "top_left": [400, 100],
      "bottom_right": [600, 300]
    }
  }
}
```

**Ответ:**
```json
{
  "message": "Установлено зон: 2",
  "zones": { ... }
}
```

**Пример (curl):**
```bash
curl -X POST "http://localhost:8888/zones" \
  -H "Content-Type: application/json" \
  -d '{
    "zones": {
      "Касса": {
        "top_left": [10, 10],
        "bottom_right": [200, 150]
      }
    }
  }'
```

**Пример (Python):**
```python
import requests

url = "http://localhost:8888/zones"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    zones = data["zones"]
    print(f"Загружено зон: {data['count']}")
    for zone_name, coords in zones.items():
        print(f"{zone_name}: {coords['top_left']} - {coords['bottom_right']}")
```

### 4. Установка зон

**POST** `/zones`

Устанавливает зоны для анализа. Зоны сохраняются глобально и используются для всех последующих анализов.

**Тело запроса:**
```json
{
  "zones": {
    "Зона 1": {
      "top_left": [100, 50],
      "bottom_right": [300, 200]
    },
    "Зона 2": {
      "top_left": [400, 100],
      "bottom_right": [600, 300]
    }
  }
}
```

**Ответ:**
```json
{
  "message": "Установлено зон: 2",
  "zones": { ... }
}
```

**Пример (curl):**
```bash
curl -X POST "http://localhost:8888/zones" \
  -H "Content-Type: application/json" \
  -d '{
    "zones": {
      "Касса": {
        "top_left": [10, 10],
        "bottom_right": [200, 150]
      }
    }
  }'
```

**Пример (Python):**
```python
import requests

url = "http://localhost:8888/zones"
zones_data = {
    "zones": {
        "Касса": {
            "top_left": [10, 10],
            "bottom_right": [200, 150]
        },
        "Полки": {
            "top_left": [250, 50],
            "bottom_right": [500, 300]
        }
    }
}

response = requests.post(url, json=zones_data)

if response.status_code == 200:
    data = response.json()
    print(data["message"])
else:
    print(f"Ошибка: {response.json()}")
```

**Коды ответов:**
- `200` - Зоны успешно установлены
- `400` - Ошибка валидации (неправильные координаты)
- `500` - Ошибка сохранения зон

### 5. Запуск анализа

**POST** `/analyze`

Запускает анализ видео. Если зоны не указаны, используются текущие глобальные зоны.

**Тело запроса:**
```json
{
  "video_id": "uuid-видео",
  "zones": {  // опционально
    "Зона 1": {
      "top_left": [100, 50],
      "bottom_right": [300, 200]
    }
  }
}
```

**Ответ:**
```json
{
  "task_id": "uuid-задачи",
  "status": "pending",
  "message": "Анализ запущен. Используйте GET /tasks/{task_id} для проверки статуса."
}
```

**Пример (curl):**
```bash
curl -X POST "http://localhost:8888/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "uuid-видео"
  }'
```

**Пример (Python):**
```python
import requests

url = "http://localhost:8888/analyze"
data = {
    "video_id": video_id,
    # Опционально: можно указать зоны для этого анализа
    # "zones": {
    #     "Зона 1": {
    #         "top_left": [100, 50],
    #         "bottom_right": [300, 200]
    #     }
    # }
}

response = requests.post(url, json=data)

if response.status_code == 200:
    result = response.json()
    task_id = result["task_id"]
    print(f"Анализ запущен. Task ID: {task_id}")
else:
    print(f"Ошибка: {response.json()}")
```

**Коды ответов:**
- `200` - Анализ успешно запущен
- `400` - Видео не найдено или зоны не установлены
- `404` - Видео с указанным ID не найдено

### 6. Получение статуса задачи

**GET** `/tasks/{task_id}`

Получает статус задачи анализа.

**Ответ:**
```json
{
  "task_id": "uuid-задачи",
  "status": "completed",  // pending, processing, completed, failed
  "video_id": "uuid-видео",
  "created_at": "2024-01-01T12:00:00",
  "completed_at": "2024-01-01T12:05:00",
  "error": null,
  "statistics": {
    "Зона 1": {
      "zone_name": "Зона 1",
      "total_time": 120.5,
      "avg_time": 30.1,
      "visitor_count": 4
    }
  }
}
```

**Пример (Python):**
```python
import requests
import time

url = f"http://localhost:8888/tasks/{task_id}"

# Проверяем статус каждые 5 секунд
while True:
    response = requests.get(url)
    if response.status_code == 200:
        task = response.json()
        status = task["status"]
        print(f"Статус: {status}")
        
        if status == "completed":
            print("Анализ завершен!")
            break
        elif status == "failed":
            print(f"Ошибка: {task.get('error', 'Неизвестная ошибка')}")
            break
        elif status == "processing":
            print("Обработка...")
        
        time.sleep(5)
    else:
        print(f"Ошибка получения статуса: {response.status_code}")
        break
```

### 7. Список всех задач

**GET** `/tasks`

Получает список всех задач.

**Ответ:**
```json
{
  "tasks": [ ... ],
  "total": 10
}
```

**Пример (Python):**
```python
import requests

url = "http://localhost:8888/tasks"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    print(f"Всего задач: {data['total']}")
    for task in data["tasks"]:
        print(f"Task {task['task_id']}: {task['status']}")
```

### 8. Получение статистики

**GET** `/statistics/{task_id}`

Получает статистику по завершенной задаче.

**Ответ:**
```json
{
  "task_id": "uuid-задачи",
  "statistics": {
    "Зона 1": {
      "zone_name": "Зона 1",
      "total_time": 120.5,
      "avg_time": 30.1,
      "visitor_count": 4
    },
    "Зона 2": {
      "zone_name": "Зона 2",
      "total_time": 80.3,
      "avg_time": 20.0,
      "visitor_count": 4
    }
  }
}
```

**Пример (Python):**
```python
import requests
import json

url = f"http://localhost:8888/statistics/{task_id}"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    statistics = data["statistics"]
    
    # Выводим статистику в удобном формате
    for zone_name, stats in statistics.items():
        print(f"\n{zone_name}:")
        print(f"  Суммарное время: {stats['total_time']:.2f} сек")
        print(f"  Среднее время: {stats['avg_time']:.2f} сек")
        print(f"  Посетителей: {stats['visitor_count']}")
else:
    print(f"Ошибка: {response.status_code}")
```

### 9. Получение визуализации

**GET** `/visualization/{task_id}`

Получает изображение с визуализацией результатов (тепловая карта, зоны, статистика).

**Ответ:** PNG изображение

**Пример (curl):**
```bash
curl -X GET "http://localhost:8888/visualization/{task_id}" \
  --output visualization.png
```

**Пример (Python):**
```python
import requests
from PIL import Image
import io

url = f"http://localhost:8888/visualization/{task_id}"
response = requests.get(url)

if response.status_code == 200:
    img = Image.open(io.BytesIO(response.content))
    img.save("visualization.png")
    print("Визуализация сохранена")
else:
    print(f"Ошибка: {response.status_code}")
```

**Коды ответов:**
- `200` - Изображение успешно получено
- `400` - Задача еще не завершена
- `404` - Задача или визуализация не найдены

### 10. Удаление задачи

**DELETE** `/tasks/{task_id}`

Удаляет задачу и связанные файлы.

**Пример (Python):**
```python
import requests

url = f"http://localhost:8888/tasks/{task_id}"
response = requests.delete(url)

if response.status_code == 200:
    print("Задача удалена")
else:
    print(f"Ошибка: {response.status_code}")
```

### 11. Удаление видео

**DELETE** `/videos/{video_id}`

Удаляет загруженное видео и освобождает место на диске.

**Пример (Python):**
```python
import requests

url = f"http://localhost:8888/videos/{video_id}"
response = requests.delete(url)

if response.status_code == 200:
    print("Видео удалено")
else:
    print(f"Ошибка: {response.status_code}")
```

## Примеры использования

### Полный рабочий процесс (Python)

```python
import requests
import time
from PIL import Image
import io

BASE_URL = "http://localhost:8888"

# 1. Загрузить видео
print("Загрузка видео...")
with open("video.mp4", "rb") as f:
    files = {"file": ("video.mp4", f, "video/mp4")}
    response = requests.post(f"{BASE_URL}/upload-video", files=files)
    
if response.status_code != 200:
    print(f"Ошибка загрузки: {response.text}")
    exit(1)

video_data = response.json()
video_id = video_data["video_id"]
print(f"Видео загружено: {video_id}")

# 2. Получить первый кадр для предпросмотра
print("Получение первого кадра...")
response = requests.get(f"{BASE_URL}/videos/{video_id}/first-frame")
if response.status_code == 200:
    img = Image.open(io.BytesIO(response.content))
    img.save("first_frame.jpg")
    print("Первый кадр сохранен в first_frame.jpg")

# 3. Установить зоны
print("Установка зон...")
zones_data = {
    "zones": {
        "Касса": {
            "top_left": [10, 10],
            "bottom_right": [200, 150]
        },
        "Полки": {
            "top_left": [250, 50],
            "bottom_right": [500, 300]
        }
    }
}
response = requests.post(f"{BASE_URL}/zones", json=zones_data)
if response.status_code == 200:
    print("Зоны установлены")
else:
    print(f"Ошибка установки зон: {response.text}")

# 4. Запустить анализ
print("Запуск анализа...")
response = requests.post(
    f"{BASE_URL}/analyze",
    json={"video_id": video_id}
)
if response.status_code != 200:
    print(f"Ошибка запуска анализа: {response.text}")
    exit(1)

task_data = response.json()
task_id = task_data["task_id"]
print(f"Анализ запущен. Task ID: {task_id}")

# 5. Ожидание завершения
print("Ожидание завершения анализа...")
while True:
    response = requests.get(f"{BASE_URL}/tasks/{task_id}")
    if response.status_code == 200:
        task = response.json()
        status = task["status"]
        print(f"Статус: {status}")
        
        if status == "completed":
            print("Анализ завершен!")
            break
        elif status == "failed":
            print(f"Ошибка: {task.get('error', 'Неизвестная ошибка')}")
            exit(1)
    
    time.sleep(5)

# 6. Получить статистику
print("Получение статистики...")
response = requests.get(f"{BASE_URL}/statistics/{task_id}")
if response.status_code == 200:
    data = response.json()
    print("\nСтатистика по зонам:")
    for zone_name, stats in data["statistics"].items():
        print(f"\n{zone_name}:")
        print(f"  Суммарное время: {stats['total_time']:.2f} сек")
        print(f"  Среднее время: {stats['avg_time']:.2f} сек")
        print(f"  Посетителей: {stats['visitor_count']}")

# 7. Получить визуализацию
print("Получение визуализации...")
response = requests.get(f"{BASE_URL}/visualization/{task_id}")
if response.status_code == 200:
    img = Image.open(io.BytesIO(response.content))
    img.save("visualization.png")
    print("Визуализация сохранена в visualization.png")
```

## Пример полного рабочего процесса (Bash)

```bash
# 1. Загрузить видео
VIDEO_RESPONSE=$(curl -X POST "http://localhost:8888/upload-video" \
  -F "file=@video.mp4")
VIDEO_ID=$(echo $VIDEO_RESPONSE | jq -r '.video_id')

# 2. Установить зоны
curl -X POST "http://localhost:8888/zones" \
  -H "Content-Type: application/json" \
  -d '{
    "zones": {
      "Касса": {
        "top_left": [10, 10],
        "bottom_right": [200, 150]
      },
      "Полки": {
        "top_left": [250, 50],
        "bottom_right": [500, 300]
      }
    }
  }'

# 3. Запустить анализ
ANALYZE_RESPONSE=$(curl -X POST "http://localhost:8888/analyze" \
  -H "Content-Type: application/json" \
  -d "{\"video_id\": \"$VIDEO_ID\"}")
TASK_ID=$(echo $ANALYZE_RESPONSE | jq -r '.task_id')

# 4. Проверить статус (повторять до завершения)
while true; do
  STATUS=$(curl -s "http://localhost:8888/tasks/$TASK_ID" | jq -r '.status')
  echo "Статус: $STATUS"
  if [ "$STATUS" = "completed" ]; then
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "Ошибка анализа!"
    exit 1
  fi
  sleep 5
done

# 5. Получить статистику
curl "http://localhost:8888/statistics/$TASK_ID" | jq

# 6. Получить визуализацию
curl "http://localhost:8888/visualization/$TASK_ID" \
  --output visualization.png
```

## Структура данных

### Зоны

Зоны определяются как прямоугольники с координатами:
- `top_left`: [x, y] - левый верхний угол
- `bottom_right`: [x, y] - правый нижний угол

Координаты в пикселях относительно исходного разрешения видео.

### Статистика

Для каждой зоны возвращается:
- `zone_name`: название зоны
- `total_time`: суммарное время пребывания всех посетителей (секунды)
- `avg_time`: среднее время пребывания одного посетителя (секунды)
- `visitor_count`: количество уникальных посетителей

## Статусы задач

- `pending`: задача создана, ожидает обработки
- `processing`: видео обрабатывается
- `completed`: обработка завершена успешно
- `failed`: произошла ошибка при обработке

## Обработка ошибок

API возвращает стандартные HTTP коды:

### Успешные ответы
- `200 OK` - Запрос выполнен успешно

### Ошибки клиента
- `400 Bad Request` - Ошибка валидации (неправильные параметры, формат файла)
- `404 Not Found` - Ресурс не найден (видео, задача)

### Ошибки сервера
- `500 Internal Server Error` - Внутренняя ошибка сервера

### Формат ошибок

При ошибке API возвращает JSON с полем `detail`:

```json
{
  "detail": "Описание ошибки"
}
```

**Пример обработки ошибок (Python):**
```python
import requests

try:
    response = requests.post(url, json=data)
    response.raise_for_status()  # Вызовет исключение при ошибке
    result = response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 400:
        error_detail = e.response.json().get("detail", "Ошибка валидации")
        print(f"Ошибка валидации: {error_detail}")
    elif e.response.status_code == 404:
        print("Ресурс не найден")
    else:
        print(f"HTTP ошибка: {e}")
except requests.exceptions.RequestException as e:
    print(f"Ошибка запроса: {e}")
```

## CORS

По умолчанию CORS разрешен для всех источников (`*`). В продакшене рекомендуется указать конкретные домены.

## Ограничения и лимиты

### Размер файлов
- Максимальный размер видеофайла ограничен только доступной памятью сервера
- Рекомендуется использовать видео до 500 МБ для оптимальной производительности
- Для больших файлов увеличьте таймаут в клиенте

### Форматы видео
Поддерживаемые форматы:
- MP4 (рекомендуется)
- AVI
- MOV
- MKV
- FLV

### Производительность
- Обработка видео может занять от нескольких секунд до нескольких минут в зависимости от:
  - Длительности видео
  - Разрешения видео
  - Количества людей в кадре
  - Производительности сервера

### Хранение данных
- Загруженные видео: `uploads/` (автоматически создается)
- Результаты анализа: `results/` (автоматически создается)
- Зоны: `zones.json` (сохраняются автоматически)

Все эти папки добавлены в `.gitignore`.

### Очистка данных
Рекомендуется периодически очищать старые файлы:
- Удаляйте завершенные задачи через `DELETE /tasks/{task_id}`
- Удаляйте неиспользуемые видео через `DELETE /videos/{video_id}`

## Интеграция с другими языками

### JavaScript/TypeScript

```javascript
// Загрузка видео
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8888/upload-video', {
    method: 'POST',
    body: formData
});

const data = await response.json();
console.log('Video ID:', data.video_id);
```

### cURL

Все примеры в документации также доступны через cURL. См. разделы с примерами выше.

## Безопасность

⚠️ **Важно для продакшена:**

1. **CORS**: Измените настройки CORS в `api.py`, указав конкретные домены вместо `*`
2. **Аутентификация**: Добавьте аутентификацию для защиты API
3. **HTTPS**: Используйте HTTPS в продакшене
4. **Лимиты**: Настройте лимиты на размер файлов и количество запросов
5. **Валидация**: Всегда валидируйте входные данные на клиенте

## Дополнительные ресурсы

- **Swagger UI**: http://localhost:8888/docs - Интерактивная документация API
- **ReDoc**: http://localhost:8888/redoc - Альтернативная документация
- **Исходный код**: См. файл `api.py` для деталей реализации

