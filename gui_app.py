"""
GUI приложение для анализа зон магазина
Использует Streamlit для интерактивного интерфейса
"""

import streamlit as st
import cv2
import numpy as np
import json
import os
import tempfile
import pandas as pd
from typing import Dict, Optional
from store_zone_analyzer import (
    process_video, 
    calculate_statistics, 
    create_visualization,
    load_zones_from_json,
    ZONES_FILE
)

# Настройки страницы
st.set_page_config(
    page_title="Анализатор зон магазина",
    page_icon="🏪",
    layout="wide"
)

# Инициализация состояния
if 'zones' not in st.session_state:
    st.session_state.zones = {}
if 'video_path' not in st.session_state:
    st.session_state.video_path = None
if 'frame' not in st.session_state:
    st.session_state.frame = None
if 'frame_loaded' not in st.session_state:
    st.session_state.frame_loaded = False


def extract_first_frame(video_path: str) -> Optional[np.ndarray]:
    """Извлекает первый кадр из видео."""
    if not video_path or not os.path.exists(video_path):
        return None
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return None
    
    # Конвертируем BGR в RGB для отображения
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return frame_rgb


def draw_zones_on_frame(frame: np.ndarray, zones: Dict) -> np.ndarray:
    """Рисует зоны на кадре."""
    frame_copy = frame.copy()
    
    for zone_name, rect in zones.items():
        (x1, y1), (x2, y2) = rect
        # Рисуем прямоугольник
        cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 3)
        # Добавляем название
        cv2.putText(frame_copy, zone_name, (x1, y1 - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    return frame_copy


# Заголовок
st.title("🏪 Анализатор зон магазина")
st.markdown("Загрузите видео, выделите зоны и запустите анализ")

# Загрузка видео
st.sidebar.header("📁 Загрузка видео")
uploaded_file = st.sidebar.file_uploader(
    "Выберите видеофайл",
    type=['mp4', 'avi', 'mov'],
    help="Поддерживаются форматы: MP4, AVI, MOV"
)

if uploaded_file is not None:
    # Сохраняем загруженный файл во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name
    
    # Извлекаем первый кадр
    if not st.session_state.frame_loaded or st.session_state.video_path != tmp_path:
        with st.spinner("Загрузка видео..."):
            frame = extract_first_frame(tmp_path)
            if frame is not None:
                st.session_state.frame = frame
                st.session_state.frame_loaded = True
                st.session_state.video_path = tmp_path
                st.sidebar.success(f"✅ Видео загружено: {uploaded_file.name}")
            else:
                st.sidebar.error("❌ Ошибка загрузки видео")

# Загрузка существующих зон
if os.path.exists(ZONES_FILE):
    if st.sidebar.button("📥 Загрузить зоны из файла"):
        loaded_zones = load_zones_from_json(ZONES_FILE)
        st.session_state.zones = loaded_zones
        st.sidebar.success(f"Загружено зон: {len(loaded_zones)}")

# Основной интерфейс
if st.session_state.frame is not None:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🎯 Выделение зон")
        
        # Интерактивное выделение зон с drag & drop
        try:
            from components.zone_selector_simple import zone_selector
            
            st.markdown("**🎯 Выделение зон:** Зажмите ЛКМ и перетащите мышкой для создания прямоугольника")
            
            selected_zones = zone_selector(
                st.session_state.frame, 
                zones=st.session_state.zones,
                key="zone_selector_main"
            )
            
            # Показываем инструкцию
            st.info("""
            💡 **Инструкция по выделению зон:**
            1. Зажмите **ЛКМ** на изображении и перетащите для выделения прямоугольника
            2. Введите название зоны в поле ввода в компоненте
            3. Нажмите **➕ Добавить зону** в компоненте
            4. Повторите для всех зон
            5. Скопируйте JSON из компонента (кнопка "📋 Копировать JSON")
            6. Вставьте JSON ниже и нажмите "✅ Применить зоны из JSON"
            """)
            
            # Поле для JSON зон (для синхронизации с компонентом)
            with st.expander("📋 Применить зоны из компонента (вставьте JSON)", expanded=True):
                zones_json_display = json.dumps(
                    {name: {"top_left": list(rect[0]), "bottom_right": list(rect[1])} 
                     for name, rect in st.session_state.zones.items()},
                    ensure_ascii=False, indent=2
                )
                st.code(zones_json_display, language="json")
                
                st.markdown("**Скопируйте JSON из компонента ниже (кнопка '📋 Копировать JSON') и вставьте сюда:**")
                zones_json_input = st.text_area(
                    "JSON зон из компонента",
                    value="",
                    height=150,
                    placeholder='{"Зона 1": {"top_left": [100, 50], "bottom_right": [300, 200]}, ...}',
                    key="zones_json_input"
                )
                
                if st.button("✅ Применить зоны из JSON", key="apply_json_zones"):
                    try:
                        zones_data = json.loads(zones_json_input)
                        new_zones = {}
                        for name, coords in zones_data.items():
                            new_zones[name] = [
                                tuple(coords["top_left"]),
                                tuple(coords["bottom_right"])
                            ]
                        st.session_state.zones = new_zones
                        st.success(f"✅ Применено зон: {len(new_zones)}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Ошибка парсинга JSON: {e}")
        except ImportError:
            # Fallback: показываем изображение с зонами
            frame_with_zones = draw_zones_on_frame(st.session_state.frame, st.session_state.zones)
            st.image(frame_with_zones, use_container_width=True, caption="Первый кадр видео - выделите зоны")
            st.warning("⚠️ Компонент для drag & drop не найден. Используйте ручной ввод.")
        
        # Ввод зон вручную (резервный вариант)
        with st.expander("📝 Добавить зону вручную (если drag & drop не работает)"):
            zone_name = st.text_input("Название зоны", key="zone_name_input")
            col_x1, col_y1, col_x2, col_y2 = st.columns(4)
            with col_x1:
                x1 = st.number_input("X1", value=0, min_value=0, key="x1")
            with col_y1:
                y1 = st.number_input("Y1", value=0, min_value=0, key="y1")
            with col_x2:
                x2 = st.number_input("X2", value=100, min_value=0, key="x2")
            with col_y2:
                y2 = st.number_input("Y2", value=100, min_value=0, key="y2")
            
            if st.button("➕ Добавить зону", key="add_zone"):
                if zone_name:
                    st.session_state.zones[zone_name] = [(int(x1), int(y1)), (int(x2), int(y2))]
                    st.success(f"Зона '{zone_name}' добавлена!")
                    st.rerun()
                else:
                    st.error("Введите название зоны")
    
    with col2:
        st.subheader("📊 Текущие зоны")
        
        if st.session_state.zones:
            for zone_name, rect in st.session_state.zones.items():
                with st.container():
                    st.markdown(f"**{zone_name}**")
                    st.code(f"[(x1={rect[0][0]}, y1={rect[0][1]}), (x2={rect[1][0]}, y2={rect[1][1]})]")
                    if st.button(f"🗑️ Удалить", key=f"del_{zone_name}"):
                        del st.session_state.zones[zone_name]
                        st.rerun()
        else:
            st.info("Зоны не добавлены")
        
        # Управление зонами
        st.markdown("---")
        if st.button("💾 Сохранить зоны", use_container_width=True):
            zones_to_save = {}
            for zone_name, rect in st.session_state.zones.items():
                zones_to_save[zone_name] = {
                    "top_left": list(rect[0]),
                    "bottom_right": list(rect[1])
                }
            
            with open(ZONES_FILE, 'w', encoding='utf-8') as f:
                json.dump(zones_to_save, f, ensure_ascii=False, indent=2)
            st.success(f"✅ Сохранено зон: {len(st.session_state.zones)}")
        
        if st.button("🗑️ Очистить все зоны", use_container_width=True):
            st.session_state.zones = {}
            st.rerun()
        
        # Запуск анализа
        st.markdown("---")
        if st.session_state.video_path and st.session_state.zones:
            if st.button("🚀 Запустить анализ", use_container_width=True, type="primary"):
                with st.spinner("Обработка видео... Это может занять некоторое время"):
                    try:
                        # Временно устанавливаем зоны
                        import store_zone_analyzer
                        store_zone_analyzer.ZONES = st.session_state.zones
                        
                        # Обрабатываем видео
                        zone_statistics, last_frame, scale, scaled_zones, track_merges = process_video(
                            st.session_state.video_path
                        )
                        
                        # Вычисляем статистику
                        stats = calculate_statistics(zone_statistics, track_merges)
                        
                        # Отображаем результаты
                        st.success("✅ Анализ завершен!")
                        
                        # Таблица результатов
                        st.subheader("📈 Результаты анализа")
                        
                        # Формируем DataFrame для таблицы
                        results_data = []
                        for zone_name, data in sorted(stats.items(), key=lambda x: x[1]["total_time"], reverse=True):
                            results_data.append({
                                "Зона": zone_name,
                                "Суммарное время (сек)": f"{data['total_time']:.2f}",
                                "Среднее время (сек)": f"{data['avg_time']:.2f}",
                                "Посетителей": data['visitor_count']
                            })
                        
                        df = pd.DataFrame(results_data)
                        st.dataframe(df, use_container_width=True)
                        
                        # Визуализация
                        visualization = create_visualization(last_frame, stats, zone_statistics, scaled_zones)
                        visualization_rgb = cv2.cvtColor(visualization, cv2.COLOR_BGR2RGB)
                        
                        st.subheader("🎨 Визуализация результатов")
                        st.image(visualization_rgb, use_container_width=True, 
                                caption="Тепловая карта и цветовые зоны")
                        
                        # Сохраняем результат
                        output_path = "zone_analysis_result.png"
                        cv2.imwrite(output_path, visualization)
                        st.info(f"📁 Результат сохранен: {output_path}")
                        
                    except Exception as e:
                        st.error(f"❌ Ошибка анализа: {str(e)}")
                        st.exception(e)
        else:
            if not st.session_state.video_path:
                st.warning("⚠️ Сначала загрузите видео")
            if not st.session_state.zones:
                st.warning("⚠️ Сначала добавьте зоны")

else:
    st.info("👆 Загрузите видеофайл в боковой панели для начала работы")

# Инструкции
with st.expander("ℹ️ Инструкция по использованию"):
    st.markdown("""
    ### Как использовать:
    
    1. **Загрузка видео:** Используйте боковую панель для загрузки видеофайла
    2. **Добавление зон:** 
       - Используйте раздел "Добавить зону вручную" для ввода координат
       - Или используйте скрипт `setup_zones.py` для интерактивного выделения мышкой
       - Или загрузите зоны из файла zones.json
    3. **Сохранение зон:** Нажмите "Сохранить зоны" для сохранения в файл
    4. **Запуск анализа:** После добавления зон нажмите "Запустить анализ"
    
    ### Для интерактивного выделения зон мышкой:
    Запустите в терминале: `python setup_zones.py`
    Это откроет окно OpenCV с полной поддержкой drag & drop выделения прямоугольников.
    """)

