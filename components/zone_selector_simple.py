"""
Упрощенный компонент для выделения зон с drag & drop через HTML/JavaScript
Работает напрямую без сборки
"""

import streamlit.components.v1 as components
import json
import numpy as np
import base64
from PIL import Image
import io

def zone_selector(image, zones=None, key=None):
    """
    Компонент для выделения зон на изображении с drag & drop.
    
    Args:
        image: numpy array изображения (RGB)
        zones: словарь существующих зон {name: [(x1,y1), (x2,y2)]}
        key: уникальный ключ для компонента
    
    Returns:
        словарь зон или переданные zones если ничего не изменилось
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
        return zones if zones else None
    
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
    
    zones_json = json.dumps(zones_data, ensure_ascii=False)
    
    # Подготавливаем ключ для использования в JavaScript
    key_str = key or "default"
    
    # HTML/JavaScript код для drag & drop
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 10px;
                font-family: Arial, sans-serif;
                background: #1e1e1e;
                color: white;
            }}
            #container {{
                position: relative;
                display: inline-block;
                border: 2px solid #4CAF50;
                background: #000;
                border-radius: 5px;
            }}
            #canvas {{
                display: block;
                cursor: crosshair;
                max-width: 100%;
            }}
            #controls {{
                margin-top: 10px;
                padding: 15px;
                background: #2d2d2d;
                border-radius: 5px;
            }}
            input[type="text"] {{
                padding: 8px;
                margin-right: 10px;
                width: 200px;
                border: 1px solid #555;
                border-radius: 3px;
                background: #1e1e1e;
                color: white;
            }}
            button {{
                padding: 8px 15px;
                margin: 5px;
                cursor: pointer;
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
            }}
            button:hover {{
                background: #45a049;
            }}
            button.delete {{
                background: #f44336;
            }}
            button.delete:hover {{
                background: #da190b;
            }}
            button.save {{
                background: #2196F3;
            }}
            button.save:hover {{
                background: #0b7dda;
            }}
            #zones-list {{
                margin-top: 10px;
                max-height: 200px;
                overflow-y: auto;
            }}
            .zone-item {{
                padding: 8px;
                margin: 5px 0;
                background: #1e1e1e;
                border-left: 3px solid #4CAF50;
                border-radius: 3px;
            }}
            .zone-item strong {{
                color: #4CAF50;
            }}
        </style>
    </head>
    <body>
        <div id="container">
            <canvas id="canvas"></canvas>
        </div>
        <div id="controls">
            <div style="margin-bottom: 10px;">
                <input type="text" id="zone-name" placeholder="Введите название зоны">
                <button onclick="addZone()">➕ Добавить зону</button>
                <button onclick="clearSelection()">🗑️ Очистить выделение</button>
            </div>
            <div id="zones-list"></div>
            <div style="margin-top: 10px;">
                <button onclick="saveZones()" class="save">💾 Сохранить зоны</button>
                <button onclick="clearAllZones()" class="delete">🗑️ Очистить все</button>
            </div>
            <div style="margin-top: 10px; padding: 10px; background: #1e1e1e; border-radius: 5px;">
                <strong>📋 JSON зон (скопируйте и вставьте в Streamlit):</strong>
                <textarea id="zones-json" readonly style="width: 100%; height: 100px; margin-top: 5px; padding: 5px; background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 3px; font-family: monospace; font-size: 12px;"></textarea>
                <button onclick="copyJSON()" id="copy-json-btn" style="margin-top: 5px; background: #6e7681;">📋 Копировать JSON</button>
            </div>
        </div>
        
        <script>
            const img = new Image();
            img.src = "{img_data}";
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            
            let zones = {zones_json};
            let isDrawing = false;
            let startX = 0;
            let startY = 0;
            let currentRect = null;
            let scale = 1.0;
            
            img.onload = function() {{
                // Устанавливаем размер canvas
                const maxWidth = 1200;
                if (img.width > maxWidth) {{
                    scale = maxWidth / img.width;
                }}
                
                canvas.width = img.width * scale;
                canvas.height = img.height * scale;
                
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                drawAllZones();
                updateZonesList();
                updateJSON();
            }};
            
            function drawRect(x1, y1, x2, y2, color = '#00ff00', fill = false) {{
                ctx.strokeStyle = color;
                ctx.lineWidth = 3;
                ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                if (fill) {{
                    ctx.fillStyle = color + '40';
                    ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
                }}
            }}
            
            function drawAllZones() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                
                zones.forEach((zone, index) => {{
                    const x1 = zone.x1 * scale;
                    const y1 = zone.y1 * scale;
                    const x2 = zone.x2 * scale;
                    const y2 = zone.y2 * scale;
                    
                    drawRect(x1, y1, x2, y2, '#00ff00', true);
                    ctx.fillStyle = 'white';
                    ctx.font = 'bold 14px Arial';
                    ctx.strokeStyle = 'black';
                    ctx.lineWidth = 3;
                    ctx.strokeText(zone.name, x1 + 5, y1 - 5);
                    ctx.fillText(zone.name, x1 + 5, y1 - 5);
                }});
                
                if (currentRect) {{
                    drawRect(currentRect.x1, currentRect.y1, 
                            currentRect.x2, currentRect.y2, '#ff0000', true);
                }}
            }}
            
            canvas.addEventListener('mousedown', function(e) {{
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) / scale;
                const y = (e.clientY - rect.top) / scale;
                
                isDrawing = true;
                startX = x;
                startY = y;
                currentRect = null;
            }});
            
            canvas.addEventListener('mousemove', function(e) {{
                if (!isDrawing) return;
                
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) / scale;
                const y = (e.clientY - rect.top) / scale;
                
                currentRect = {{
                    x1: Math.min(startX, x) * scale,
                    y1: Math.min(startY, y) * scale,
                    x2: Math.max(startX, x) * scale,
                    y2: Math.max(startY, y) * scale
                }};
                
                drawAllZones();
            }});
            
            canvas.addEventListener('mouseup', function(e) {{
                if (!isDrawing) return;
                
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) / scale;
                const y = (e.clientY - rect.top) / scale;
                
                const x1 = Math.min(startX, x);
                const y1 = Math.min(startY, y);
                const x2 = Math.max(startX, x);
                const y2 = Math.max(startY, y);
                
                if (Math.abs(x2 - x1) > 10 && Math.abs(y2 - y1) > 10) {{
                    currentRect = {{
                        x1: x1 * scale,
                        y1: y1 * scale,
                        x2: x2 * scale,
                        y2: y2 * scale,
                        orig_x1: Math.round(x1),
                        orig_y1: Math.round(y1),
                        orig_x2: Math.round(x2),
                        orig_y2: Math.round(y2)
                    }};
                }}
                
                isDrawing = false;
                drawAllZones();
            }});
            
            function addZone() {{
                const name = document.getElementById('zone-name').value.trim();
                if (!name) {{
                    // Визуальная обратная связь
                    const nameInput = document.getElementById('zone-name');
                    nameInput.style.border = '2px solid #f44336';
                    setTimeout(() => {{
                        nameInput.style.border = '1px solid #555';
                    }}, 2000);
                    return;
                }}
                
                if (!currentRect || !currentRect.orig_x1) {{
                    // Визуальная обратная связь
                    const nameInput = document.getElementById('zone-name');
                    nameInput.placeholder = 'Сначала выделите область на изображении!';
                    nameInput.style.border = '2px solid #f44336';
                    setTimeout(() => {{
                        nameInput.placeholder = 'Введите название зоны';
                        nameInput.style.border = '1px solid #555';
                    }}, 2000);
                    return;
                }}
                
                zones.push({{
                    name: name,
                    x1: currentRect.orig_x1,
                    y1: currentRect.orig_y1,
                    x2: currentRect.orig_x2,
                    y2: currentRect.orig_y2
                }});
                
                currentRect = null;
                document.getElementById('zone-name').value = '';
                drawAllZones();
                updateZonesList();
                saveZones();
            }}
            
            function updateZonesList() {{
                const list = document.getElementById('zones-list');
                list.innerHTML = '<strong>Зоны ({' + zones.length + '}):</strong>';
                zones.forEach((zone, index) => {{
                    const div = document.createElement('div');
                    div.className = 'zone-item';
                    div.innerHTML = `<strong>${{zone.name}}</strong>: [${{zone.x1}}, ${{zone.y1}}] - [${{zone.x2}}, ${{zone.y2}}] 
                        <button onclick="deleteZone(${{index}})" class="delete">Удалить</button>`;
                    list.appendChild(div);
                }});
                updateJSON();
            }}
            
            function updateJSON() {{
                const jsonOutput = document.getElementById('zones-json');
                const zonesObj = {{}};
                zones.forEach(zone => {{
                    zonesObj[zone.name] = {{
                        top_left: [zone.x1, zone.y1],
                        bottom_right: [zone.x2, zone.y2]
                    }};
                }});
                jsonOutput.value = JSON.stringify(zonesObj, null, 2);
            }}
            
            function copyJSON() {{
                const jsonOutput = document.getElementById('zones-json');
                jsonOutput.select();
                document.execCommand('copy');
                // Визуальная обратная связь без alert
                const copyButton = document.getElementById('copy-json-btn');
                if (copyButton) {{
                    const originalText = copyButton.textContent;
                    copyButton.textContent = '✅ Скопировано!';
                    copyButton.style.background = '#4CAF50';
                    setTimeout(() => {{
                        copyButton.textContent = originalText;
                        copyButton.style.background = '#6e7681';
                    }}, 2000);
                }}
            }}
            
            function deleteZone(index) {{
                zones.splice(index, 1);
                drawAllZones();
                updateZonesList();
                saveZones();
            }}
            
            function clearSelection() {{
                currentRect = null;
                drawAllZones();
            }}
            
            function clearAllZones() {{
                if (confirm('Очистить все зоны?')) {{
                    zones = [];
                    currentRect = null;
                    drawAllZones();
                    updateZonesList();
                    saveZones();
                }}
            }}
            
            function saveZones() {{
                // Сохраняем в localStorage
                const storageKey = 'zones_data_{key_str}';
                localStorage.setItem(storageKey, JSON.stringify(zones));
                
                // Пытаемся отправить через postMessage для Streamlit
                try {{
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: JSON.stringify(zones)
                    }}, '*');
                }} catch(e) {{
                    console.log('postMessage failed:', e);
                }}
                
                // Обновляем JSON поле
                updateJSON();
            }}
        </script>
    </body>
    </html>
    """
    
    # Рендерим компонент
    # Заменяем placeholder ключа в HTML коде
    html_code_final = html_code.replace('{key_str}', key_str)
    components.html(html_code_final, height=900)
    
    # Возвращаем переданные зоны (данные будут синхронизироваться через JSON)
    return zones if zones else None

