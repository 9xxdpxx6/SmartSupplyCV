"""
Анализатор зон магазина по видеозаписям
Определяет время пребывания посетителей в различных зонах магазина
Соблюдает 152-ФЗ: не сохраняет персональные данные и лица
"""

import cv2
import numpy as np
from ultralytics import YOLO
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import os
import json
from PIL import Image, ImageDraw, ImageFont

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# Путь к видеофайлу
VIDEO_PATH = "vids/vid1.mp4"

# Определение зон магазина как прямоугольники
# Формат: {"название_зоны": [(x1, y1), (x2, y2)]}
# где (x1, y1) - левый верхний угол, (x2, y2) - правый нижний угол
# Можно задать вручную или загрузить из JSON файла через load_zones_from_json()
ZONES_FILE = "zones.json"  # Путь к файлу с зонами (если существует, будет загружен автоматически)

# Зоны по умолчанию (используются, если файл zones.json не найден)
ZONES_DEFAULT = {
    "У входа": [(100, 50), (300, 200)],
    "Зона А": [(400, 100), (600, 300)],
    "Зона Б": [(200, 350), (450, 500)],
}

# Загружаем зоны из JSON файла, если он существует
def load_zones_from_json(filename: str) -> Dict[str, List[Tuple[int, int]]]:
    """
    Загружает зоны из JSON файла.
    
    Args:
        filename: путь к JSON файлу
    
    Returns:
        Словарь зон или пустой словарь, если файл не найден
    """
    if not os.path.exists(filename):
        return {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            zones_json = json.load(f)
        
        zones = {}
        for zone_name, coords in zones_json.items():
            zones[zone_name] = [tuple(coords["top_left"]), tuple(coords["bottom_right"])]
        
        return zones
    except Exception as e:
        print(f"Предупреждение: Не удалось загрузить зоны из {filename}: {e}")
        return {}

# Загружаем зоны (из файла или используем по умолчанию)
ZONES = load_zones_from_json(ZONES_FILE)
if not ZONES:
    ZONES = ZONES_DEFAULT
    print(f"Используются зоны по умолчанию. Для настройки зон используйте: python setup_zones.py")
else:
    print(f"Загружено зон из {ZONES_FILE}: {len(ZONES)}")

# Параметры оптимизации для CPU
TARGET_WIDTH = 640
TARGET_HEIGHT = 480
FRAME_SKIP = 5  # Обрабатывать каждый N-й кадр для ускорения

# Параметры для объединения повторных посетителей
MERGE_TRACKS_ENABLED = True  # Включить объединение повторных треков
MAX_TRACK_GAP_SECONDS = 30.0  # Максимальный разрыв между треками для объединения (секунды)
SIMILAR_SIZE_THRESHOLD = 0.3  # Порог схожести размера bbox для объединения (30%)

# Путь для сохранения результата
OUTPUT_IMAGE_PATH = "zone_analysis_result.png"


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def point_in_rect(point: Tuple[int, int], rect: Tuple[Tuple[int, int], Tuple[int, int]]) -> bool:
    """
    Проверяет, находится ли точка внутри прямоугольника.
    
    Args:
        point: (x, y) координаты точки
        rect: ((x1, y1), (x2, y2)) координаты прямоугольника
    
    Returns:
        True если точка внутри прямоугольника
    """
    x, y = point
    (x1, y1), (x2, y2) = rect
    
    # Убеждаемся, что x1 < x2 и y1 < y2
    min_x, max_x = min(x1, x2), max(x1, x2)
    min_y, max_y = min(y1, y2), max(y1, y2)
    
    return min_x <= x <= max_x and min_y <= y <= max_y


def get_bbox_center(bbox: np.ndarray) -> Tuple[int, int]:
    """
    Вычисляет центр bounding box.
    
    Args:
        bbox: массив [x1, y1, x2, y2]
    
    Returns:
        (center_x, center_y)
    """
    x1, y1, x2, y2 = bbox[:4]
    center_x = int((x1 + x2) / 2)
    center_y = int((y1 + y2) / 2)
    return center_x, center_y


def resize_frame_if_needed(frame: np.ndarray, target_width: int, target_height: int) -> Tuple[np.ndarray, float]:
    """
    Изменяет размер кадра, если он больше целевого размера.
    
    Args:
        frame: исходный кадр
        target_width: целевая ширина
        target_height: целевая высота
    
    Returns:
        Кортеж (измененный кадр, коэффициент масштабирования)
    """
    h, w = frame.shape[:2]
    scale = 1.0
    
    if w > target_width or h > target_height:
        # Вычисляем коэффициент масштабирования
        scale_w = target_width / w
        scale_h = target_height / h
        scale = min(scale_w, scale_h)
        
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    
    return frame, scale


def scale_zones(zones: Dict[str, List[Tuple[int, int]]], scale: float) -> Dict[str, List[Tuple[int, int]]]:
    """
    Масштабирует координаты зон.
    
    Args:
        zones: словарь зон
        scale: коэффициент масштабирования
    
    Returns:
        Масштабированные зоны
    """
    scaled_zones = {}
    for zone_name, rect in zones.items():
        scaled_zones[zone_name] = [
            (int(rect[0][0] * scale), int(rect[0][1] * scale)),
            (int(rect[1][0] * scale), int(rect[1][1] * scale))
        ]
    return scaled_zones


# ============================================================================
# ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ
# ============================================================================

def process_video(video_path: str) -> Tuple[Dict, Optional[np.ndarray], float, Dict, Dict]:
    """
    Обрабатывает видео и собирает статистику по зонам.
    
    Args:
        video_path: путь к видеофайлу
    
    Returns:
        Кортеж (zone_statistics, last_frame, scale, scaled_zones, track_merges)
        zone_statistics: {zone_name: {track_id: [(start_time, end_time), ...]}}
        last_frame: последний обработанный кадр для визуализации
        scale: коэффициент масштабирования
        scaled_zones: масштабированные зоны
        track_merges: {new_track_id: original_track_id} - маппинг объединенных треков
    """
    print(f"Загрузка видео: {video_path}")
    
    # Открываем видео
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть видео: {video_path}")
    
    # Получаем параметры видео
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # Значение по умолчанию
    
    frame_time = 1.0 / fps  # Время одного кадра в секундах
    
    print(f"FPS: {fps:.2f}")
    print(f"Обработка каждого {FRAME_SKIP}-го кадра для ускорения...")
    
    # Определяем масштаб на первом кадре
    ret, first_frame = cap.read()
    if not ret:
        raise ValueError("Не удалось прочитать первый кадр видео")
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Возвращаемся к началу
    
    first_frame, scale = resize_frame_if_needed(first_frame, TARGET_WIDTH, TARGET_HEIGHT)
    scaled_zones = scale_zones(ZONES, scale)
    
    print(f"Масштаб видео: {scale:.3f}")
    
    # Инициализация YOLOv8 модели (nano версия для CPU)
    print("Загрузка модели YOLOv8n...")
    model = YOLO('yolov8n.pt')  # Автоматически скачает при первом запуске
    
    # Структура для хранения статистики: {zone_name: {track_id: [(start_time, end_time), ...]}}
    zone_statistics = defaultdict(lambda: defaultdict(list))
    
    # Текущее состояние: {track_id: {zone_name: start_time}}
    current_state = defaultdict(dict)
    
    # История треков для объединения повторных посетителей
    # {track_id: {"last_seen": time, "last_bbox": bbox, "last_center": center, "last_zones": zones, "bbox_size": size}}
    track_history = {}
    
    # Маппинг объединенных треков: {new_track_id: original_track_id}
    track_merges = {}
    
    # Для хранения последнего кадра
    last_frame = None
    
    frame_count = 0
    processed_frames = 0
    
    print("Начало обработки видео...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Пропускаем кадры для ускорения
        if frame_count % FRAME_SKIP != 0:
            continue
        
        processed_frames += 1
        
        # Ресайз кадра для оптимизации (scale уже определен)
        frame, _ = resize_frame_if_needed(frame, TARGET_WIDTH, TARGET_HEIGHT)
        
        # Обновляем последний кадр
        last_frame = frame.copy()
        
        # Вычисляем текущее время
        current_time = frame_count * frame_time
        
        # Трекинг людей
        results = model.track(frame, persist=True, classes=[0], verbose=False)  # class 0 = person
        
        # Обрабатываем результаты трекинга
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            
            # Получаем track_id (если доступны)
            track_ids = boxes.id.cpu().numpy() if boxes.id is not None else None
            
            for idx, box in enumerate(boxes):
                bbox = box.xyxy[0].cpu().numpy()
                
                # Получаем центр bounding box
                center = get_bbox_center(bbox)
                
                # Определяем, в каких зонах находится центр (используем масштабированные зоны)
                zones = []
                for zone_name, rect in scaled_zones.items():
                    if point_in_rect(center, rect):
                        zones.append(zone_name)
                
                # Получаем track_id
                track_id = int(track_ids[idx]) if track_ids is not None else idx
                
                # Вычисляем размер bbox для сравнения
                bbox_width = bbox[2] - bbox[0]
                bbox_height = bbox[3] - bbox[1]
                bbox_size = bbox_width * bbox_height
                
                # Попытка объединения с предыдущими треками (если включено)
                if MERGE_TRACKS_ENABLED and track_id not in track_history:
                    # Ищем похожий трек, который недавно закончился
                    for old_track_id, old_info in track_history.items():
                        if old_track_id == track_id:
                            continue
                        
                        time_gap = current_time - old_info["last_seen"]
                        
                        # Проверяем временной разрыв
                        if time_gap > MAX_TRACK_GAP_SECONDS:
                            continue
                        
                        # Проверяем размер bbox (рост человека примерно одинаковый)
                        old_size = old_info.get("bbox_size", 0)
                        if old_size > 0:
                            size_ratio = min(bbox_size, old_size) / max(bbox_size, old_size)
                            if size_ratio < (1.0 - SIMILAR_SIZE_THRESHOLD):
                                continue  # Размеры слишком разные
                        
                        # Проверяем, были ли в похожих зонах
                        old_zones = old_info.get("last_zones", [])
                        if zones and old_zones:
                            # Если оба были в зонах и зоны пересекаются - вероятно тот же человек
                            if set(zones) & set(old_zones):
                                # Объединяем треки
                                merged_track_id = track_merges.get(old_track_id, old_track_id)
                                track_merges[track_id] = merged_track_id
                                track_id = merged_track_id
                                print(f"Объединены треки: {old_track_id} -> {merged_track_id} (разрыв {time_gap:.1f}с)")
                                break
                
                # Обновляем историю трека
                track_history[track_id] = {
                    "last_seen": current_time,
                    "last_bbox": bbox.copy(),
                    "last_center": center,
                    "last_zones": zones.copy(),
                    "bbox_size": bbox_size
                }
                
                # Обновляем состояние для всех зон, в которых был посетитель
                active_zones = set(zones)
                previous_zones = set(current_state.get(track_id, {}).keys())
                
                # Зоны, которые посетитель покинул
                exited_zones = previous_zones - active_zones
                
                # Зоны, в которые посетитель вошел
                entered_zones = active_zones - previous_zones
                
                # Зоны, в которых посетитель остался
                stayed_zones = active_zones & previous_zones
                
                # Закрываем интервалы для зон, которые покинули
                for zone_name in exited_zones:
                    start_time = current_state[track_id][zone_name]
                    zone_statistics[zone_name][track_id].append((start_time, current_time))
                    del current_state[track_id][zone_name]
                
                # Начинаем новые интервалы для зон, в которые вошли
                for zone_name in entered_zones:
                    current_state[track_id][zone_name] = current_time
                
                # Для зон, в которых остались, ничего не делаем (интервал продолжается)
        
        # Закрываем интервалы для треков, которые больше не видны
        if frame_count % (FRAME_SKIP * 10) == 0:  # Проверяем каждые 10 обработанных кадров
            active_track_ids = set()
            if results[0].boxes is not None and results[0].boxes.id is not None:
                active_track_ids = set(results[0].boxes.id.cpu().numpy().astype(int))
            
            # Очищаем старую историю треков (старше MAX_TRACK_GAP_SECONDS)
            tracks_to_remove = []
            for old_track_id, old_info in track_history.items():
                if current_time - old_info["last_seen"] > MAX_TRACK_GAP_SECONDS:
                    tracks_to_remove.append(old_track_id)
            for old_track_id in tracks_to_remove:
                del track_history[old_track_id]
            
            for track_id in list(current_state.keys()):
                if track_id not in active_track_ids:
                    # Трек больше не активен, закрываем все его интервалы
                    for zone_name, start_time in current_state[track_id].items():
                        zone_statistics[zone_name][track_id].append((start_time, current_time))
                    del current_state[track_id]
        
        # Прогресс
        if processed_frames % 10 == 0:
            print(f"Обработано кадров: {processed_frames} (кадр {frame_count} из видео)")
    
    # Закрываем все оставшиеся интервалы
    final_time = frame_count * frame_time
    for track_id, zones_dict in current_state.items():
        for zone_name, start_time in zones_dict.items():
            zone_statistics[zone_name][track_id].append((start_time, final_time))
    
    cap.release()
    print(f"Обработка завершена. Всего обработано кадров: {processed_frames}")
    
    return zone_statistics, last_frame, scale, scaled_zones, track_merges


def calculate_statistics(zone_statistics: Dict, track_merges: Dict = None) -> Dict[str, Dict]:
    """
    Вычисляет статистику по зонам.
    
    Args:
        zone_statistics: {zone_name: {track_id: [(start_time, end_time), ...]}}
    
    Returns:
        {zone_name: {"total_time": float, "avg_time": float, "visitor_count": int}}
    """
    result = {}
    
    for zone_name, tracks_data in zone_statistics.items():
        total_time = 0.0
        
        if track_merges:
            # Объединяем треки, которые были объединены
            merged_tracks = {}
            for track_id, intervals in tracks_data.items():
                # Используем оригинальный track_id если был объединен
                original_id = track_merges.get(track_id, track_id)
                if original_id not in merged_tracks:
                    merged_tracks[original_id] = []
                merged_tracks[original_id].extend(intervals)
            
            # Суммируем время для всех уникальных треков (после объединения)
            for track_id, intervals in merged_tracks.items():
                for start_time, end_time in intervals:
                    total_time += (end_time - start_time)
            
            # Количество уникальных посетителей (после объединения)
            visitor_count = len(merged_tracks)
        else:
            # Без объединения - считаем как раньше
            visitor_count = len(tracks_data)
            for track_id, intervals in tracks_data.items():
                for start_time, end_time in intervals:
                    total_time += (end_time - start_time)
        
        # Среднее время на посетителя
        avg_time = total_time / visitor_count if visitor_count > 0 else 0.0
        
        result[zone_name] = {
            "total_time": total_time,
            "avg_time": avg_time,
            "visitor_count": visitor_count
        }
    
    return result


def print_statistics(stats: Dict[str, Dict]):
    """
    Выводит таблицу статистики в консоль.
    
    Args:
        stats: {zone_name: {"total_time": float, "avg_time": float, "visitor_count": int}}
    """
    print("\n" + "="*80)
    print("СТАТИСТИКА ПО ЗОНАМ")
    print("="*80)
    print(f"{'Зона':<30} {'Суммарное время (сек)':<25} {'Среднее время (сек)':<25} {'Посетителей':<15}")
    print("-"*80)
    
    # Сортируем по суммарному времени (по убыванию)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]["total_time"], reverse=True)
    
    for zone_name, data in sorted_stats:
        total_time = data["total_time"]
        avg_time = data["avg_time"]
        visitor_count = data["visitor_count"]
        
        print(f"{zone_name:<30} {total_time:<25.2f} {avg_time:<25.2f} {visitor_count:<15}")
    
    print("="*80 + "\n")


def anonymize_frame(frame: np.ndarray, model: YOLO) -> np.ndarray:
    """
    Размывает людей на кадре для соблюдения 152-ФЗ.
    
    Args:
        frame: исходный кадр
        model: модель YOLO для детекции
    
    Returns:
        Анонимизированный кадр
    """
    anonymized_frame = frame.copy()
    
    # Детектируем людей
    results = model(frame, classes=[0], verbose=False)
    
    if results[0].boxes is not None and len(results[0].boxes) > 0:
        boxes = results[0].boxes
        
        for box in boxes:
            bbox = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, bbox[:4])
            
            # Размываем область с человеком
            roi = anonymized_frame[y1:y2, x1:x2]
            if roi.size > 0:
                blurred_roi = cv2.GaussianBlur(roi, (51, 51), 0)
                anonymized_frame[y1:y2, x1:x2] = blurred_roi
    
    return anonymized_frame


def create_visualization(frame: np.ndarray, stats: Dict[str, Dict], zone_statistics: Dict, scaled_zones: Dict) -> np.ndarray:
    """
    Создает визуализацию с тепловой картой и цветовыми зонами.
    
    Args:
        frame: исходный кадр
        stats: статистика по зонам
        zone_statistics: исходные данные для расчета интенсивности
        scaled_zones: масштабированные зоны для отображения
    
    Returns:
        Кадр с визуализацией
    """
    # Анонимизируем кадр
    model = YOLO('yolov8n.pt')
    anonymized_frame = anonymize_frame(frame, model)
    
    # Создаем overlay для визуализации
    overlay = anonymized_frame.copy()
    h, w = overlay.shape[:2]
    
    # Находим максимальное суммарное время для нормализации
    max_time = max([data["total_time"] for data in stats.values()], default=1.0)
    
    # Создаем цветовую карту для тепловой карты
    try:
        # Для новых версий matplotlib (>=3.5)
        colors = plt.colormaps['hot']
    except (AttributeError, KeyError):
        # Для старых версий matplotlib
        colors = plt.cm.get_cmap('hot')
    
    # Конвертируем в PIL для работы с кириллицей
    overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(overlay_rgb)
    draw = ImageDraw.Draw(pil_image, 'RGBA')
    
    # Пытаемся загрузить шрифт с поддержкой кириллицы
    try:
        # Пробуем стандартные шрифты Windows
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
        ]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, 20)
                    font_small = ImageFont.truetype(path, 16)
                    break
                except:
                    continue
        if font is None:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Генерируем уникальные цвета для зон
    zone_colors_list = [
        (0, 255, 0),      # Зеленый
        (255, 0, 0),      # Синий
        (255, 0, 255),    # Пурпурный
        (0, 255, 255),    # Желтый
        (255, 165, 0),    # Оранжевый
        (128, 0, 128),    # Фиолетовый
    ]
    zone_colors = {}
    for idx, (zone_name, _) in enumerate(scaled_zones.items()):
        zone_colors[zone_name] = zone_colors_list[idx % len(zone_colors_list)]
    
    # Рисуем зоны
    for zone_name, rect in scaled_zones.items():
        (x1, y1), (x2, y2) = rect
        
        # Получаем статистику для этой зоны
        zone_stat = stats.get(zone_name, {"total_time": 0, "avg_time": 0, "visitor_count": 0})
        intensity = zone_stat["total_time"] / max_time if max_time > 0 else 0
        
        # Цвет для тепловой карты (красный = больше времени)
        heat_color = colors(intensity)[:3]
        heat_color_rgba = tuple(int(c * 255) for c in heat_color) + (128,)  # 50% прозрачность
        
        # Цвет для границы зоны
        zone_color = zone_colors.get(zone_name, (128, 128, 128))
        
        # Полупрозрачный overlay для тепловой карты
        draw.rectangle([x1, y1, x2, y2], fill=heat_color_rgba)
        
        # Границы зоны с цветом зоны
        draw.rectangle([x1, y1, x2, y2], outline=zone_color, width=3)
        
        # Подготовка текста со статистикой
        total_time = zone_stat.get('total_time', 0)
        avg_time = zone_stat.get('avg_time', 0)
        visitor_count = zone_stat.get('visitor_count', 0)
        
        # Многострочный текст
        lines = [
            f"{zone_name}",
            f"Время: {total_time:.1f} сек",
            f"Среднее: {avg_time:.1f} сек",
            f"Посетителей: {visitor_count}"
        ]
        
        # Вычисляем размер текста
        line_heights = []
        max_width = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_small)
            line_heights.append(bbox[3] - bbox[1])
            max_width = max(max_width, bbox[2] - bbox[0])
        
        total_height = sum(line_heights) + 10 * (len(lines) - 1) + 10
        
        # Позиция текста (сверху или снизу зоны)
        if y1 > total_height + 20:
            text_y = y1 - total_height - 10
        else:
            text_y = y2 + 10
        
        text_x = x1
        
        # Фон для текста
        draw.rectangle(
            [text_x - 5, text_y - 5, text_x + max_width + 10, text_y + total_height + 5],
            fill=(0, 0, 0, 200),  # Полупрозрачный черный фон
            outline=zone_color,
            width=2
        )
        
        # Рисуем текст построчно
        current_y = text_y
        for i, line in enumerate(lines):
            draw.text((text_x, current_y), line, fill=(255, 255, 255), font=font_small)
            current_y += line_heights[i] + 10
    
    # Добавляем легенду в правый верхний угол
    legend_x = w - 250
    legend_y = 20
    legend_width = 230
    legend_height = 150
    
    # Фон для легенды
    draw.rectangle(
        [legend_x, legend_y, legend_x + legend_width, legend_y + legend_height],
        fill=(0, 0, 0, 220),
        outline=(255, 255, 255),
        width=2
    )
    
    # Заголовок легенды
    draw.text((legend_x + 10, legend_y + 10), "Легенда", fill=(255, 255, 255), font=font)
    
    # Объяснение цветов
    legend_items = [
        ("Красный = больше времени", (255, 0, 0)),
        ("Цветные границы = зоны", (128, 128, 128)),
    ]
    
    current_y = legend_y + 40
    for text, color in legend_items:
        # Цветной индикатор
        draw.rectangle([legend_x + 10, current_y, legend_x + 30, current_y + 15], fill=color)
        # Текст
        draw.text((legend_x + 35, current_y), text, fill=(255, 255, 255), font=font_small)
        current_y += 25
    
    # Конвертируем обратно в OpenCV формат
    result = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    return result


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Основная функция запуска анализа."""
    
    print("="*80)
    print("АНАЛИЗАТОР ЗОН МАГАЗИНА")
    print("="*80)
    print(f"Видео: {VIDEO_PATH}")
    print(f"Зоны: {list(ZONES.keys())}")
    print("="*80 + "\n")
    
    # Проверяем наличие файла
    if not os.path.exists(VIDEO_PATH):
        print(f"ОШИБКА: Файл {VIDEO_PATH} не найден!")
        print("Пожалуйста, укажите правильный путь к видеофайлу в переменной VIDEO_PATH.")
        return
    
    try:
        # Обрабатываем видео
        zone_statistics, last_frame, scale, scaled_zones, track_merges = process_video(VIDEO_PATH)
        
        if last_frame is None:
            print("ОШИБКА: Не удалось обработать видео или видео пустое.")
            return
        
        # Вычисляем статистику
        stats = calculate_statistics(zone_statistics, track_merges)
        
        # Выводим статистику
        print_statistics(stats)
        
        # Создаем визуализацию
        print("Создание визуализации...")
        visualization = create_visualization(last_frame, stats, zone_statistics, scaled_zones)
        
        # Сохраняем результат
        cv2.imwrite(OUTPUT_IMAGE_PATH, visualization)
        print(f"Визуализация сохранена: {OUTPUT_IMAGE_PATH}")
        
        print("\nГотово!")
        
    except Exception as e:
        print(f"\nОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

