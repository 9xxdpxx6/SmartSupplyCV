"""
Интерактивный инструмент для настройки зон магазина
Позволяет выделить зоны мышкой на первом кадре видео
"""

import cv2
import numpy as np
import json
import os
import threading
import queue
from typing import List, Tuple, Optional, Dict

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

VIDEO_PATH = "vids/vid1.mp4"  # Путь к видеофайлу
ZONES_FILE = "zones.json"  # Файл для сохранения координат зон
OUTPUT_PYTHON_CODE = True  # Генерировать код Python для вставки в store_zone_analyzer.py

# ============================================================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ОБРАБОТКИ МЫШИ
# ============================================================================

drawing = False
start_point = None
end_point = None
current_rect = None
zones = {}  # {zone_name: [(x1, y1), (x2, y2)]}
current_zone_name = None
display_frame = None
display_scale_factor = 1.0  # Коэффициент масштабирования для отображения
original_video_size = (0, 0)  # Исходное разрешение видео
pending_zone_rect = None  # Ожидающий названия прямоугольник
input_queue = queue.Queue()  # Очередь для ввода названий зон


def mouse_callback(event, x, y, flags, param):
    """
    Обработчик событий мыши для выделения прямоугольников.
    """
    global drawing, start_point, end_point, current_rect, display_frame, zones, display_scale_factor, pending_zone_rect
    
    frame = display_frame.copy()
    
    # Рисуем уже созданные зоны (в масштабе отображения)
    for zone_name, rect in zones.items():
        (x1, y1), (x2, y2) = rect
        
        # Масштабируем координаты для отображения
        if display_scale_factor != 1.0:
            x1_display = int(x1 * display_scale_factor)
            y1_display = int(y1 * display_scale_factor)
            x2_display = int(x2 * display_scale_factor)
            y2_display = int(y2 * display_scale_factor)
        else:
            x1_display, y1_display = x1, y1
            x2_display, y2_display = x2, y2
        
        cv2.rectangle(frame, (x1_display, y1_display), (x2_display, y2_display), (0, 255, 0), 2)
        # Добавляем название зоны
        cv2.putText(frame, zone_name, (x1_display, y1_display - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_point = (x, y)
        end_point = (x, y)
    
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            end_point = (x, y)
            # Рисуем текущий прямоугольник
            cv2.rectangle(frame, start_point, end_point, (255, 0, 0), 2)
    
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_point = (x, y)
        
        # Проверяем, что прямоугольник имеет размер
        if abs(start_point[0] - end_point[0]) > 10 and abs(start_point[1] - end_point[1]) > 10:
            # Сохраняем прямоугольник для обработки в основном цикле
            pending_zone_rect = (start_point, end_point)
        
        start_point = None
        end_point = None
    
    # Обновляем отображение
    cv2.imshow('Настройка зон - Выделите прямоугольники мышкой', frame)


def load_first_frame(video_path: str) -> Tuple[Optional[np.ndarray], Tuple[int, int]]:
    """
    Загружает первый кадр видео и возвращает его размер.
    
    Returns:
        Кортеж (кадр, (ширина, высота))
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Ошибка: Не удалось открыть видео {video_path}")
        return None, (0, 0)
    
    ret, frame = cap.read()
    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    if not ret:
        print("Ошибка: Не удалось прочитать первый кадр")
        return None, (0, 0)
    
    return frame, (original_width, original_height)


def save_zones_json(zones: Dict, filename: str):
    """
    Сохраняет зоны в JSON файл.
    """
    # Преобразуем координаты в список для JSON
    zones_json = {}
    for zone_name, rect in zones.items():
        zones_json[zone_name] = {
            "top_left": rect[0],
            "bottom_right": rect[1]
        }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(zones_json, f, ensure_ascii=False, indent=2)
    
    print(f"\nЗоны сохранены в {filename}")


def generate_python_code(zones: Dict) -> str:
    """
    Генерирует код Python для вставки в store_zone_analyzer.py.
    """
    lines = ["ZONES = {"]
    
    for zone_name, rect in zones.items():
        (x1, y1), (x2, y2) = rect
        lines.append(f'    "{zone_name}": [({x1}, {y1}), ({x2}, {y2})],')
    
    lines.append("}")
    
    return "\n".join(lines)


def scale_coordinates_to_original(coords: List[Tuple[int, int]], scale: float) -> List[Tuple[int, int]]:
    """
    Масштабирует координаты обратно в исходное разрешение.
    
    Args:
        coords: список координат в масштабированном разрешении
        scale: коэффициент масштабирования
    
    Returns:
        Координаты в исходном разрешении
    """
    if scale == 1.0:
        return coords
    
    scaled_coords = []
    for (x, y) in coords:
        scaled_coords.append((int(x / scale), int(y / scale)))
    
    return scaled_coords


def load_zones_from_json(filename: str) -> Dict:
    """
    Загружает зоны из JSON файла.
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
        print(f"Ошибка при загрузке зон: {e}")
        return {}


def main():
    """
    Основная функция интерактивной настройки зон.
    """
    global display_frame, zones, display_scale_factor, pending_zone_rect
    
    # Инициализируем переменные
    pending_zone_rect = None
    
    print("="*60)
    print("ИНТЕРАКТИВНАЯ НАСТРОЙКА ЗОН МАГАЗИНА")
    print("="*60)
    
    # Проверяем наличие видео
    if not os.path.exists(VIDEO_PATH):
        print(f"\nОшибка: Файл {VIDEO_PATH} не найден!")
        print("Укажите правильный путь к видеофайлу в переменной VIDEO_PATH.")
        return
    
    # Загружаем первый кадр
    print(f"\nЗагрузка первого кадра из {VIDEO_PATH}...")
    frame, original_size = load_first_frame(VIDEO_PATH)
    
    if frame is None:
        return
    
    original_width, original_height = original_size
    
    # Загружаем существующие зоны (если есть)
    if os.path.exists(ZONES_FILE):
        load_existing = input(f"\nНайдены существующие зоны в {ZONES_FILE}. Загрузить? (y/n): ").strip().lower()
        if load_existing == 'y':
            zones = load_zones_from_json(ZONES_FILE)
            print(f"Загружено зон: {len(zones)}")
    
    # Масштабируем кадр для удобства отображения (если слишком большой)
    h, w = frame.shape[:2]
    max_display_size = 1280
    display_scale = 1.0
    
    if w > max_display_size or h > max_display_size:
        display_scale = min(max_display_size / w, max_display_size / h)
        new_w = int(w * display_scale)
        new_h = int(h * display_scale)
        display_frame = cv2.resize(frame.copy(), (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        print(f"Кадр масштабирован для отображения: {w}x{h} -> {new_w}x{new_h}")
        print(f"Масштаб отображения: {display_scale:.3f}")
        if original_width > 0 and original_height > 0:
            print(f"Координаты будут автоматически пересчитаны в исходное разрешение: {original_width}x{original_height}")
    else:
        display_frame = frame.copy()
    
    # Сохраняем информацию о масштабе для пересчета координат
    global display_scale_factor, original_video_size
    display_scale_factor = display_scale
    original_video_size = original_size
    
    # Создаем окно и устанавливаем обработчик мыши
    window_name = 'Настройка зон - Выделите прямоугольники мышкой'
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback)
    
    print("\n" + "="*60)
    print("ИНСТРУКЦИИ:")
    print("="*60)
    print("1. Зажмите левую кнопку мыши и выделите прямоугольник")
    print("2. Отпустите кнопку мыши")
    print("3. Введите название зоны в консоли")
    print("4. Повторите для всех зон")
    print("5. Нажмите 's' для сохранения")
    print("6. Нажмите 'q' или ESC для выхода")
    print("7. Нажмите 'd' для удаления последней зоны")
    print("8. Нажмите 'c' для очистки всех зон")
    print("="*60 + "\n")
    
    # Основной цикл
    while True:
        # Обрабатываем ожидающий прямоугольник
        if pending_zone_rect is not None:
            start_pt, end_pt = pending_zone_rect
            pending_zone_rect = None
            
            # Нормализуем координаты (верхний левый, нижний правый)
            x1, y1 = min(start_pt[0], end_pt[0]), min(start_pt[1], end_pt[1])
            x2, y2 = max(start_pt[0], end_pt[0]), max(start_pt[1], end_pt[1])
            
            # Пересчитываем координаты в исходное разрешение, если было масштабирование
            if display_scale_factor != 1.0:
                x1_orig = int(x1 / display_scale_factor)
                y1_orig = int(y1 / display_scale_factor)
                x2_orig = int(x2 / display_scale_factor)
                y2_orig = int(y2 / display_scale_factor)
            else:
                x1_orig, y1_orig = x1, y1
                x2_orig, y2_orig = x2, y2
            
            # Запрашиваем название зоны
            print(f"\nВыделен прямоугольник: [{x1_orig}, {y1_orig}] -> [{x2_orig}, {y2_orig}]")
            
            # Даем время окну обработать события перед блокирующим input
            cv2.waitKey(100)
            
            # Используем более безопасный способ ввода
            try:
                zone_name = input("Введите название зоны (или Enter для отмены): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nОтменено")
                zone_name = ""
            
            # Пересоздаем окно если оно было закрыто
            if not cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) >= 1:
                cv2.namedWindow(window_name)
                cv2.setMouseCallback(window_name, mouse_callback)
            
            if zone_name:
                zones[zone_name] = [(x1_orig, y1_orig), (x2_orig, y2_orig)]
                print(f"Зона '{zone_name}' добавлена: [{x1_orig}, {y1_orig}] -> [{x2_orig}, {y2_orig}]")
            else:
                print("Отменено")
        
        # Обновляем отображение
        frame_copy = display_frame.copy()
        
        # Рисуем все зоны (в масштабе отображения)
        for zone_name, rect in zones.items():
            (x1, y1), (x2, y2) = rect
            
            # Масштабируем координаты для отображения
            if display_scale_factor != 1.0:
                x1_display = int(x1 * display_scale_factor)
                y1_display = int(y1 * display_scale_factor)
                x2_display = int(x2 * display_scale_factor)
                y2_display = int(y2 * display_scale_factor)
            else:
                x1_display, y1_display = x1, y1
                x2_display, y2_display = x2, y2
            
            cv2.rectangle(frame_copy, (x1_display, y1_display), (x2_display, y2_display), (0, 255, 0), 2)
            # Добавляем название зоны
            cv2.putText(frame_copy, zone_name, (x1_display, y1_display - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Рисуем текущий прямоугольник (если рисуем)
        if drawing and start_point and end_point:
            cv2.rectangle(frame_copy, start_point, end_point, (255, 0, 0), 2)
        
        # Добавляем подсказку
        cv2.putText(frame_copy, "Нажмите 's' для сохранения, 'q' для выхода", 
                   (10, frame_copy.shape[0] - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.imshow(window_name, frame_copy)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q') or key == 27:  # 'q' или ESC
            break
        elif key == ord('s'):  # Сохранить
            if zones:
                save_zones_json(zones, ZONES_FILE)
                
                if OUTPUT_PYTHON_CODE:
                    code = generate_python_code(zones)
                    print("\n" + "="*60)
                    print("КОД ДЛЯ ВСТАВКИ В store_zone_analyzer.py:")
                    print("="*60)
                    print(code)
                    print("="*60)
            else:
                print("Нет зон для сохранения!")
        elif key == ord('d'):  # Удалить последнюю зону
            if zones:
                last_zone = list(zones.keys())[-1]
                del zones[last_zone]
                print(f"Зона '{last_zone}' удалена")
            else:
                print("Нет зон для удаления")
        elif key == ord('c'):  # Очистить все зоны
            zones.clear()
            print("Все зоны очищены")
    
    cv2.destroyAllWindows()
    
    if zones:
        print(f"\nИтого настроено зон: {len(zones)}")
        print("\nЗоны:")
        for zone_name, rect in zones.items():
            print(f"  - {zone_name}: {rect}")


if __name__ == "__main__":
    main()

