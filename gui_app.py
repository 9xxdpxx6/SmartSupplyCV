"""
GUI приложение для анализа зон магазина
Использует Streamlit для интерактивного интерфейса
Работает через FastAPI
"""

import streamlit as st
import cv2
import numpy as np
import json
import os
import pandas as pd
import requests
import time
from typing import Dict, Optional
from PIL import Image
import io

# Импортируем утилиту для предотвращения свайпа назад
from components.swipe_back_handler import prevent_swipe_back

# Настройки страницы
st.set_page_config(
    page_title="Анализатор зон магазина",
    page_icon="🏪",
    layout="wide"
)

# Предотвращаем свайп назад (можно отключить, передав enabled=False)
prevent_swipe_back()

# Настройка API URL
API_URL = os.getenv("API_URL", "http://localhost:8888")

# Инициализация состояния
if 'api_url' not in st.session_state:
    st.session_state.api_url = API_URL
if 'zones' not in st.session_state:
    st.session_state.zones = {}
if 'video_id' not in st.session_state:
    st.session_state.video_id = None
if 'frame' not in st.session_state:
    st.session_state.frame = None
if 'frame_loaded' not in st.session_state:
    st.session_state.frame_loaded = False
if 'task_id' not in st.session_state:
    st.session_state.task_id = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def check_api_connection(api_url: str) -> bool:
    """Проверяет подключение к API."""
    try:
        response = requests.get(f"{api_url}/", timeout=5)
        if response.status_code == 200:
            # Проверяем, что это действительно наш API (должен вернуть JSON)
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    # Проверяем, что это наш API по наличию поля "message"
                    return data.get("message") == "Анализатор зон магазина API"
                except:
                    return False
            return False
        return False
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False

def upload_video_to_api(api_url: str, file_bytes: bytes, filename: str) -> Optional[Dict]:
    """Загружает видео на сервер через API."""
    try:
        # Определяем MIME тип по расширению
        file_ext = os.path.splitext(filename)[1].lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.mkv': 'video/x-matroska',
            '.flv': 'video/x-flv'
        }
        mime_type = mime_types.get(file_ext, 'video/mp4')
        
        files = {"file": (filename, file_bytes, mime_type)}
        
        # Увеличиваем таймаут для больших файлов
        file_size_mb = len(file_bytes) / (1024 * 1024)
        timeout = max(60, int(file_size_mb * 2))  # 2 секунды на МБ, минимум 60 секунд
        
        response = requests.post(
            f"{api_url}/upload-video",
            files=files,
            timeout=timeout
        )
        
        if response.status_code == 200:
            # Проверяем, что ответ действительно JSON
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type or not content_type:
                try:
                    return response.json()
                except ValueError as e:
                    st.error(f"Ошибка парсинга JSON ответа: {str(e)}")
                    st.error(f"Content-Type: {content_type}")
                    st.error(f"Ответ сервера (первые 500 символов): {response.text[:500]}")
                    return None
            else:
                st.error(f"Неожиданный тип ответа: {content_type}")
                st.error(f"Ответ сервера (первые 500 символов): {response.text[:500]}")
                return None
        else:
            # Проверяем, что это действительно наш API
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                # Это HTML страница, значит запрос идет не на наш API
                st.error(f"❌ Эндпоинт не найден (404). Возможные причины:")
                st.error(f"1. API сервер не запущен или недоступен по адресу: {api_url}")
                st.error(f"2. Неправильный URL API. Проверьте настройки.")
                st.error(f"3. Запрос идет на другой сервер (получен HTML вместо JSON)")
                st.info(f"💡 Убедитесь, что FastAPI сервер запущен: `python api.py` или `uvicorn api:app`")
                st.info(f"💡 Проверьте доступность API: {api_url}/docs")
                return None
            
            # Пытаемся получить JSON ошибку, если есть
            try:
                error_data = response.json()
                error_msg = error_data.get('detail', str(error_data))
            except ValueError:
                # Если не JSON, показываем текст ошибки
                error_msg = response.text[:500] if response.text else f"HTTP {response.status_code}"
            st.error(f"Ошибка загрузки видео (код {response.status_code}): {error_msg}")
            return None
    except requests.exceptions.ConnectionError:
        st.error(f"Не удалось подключиться к API: {api_url}. Убедитесь, что сервер запущен.")
        return None
    except requests.exceptions.Timeout:
        st.error("Превышено время ожидания. Файл слишком большой или сервер не отвечает.")
        return None
    except Exception as e:
        st.error(f"Ошибка подключения к API: {str(e)}")
        import traceback
        st.error(f"Детали: {traceback.format_exc()}")
        return None

def get_first_frame_from_api(api_url: str, video_id: str) -> Optional[np.ndarray]:
    """Получает первый кадр видео через API."""
    try:
        response = requests.get(f"{api_url}/videos/{video_id}/first-frame", timeout=10)
        if response.status_code == 200:
            # Декодируем изображение
            img = Image.open(io.BytesIO(response.content))
            return np.array(img)
        else:
            return None
    except Exception as e:
        st.error(f"Ошибка получения кадра: {str(e)}")
        return None

def get_zones_from_api(api_url: str) -> Dict:
    """Получает зоны через API."""
    try:
        response = requests.get(f"{api_url}/zones", timeout=5)
        if response.status_code == 200:
            try:
                data = response.json()
                # Конвертируем из API формата во внутренний
                zones = {}
                for zone_name, coords in data["zones"].items():
                    zones[zone_name] = [
                        tuple(coords["top_left"]),
                        tuple(coords["bottom_right"])
                    ]
                return zones
            except ValueError as e:
                st.warning(f"Ошибка парсинга ответа зон: {str(e)}")
                return {}
        else:
            return {}
    except Exception as e:
        st.warning(f"Ошибка получения зон: {str(e)}")
        return {}

def set_zones_to_api(api_url: str, zones: Dict) -> bool:
    """Устанавливает зоны через API."""
    try:
        # Конвертируем во внутренний формат в API формат
        zones_request = {
            "zones": {
                zone_name: {
                    "top_left": list(rect[0]),
                    "bottom_right": list(rect[1])
                }
                for zone_name, rect in zones.items()
            }
        }
        response = requests.post(
            f"{api_url}/zones",
            json=zones_request,
            timeout=10
        )
        if response.status_code == 200:
            return True
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('detail', response.text)
            except:
                error_msg = response.text
            st.error(f"Ошибка установки зон (код {response.status_code}): {error_msg}")
            return False
    except requests.exceptions.ConnectionError:
        st.error(f"Не удалось подключиться к API: {api_url}")
        return False
    except Exception as e:
        st.error(f"Ошибка установки зон: {str(e)}")
        return False

def start_analysis(api_url: str, video_id: str, zones: Optional[Dict] = None) -> Optional[str]:
    """Запускает анализ через API."""
    try:
        request_data = {"video_id": video_id}
        if zones:
            request_data["zones"] = {
                zone_name: {
                    "top_left": list(rect[0]),
                    "bottom_right": list(rect[1])
                }
                for zone_name, rect in zones.items()
            }
        
        response = requests.post(
            f"{api_url}/analyze",
            json=request_data,
            timeout=10
        )
        if response.status_code == 200:
            try:
                data = response.json()
                return data.get("task_id")
            except ValueError as e:
                st.error(f"Ошибка парсинга ответа: {str(e)}")
                st.error(f"Ответ сервера: {response.text[:500]}")
                return None
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('detail', response.text)
            except:
                error_msg = response.text
            st.error(f"Ошибка запуска анализа (код {response.status_code}): {error_msg}")
            return None
    except requests.exceptions.ConnectionError:
        st.error(f"Не удалось подключиться к API: {api_url}")
        return None
    except Exception as e:
        st.error(f"Ошибка подключения к API: {str(e)}")
        return None

def get_task_status(api_url: str, task_id: str) -> Optional[Dict]:
    """Получает статус задачи через API."""
    try:
        response = requests.get(f"{api_url}/tasks/{task_id}", timeout=5)
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return None
        else:
            return None
    except:
        return None

def get_statistics(api_url: str, task_id: str) -> Optional[Dict]:
    """Получает статистику через API."""
    try:
        response = requests.get(f"{api_url}/statistics/{task_id}", timeout=5)
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return None
        else:
            return None
    except:
        return None

def get_visualization(api_url: str, task_id: str) -> Optional[np.ndarray]:
    """Получает визуализацию через API."""
    try:
        response = requests.get(f"{api_url}/visualization/{task_id}", timeout=30)
        if response.status_code == 200:
            img = Image.open(io.BytesIO(response.content))
            return np.array(img)
        else:
            return None
    except:
        return None

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

# ============================================================================
# ИНТЕРФЕЙС
# ============================================================================

# Заголовок
st.title("🏪 Анализатор зон магазина")
st.markdown("Загрузите видео, выделите зоны и запустите анализ")

# Настройка API URL
with st.sidebar.expander("⚙️ Настройки API"):
    api_url_input = st.text_input(
        "URL API",
        value=st.session_state.api_url,
        help="URL сервера FastAPI (например: http://localhost:8888)"
    )
    if st.button("🔄 Обновить URL"):
        st.session_state.api_url = api_url_input
        st.rerun()
    
    # Проверка подключения
    if st.button("🔄 Проверить подключение", use_container_width=True):
        st.rerun()
    
    if check_api_connection(st.session_state.api_url):
        st.success("✅ Подключение к API установлено")
        st.info(f"📡 API доступен по адресу: {st.session_state.api_url}")
    else:
        st.error(f"❌ Не удалось подключиться к API: {st.session_state.api_url}")
        st.warning("**Возможные причины:**")
        st.markdown("""
        1. **API сервер не запущен** - запустите в терминале:
           ```bash
           python api.py
           ```
           или
           ```bash
           uvicorn api:app --host 0.0.0.0 --port 8888
           ```
        
        2. **Неправильный URL** - проверьте, что URL правильный (по умолчанию: http://localhost:8888)
        
        3. **Порт занят** - убедитесь, что порт 8888 свободен
        """)
        st.info(f"💡 Проверьте доступность API в браузере: [{st.session_state.api_url}/docs]({st.session_state.api_url}/docs)")

# Загрузка видео
st.sidebar.header("📁 Загрузка видео")
uploaded_file = st.sidebar.file_uploader(
    "Выберите видеофайл",
    type=['mp4', 'avi', 'mov'],
    help="Поддерживаются форматы: MP4, AVI, MOV"
)

if uploaded_file is not None:
    # Проверяем подключение к API перед загрузкой
    if not check_api_connection(st.session_state.api_url):
        st.sidebar.error("❌ API недоступен. Проверьте подключение в настройках.")
    else:
        # Загружаем видео на сервер
        if st.session_state.video_id is None or st.session_state.frame_loaded == False:
            with st.spinner("Загрузка видео на сервер..."):
                file_bytes = uploaded_file.read()
                result = upload_video_to_api(st.session_state.api_url, file_bytes, uploaded_file.name)
                
                if result:
                    st.session_state.video_id = result["video_id"]
                    st.session_state.frame_loaded = False  # Сброс для загрузки кадра
                    st.sidebar.success(f"✅ Видео загружено: {uploaded_file.name}")
                else:
                    st.sidebar.error("❌ Ошибка загрузки видео")

# Загрузка первого кадра
if st.session_state.video_id and not st.session_state.frame_loaded:
    with st.spinner("Загрузка первого кадра..."):
        frame = get_first_frame_from_api(st.session_state.api_url, st.session_state.video_id)
        if frame is not None:
            st.session_state.frame = frame
            st.session_state.frame_loaded = True
        else:
            st.error("Не удалось загрузить первый кадр")

# Загрузка существующих зон из API
if st.sidebar.button("📥 Загрузить зоны из API"):
    with st.spinner("Загрузка зон..."):
        zones = get_zones_from_api(st.session_state.api_url)
        if zones:
            st.session_state.zones = zones
            st.sidebar.success(f"Загружено зон: {len(zones)}")
        else:
            st.sidebar.info("Зоны не найдены на сервере")

# Основной интерфейс
if st.session_state.frame is not None:
    col1, col2 = st.columns([7, 5])
    
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
        if st.button("💾 Сохранить зоны в API", use_container_width=True):
            if set_zones_to_api(st.session_state.api_url, st.session_state.zones):
                st.success(f"✅ Сохранено зон в API: {len(st.session_state.zones)}")
            else:
                st.error("❌ Ошибка сохранения зон")
        
        if st.button("🗑️ Очистить все зоны", use_container_width=True):
            st.session_state.zones = {}
            st.rerun()
        
        # Запуск анализа
        st.markdown("---")
        if st.session_state.video_id and st.session_state.zones:
            if st.button("🚀 Запустить анализ", use_container_width=True, type="primary"):
                with st.spinner("Запуск анализа..."):
                    task_id = start_analysis(
                        st.session_state.api_url,
                        st.session_state.video_id,
                        st.session_state.zones
                    )
                    if task_id:
                        st.session_state.task_id = task_id
                        st.session_state.analysis_complete = False
                        st.success("✅ Анализ запущен!")
                    else:
                        st.error("❌ Ошибка запуска анализа")
        else:
            if not st.session_state.video_id:
                st.warning("⚠️ Сначала загрузите видео")
            if not st.session_state.zones:
                st.warning("⚠️ Сначала добавьте зоны")
        
        # Отслеживание статуса задачи
        if st.session_state.task_id:
            st.markdown("---")
            st.subheader("📊 Статус анализа")
            
            task_status = get_task_status(st.session_state.api_url, st.session_state.task_id)
            
            if task_status:
                status = task_status.get("status", "unknown")
                
                if status == "pending":
                    st.info("⏳ Ожидание обработки...")
                    # Автоматическое обновление
                    time.sleep(1)
                    st.rerun()
                elif status == "processing":
                    st.info("🔄 Обработка видео... Это может занять некоторое время")
                    st.progress(0.5)  # Примерный прогресс
                    # Автоматическое обновление
                    time.sleep(2)
                    st.rerun()
                elif status == "completed":
                    st.success("✅ Анализ завершен!")
                    if not st.session_state.analysis_complete:
                        st.session_state.analysis_complete = True
                        st.rerun()
                    
                    # Отображение результатов
                    st.markdown("---")
                    st.subheader("📈 Результаты анализа")
                    
                    # Получаем статистику
                    stats_data = get_statistics(st.session_state.api_url, st.session_state.task_id)
                    
                    if stats_data and "statistics" in stats_data:
                        # Формируем DataFrame для таблицы
                        results_data = []
                        for zone_name, data in sorted(
                            stats_data["statistics"].items(),
                            key=lambda x: x[1]["total_time"],
                            reverse=True
                        ):
                            results_data.append({
                                "Зона": zone_name,
                                "Суммарное время (сек)": f"{data['total_time']:.2f}",
                                "Среднее время (сек)": f"{data['avg_time']:.2f}",
                                "Посетителей": data['visitor_count']
                            })
                        
                        df = pd.DataFrame(results_data)
                        st.dataframe(df, use_container_width=True)
                        
                        # Получаем визуализацию
                        visualization = get_visualization(st.session_state.api_url, st.session_state.task_id)
                        
                        if visualization is not None:
                            st.subheader("🎨 Визуализация результатов")
                            st.image(visualization, use_container_width=True, 
                                    caption="Тепловая карта и цветовые зоны")
                        else:
                            st.warning("⚠️ Визуализация недоступна")
                    else:
                        st.warning("⚠️ Статистика недоступна")
                elif status == "failed":
                    error = task_status.get("error", "Неизвестная ошибка")
                    st.error(f"❌ Ошибка анализа: {error}")
            else:
                st.warning("⚠️ Не удалось получить статус задачи")

else:
    if st.session_state.frame is None:
        st.info("👆 Загрузите видеофайл в боковой панели для начала работы")

# Инструкции
with st.expander("ℹ️ Инструкция по использованию"):
    st.markdown("""
    ### Как использовать:
    
    1. **Настройка API:** Убедитесь, что сервер FastAPI запущен (`python api.py` или `uvicorn api:app`)
    2. **Загрузка видео:** Используйте боковую панель для загрузки видеофайла (видео загружается на сервер)
    3. **Добавление зон:** 
       - Используйте интерактивный компонент для выделения зон мышкой
       - Или используйте раздел "Добавить зону вручную" для ввода координат
       - Или загрузите зоны из API (кнопка "📥 Загрузить зоны из API")
    4. **Сохранение зон:** Нажмите "💾 Сохранить зоны в API" для сохранения на сервере
    5. **Запуск анализа:** После добавления зон нажмите "🚀 Запустить анализ"
    6. **Просмотр результатов:** После завершения анализа результаты отобразятся автоматически
    
    ### Требования:
    - Сервер FastAPI должен быть запущен и доступен
    - URL API можно настроить в боковой панели (по умолчанию: http://localhost:8888)
    """)
