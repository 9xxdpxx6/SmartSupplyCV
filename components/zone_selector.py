"""
Кастомный Streamlit компонент для выделения зон на изображении с drag & drop
"""

import streamlit.components.v1 as components
import json
import numpy as np
import base64
from PIL import Image
import io
import os

_RELEASE = True

# Создаем папку для компонента если нужно
if not _RELEASE:
    _component_func = components.declare_component(
        "zone_selector",
        url="http://localhost:3001",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component("zone_selector", path=build_dir)

def zone_selector(image, zones=None, key=None):
    """
    Компонент для выделения зон на изображении с drag & drop.
    
    Args:
        image: numpy array изображения (RGB)
        zones: словарь существующих зон {name: [(x1,y1), (x2,y2)]}
        key: уникальный ключ для компонента
    
    Returns:
        словарь зон или None
    """
    
    # Конвертируем изображение в base64
    if isinstance(image, np.ndarray):
        pil_image = Image.fromarray(image)
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        img_data = f"data:image/png;base64,{img_str}"
        img_width = image.shape[1]
        img_height = image.shape[0]
    else:
        return None
    
    # Подготавливаем существующие зоны
    zones_data = []
    if zones:
        for name, rect in zones.items():
            (x1, y1), (x2, y2) = rect
            zones_data.append({
                "name": str(name),
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2)
            })
    
    # Вызываем компонент
    component_value = _component_func(
        image_data=img_data,
        zones=zones_data,
        key=key,
        default=zones_data
    )
    
    # Конвертируем результат обратно в формат зон
    if component_value:
        try:
            if isinstance(component_value, str):
                zones_list = json.loads(component_value)
            elif isinstance(component_value, list):
                zones_list = component_value
            else:
                return zones if zones else None
            
            zones_dict = {}
            for zone in zones_list:
                if isinstance(zone, dict) and 'name' in zone:
                    zones_dict[zone['name']] = [
                        (int(zone['x1']), int(zone['y1'])),
                        (int(zone['x2']), int(zone['y2']))
                    ]
            return zones_dict if zones_dict else (zones if zones else None)
        except Exception as e:
            return zones if zones else None
    
    return zones if zones else None
