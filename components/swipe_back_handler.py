"""
Утилита для предотвращения свайпа назад в браузере на страницах Streamlit
Можно использовать на всех страницах и отключать локально при необходимости
"""

import streamlit as st
from typing import Optional

# Глобальная настройка по умолчанию
DEFAULT_ENABLED = True

def prevent_swipe_back(enabled: Optional[bool] = None):
    """
    Предотвращает свайп назад в браузере (жест навигации назад).
    
    Args:
        enabled: Если True - включает защиту от свайпа назад,
                 Если False - отключает,
                 Если None - использует глобальную настройку DEFAULT_ENABLED
    """
    # Определяем, включена ли защита
    if enabled is None:
        enabled = DEFAULT_ENABLED
    
    if not enabled:
        return
    
    # JavaScript код для предотвращения свайпа назад
    swipe_back_prevention_js = """
    <script>
    (function() {
        // Предотвращаем свайп назад на touch устройствах
        let touchStartX = 0;
        let touchStartY = 0;
        
        document.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        }, { passive: true });
        
        document.addEventListener('touchmove', function(e) {
            if (!touchStartX || !touchStartY) return;
            
            const touchEndX = e.touches[0].clientX;
            const touchEndY = e.touches[0].clientY;
            
            const diffX = touchStartX - touchEndX;
            const diffY = touchStartY - touchEndY;
            
            // Если свайп вправо (назад) больше чем вверх/вниз, предотвращаем
            if (Math.abs(diffX) > Math.abs(diffY) && diffX > 50) {
                e.preventDefault();
            }
        }, { passive: false });
        
        // Предотвращаем навигацию назад через popstate
        window.addEventListener('popstate', function(e) {
            // Сохраняем текущее состояние
            history.pushState(null, null, location.href);
        });
        
        // Добавляем состояние в историю при загрузке
        history.pushState(null, null, location.href);
    })();
    </script>
    """
    
    # Вставляем JavaScript через markdown с unsafe_allow_html
    # Используем markdown вместо html компонента для более легкого использования
    st.markdown(swipe_back_prevention_js, unsafe_allow_html=True)

def set_global_swipe_back_enabled(enabled: bool):
    """
    Устанавливает глобальную настройку для всех страниц.
    
    Args:
        enabled: True для включения, False для отключения
    """
    global DEFAULT_ENABLED
    DEFAULT_ENABLED = enabled

