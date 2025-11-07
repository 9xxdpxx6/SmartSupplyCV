"""
FastAPI приложение для анализа зон магазина
Предоставляет REST API для загрузки видео, настройки зон и получения статистики
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Tuple
import os
import json
import uuid
import cv2
import numpy as np
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
from enum import Enum

from store_zone_analyzer import (
    process_video,
    calculate_statistics,
    create_visualization,
    load_zones_from_json,
    ZONES_FILE
)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Глобальное хранилище задач
tasks_storage: Dict[str, Dict] = {}

# Глобальное хранилище зон (по умолчанию загружаем из файла)
current_zones: Dict[str, List[Tuple[int, int]]] = load_zones_from_json(ZONES_FILE)

# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

class ZoneCoordinates(BaseModel):
    top_left: List[int]
    bottom_right: List[int]

class ZonesRequest(BaseModel):
    zones: Dict[str, ZoneCoordinates]

class AnalyzeRequest(BaseModel):
    video_id: str
    zones: Optional[Dict[str, ZoneCoordinates]] = None  # Если не указаны, используются текущие зоны

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class StatisticsResponse(BaseModel):
    zone_name: str
    total_time: float
    avg_time: float
    visitor_count: int

class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    video_id: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    statistics: Optional[Dict[str, StatisticsResponse]] = None

# ============================================================================
# FASTAPI ПРИЛОЖЕНИЕ
# ============================================================================

app = FastAPI(
    title="Анализатор зон магазина API",
    description="API для анализа видеозаписей и определения времени пребывания посетителей в зонах",
    version="1.0.0"
)

# CORS middleware для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def convert_zones_to_internal_format(zones_dict: Dict[str, ZoneCoordinates]) -> Dict[str, List[Tuple[int, int]]]:
    """Конвертирует зоны из API формата во внутренний формат."""
    result = {}
    for zone_name, coords in zones_dict.items():
        result[zone_name] = [
            tuple(coords.top_left),
            tuple(coords.bottom_right)
        ]
    return result

def convert_zones_to_api_format(zones_dict: Dict[str, List[Tuple[int, int]]]) -> Dict[str, ZoneCoordinates]:
    """Конвертирует зоны из внутреннего формата в API формат."""
    result = {}
    for zone_name, rect in zones_dict.items():
        result[zone_name] = ZoneCoordinates(
            top_left=list(rect[0]),
            bottom_right=list(rect[1])
        )
    return result

def process_video_task(task_id: str, video_path: str, zones: Dict[str, List[Tuple[int, int]]]):
    """Обрабатывает видео в фоновом режиме."""
    try:
        tasks_storage[task_id]["status"] = TaskStatus.PROCESSING
        
        # Временно устанавливаем зоны в модуле анализатора
        import store_zone_analyzer
        original_zones = store_zone_analyzer.ZONES.copy()
        store_zone_analyzer.ZONES = zones
        
        # Обрабатываем видео
        zone_statistics, last_frame, scale, scaled_zones, track_merges = process_video(video_path)
        
        # Вычисляем статистику
        stats = calculate_statistics(zone_statistics, track_merges)
        
        # Создаем визуализацию
        visualization = create_visualization(last_frame, stats, zone_statistics, scaled_zones)
        
        # Сохраняем результат
        result_image_path = RESULTS_DIR / f"{task_id}_visualization.png"
        cv2.imwrite(str(result_image_path), visualization)
        
        # Восстанавливаем оригинальные зоны
        store_zone_analyzer.ZONES = original_zones
        
        # Сохраняем результаты в задачу
        tasks_storage[task_id]["status"] = TaskStatus.COMPLETED
        tasks_storage[task_id]["completed_at"] = datetime.now().isoformat()
        tasks_storage[task_id]["statistics"] = {
            zone_name: {
                "zone_name": zone_name,
                "total_time": data["total_time"],
                "avg_time": data["avg_time"],
                "visitor_count": data["visitor_count"]
            }
            for zone_name, data in stats.items()
        }
        tasks_storage[task_id]["visualization_path"] = str(result_image_path)
        
    except Exception as e:
        tasks_storage[task_id]["status"] = TaskStatus.FAILED
        tasks_storage[task_id]["completed_at"] = datetime.now().isoformat()
        tasks_storage[task_id]["error"] = str(e)
        import traceback
        traceback.print_exc()

# ============================================================================
# ЭНДПОИНТЫ
# ============================================================================

@app.get("/")
async def root():
    """Корневой эндпоинт с информацией об API."""
    return {
        "message": "Анализатор зон магазина API",
        "version": "1.0.0",
        "endpoints": {
            "POST /upload-video": "Загрузить видеофайл",
            "GET /zones": "Получить текущие зоны",
            "POST /zones": "Установить зоны",
            "POST /analyze": "Запустить анализ видео",
            "GET /tasks/{task_id}": "Получить статус задачи",
            "GET /tasks": "Получить список всех задач",
            "GET /statistics/{task_id}": "Получить статистику по задаче",
            "GET /visualization/{task_id}": "Получить визуализацию по задаче"
        }
    }

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """
    Загружает видеофайл на сервер.
    
    Возвращает video_id для использования в других эндпоинтах.
    """
    try:
        # Проверяем расширение файла
        if not file.filename:
            raise HTTPException(status_code=400, detail="Имя файла не указано")
        
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый формат файла. Разрешенные: {', '.join(allowed_extensions)}"
            )
        
        # Генерируем уникальный ID для видео
        video_id = str(uuid.uuid4())
        video_path = UPLOAD_DIR / f"{video_id}{file_ext}"
        
        # Сохраняем файл
        try:
            with open(video_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            if video_path.exists():
                os.remove(video_path)
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {str(e)}")
        
        # Проверяем размер файла
        file_size = video_path.stat().st_size
        if file_size == 0:
            os.remove(video_path)
            raise HTTPException(status_code=400, detail="Загружен пустой файл")
        
        # Проверяем, что файл действительно видео
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            os.remove(video_path)
            raise HTTPException(status_code=400, detail="Не удалось открыть видеофайл. Проверьте формат.")
        cap.release()
        
        return {
            "video_id": video_id,
            "filename": file.filename,
            "path": str(video_path),
            "message": "Видео успешно загружено"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Неожиданная ошибка: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@app.get("/zones")
async def get_zones():
    """Получает текущие зоны."""
    return {
        "zones": convert_zones_to_api_format(current_zones),
        "count": len(current_zones)
    }

@app.post("/zones")
async def set_zones(zones_request: ZonesRequest):
    """
    Устанавливает зоны для анализа.
    
    Зоны сохраняются глобально и используются для всех последующих анализов,
    если не указаны явно в запросе на анализ.
    """
    global current_zones
    
    # Конвертируем в внутренний формат
    new_zones = convert_zones_to_internal_format(zones_request.zones)
    
    # Валидация зон
    for zone_name, rect in new_zones.items():
        if len(rect) != 2:
            raise HTTPException(status_code=400, detail=f"Зона '{zone_name}' должна содержать 2 точки")
        if len(rect[0]) != 2 or len(rect[1]) != 2:
            raise HTTPException(status_code=400, detail=f"Зона '{zone_name}': координаты должны быть [x, y]")
        x1, y1 = rect[0]
        x2, y2 = rect[1]
        if x1 >= x2 or y1 >= y2:
            raise HTTPException(
                status_code=400,
                detail=f"Зона '{zone_name}': top_left должен быть меньше bottom_right"
            )
    
    # Обновляем зоны
    current_zones = new_zones
    
    # Сохраняем в файл
    zones_to_save = {}
    for zone_name, rect in current_zones.items():
        zones_to_save[zone_name] = {
            "top_left": list(rect[0]),
            "bottom_right": list(rect[1])
        }
    
    try:
        with open(ZONES_FILE, 'w', encoding='utf-8') as f:
            json.dump(zones_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения зон: {str(e)}")
    
    return {
        "message": f"Установлено зон: {len(current_zones)}",
        "zones": convert_zones_to_api_format(current_zones)
    }

@app.post("/analyze")
async def analyze_video(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Запускает анализ видео.
    
    Если зоны не указаны в запросе, используются текущие глобальные зоны.
    """
    # Проверяем наличие видео
    video_files = list(UPLOAD_DIR.glob(f"{request.video_id}.*"))
    if not video_files:
        raise HTTPException(status_code=404, detail=f"Видео с ID {request.video_id} не найдено")
    
    video_path = str(video_files[0])
    
    # Определяем зоны для использования
    if request.zones:
        zones = convert_zones_to_internal_format(request.zones)
    else:
        if not current_zones:
            raise HTTPException(
                status_code=400,
                detail="Зоны не установлены. Используйте POST /zones для установки зон или укажите их в запросе."
            )
        zones = current_zones
    
    # Создаем задачу
    task_id = str(uuid.uuid4())
    tasks_storage[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "video_id": request.video_id,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "error": None,
        "statistics": None,
        "visualization_path": None
    }
    
    # Запускаем обработку в фоне
    background_tasks.add_task(process_video_task, task_id, video_path, zones)
    
    return {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "message": "Анализ запущен. Используйте GET /tasks/{task_id} для проверки статуса."
    }

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Получает статус задачи."""
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task = tasks_storage[task_id]
    return TaskResponse(**task)

@app.get("/tasks")
async def get_all_tasks():
    """Получает список всех задач."""
    return {
        "tasks": [TaskResponse(**task) for task in tasks_storage.values()],
        "total": len(tasks_storage)
    }

@app.get("/statistics/{task_id}")
async def get_statistics(task_id: str):
    """Получает статистику по завершенной задаче."""
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task = tasks_storage[task_id]
    
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Задача еще не завершена. Текущий статус: {task['status']}"
        )
    
    if not task["statistics"]:
        raise HTTPException(status_code=500, detail="Статистика недоступна")
    
    return {
        "task_id": task_id,
        "statistics": task["statistics"]
    }

@app.get("/visualization/{task_id}")
async def get_visualization(task_id: str):
    """Получает визуализацию по завершенной задаче."""
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task = tasks_storage[task_id]
    
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Задача еще не завершена. Текущий статус: {task['status']}"
        )
    
    visualization_path = task.get("visualization_path")
    if not visualization_path or not os.path.exists(visualization_path):
        raise HTTPException(status_code=404, detail="Визуализация не найдена")
    
    return FileResponse(
        visualization_path,
        media_type="image/png",
        filename=f"visualization_{task_id}.png"
    )

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Удаляет задачу и связанные файлы."""
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task = tasks_storage[task_id]
    
    # Удаляем визуализацию, если есть
    visualization_path = task.get("visualization_path")
    if visualization_path and os.path.exists(visualization_path):
        try:
            os.remove(visualization_path)
        except Exception as e:
            print(f"Ошибка удаления визуализации: {e}")
    
    # Удаляем задачу
    del tasks_storage[task_id]
    
    return {"message": "Задача удалена"}

@app.get("/videos/{video_id}/first-frame")
async def get_first_frame(video_id: str):
    """Получает первый кадр видео в формате изображения."""
    video_files = list(UPLOAD_DIR.glob(f"{video_id}.*"))
    if not video_files:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    
    video_path = str(video_files[0])
    
    # Открываем видео и читаем первый кадр
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Не удалось открыть видеофайл")
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise HTTPException(status_code=400, detail="Не удалось прочитать первый кадр")
    
    # Конвертируем BGR в RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Кодируем в JPEG
    import io
    from PIL import Image
    pil_image = Image.fromarray(frame_rgb)
    img_bytes = io.BytesIO()
    pil_image.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    from fastapi.responses import Response
    return Response(content=img_bytes.getvalue(), media_type="image/jpeg")

@app.delete("/videos/{video_id}")
async def delete_video(video_id: str):
    """Удаляет загруженное видео."""
    video_files = list(UPLOAD_DIR.glob(f"{video_id}.*"))
    if not video_files:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    
    for video_file in video_files:
        try:
            os.remove(video_file)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка удаления файла: {str(e)}")
    
    return {"message": "Видео удалено"}

if __name__ == "__main__":
    import uvicorn
    # Настройка для больших файлов
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        limit_concurrency=100,
        limit_max_requests=1000,
        timeout_keep_alive=75
    )

