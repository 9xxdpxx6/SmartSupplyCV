"""
Streamlit компонент для выделения зон на изображении с drag & drop
"""

import streamlit.components.v1 as components
import json
import numpy as np

def zone_selector(image, zones=None, key=None):
    """
    Компонент для выделения зон на изображении с drag & drop.
    
    Args:
        image: numpy array изображения или путь к изображению
        zones: словарь существующих зон {name: [(x1,y1), (x2,y2)]}
        key: уникальный ключ для компонента
    
    Returns:
        словарь зон или None
    """
    
    # Конвертируем изображение в base64 если это numpy array
    import base64
    from PIL import Image
    import io
    
    if isinstance(image, np.ndarray):
        pil_image = Image.fromarray(image)
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        img_data = f"data:image/png;base64,{img_str}"
    else:
        # Если это путь к файлу
        with open(image, "rb") as f:
            img_str = base64.b64encode(f.read()).decode()
            img_data = f"data:image/png;base64,{img_str}"
    
    # Подготавливаем существующие зоны
    zones_data = []
    if zones:
        for name, rect in zones.items():
            (x1, y1), (x2, y2) = rect
            zones_data.append({
                "name": name,
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2)
            })
    
    # HTML/JavaScript код для drag & drop
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #canvas-container {{
                position: relative;
                display: inline-block;
                border: 2px solid #ccc;
                cursor: crosshair;
            }}
            #canvas {{
                display: block;
                max-width: 100%;
                height: auto;
            }}
            .zone {{
                position: absolute;
                border: 3px solid #00ff00;
                background: rgba(0, 255, 0, 0.1);
                cursor: move;
            }}
            .zone-label {{
                position: absolute;
                background: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 2px 6px;
                font-size: 12px;
                font-weight: bold;
                pointer-events: none;
            }}
        </style>
    </head>
    <body>
        <div id="canvas-container">
            <canvas id="canvas"></canvas>
        </div>
        <div id="zones-list"></div>
        <input type="text" id="zone-name" placeholder="Название зоны" style="margin-top: 10px;">
        <button onclick="addZone()">Добавить зону</button>
        <button onclick="saveZones()">Сохранить</button>
        <button onclick="clearZones()">Очистить</button>
        
        <script>
            const img = new Image();
            img.src = "{img_data}";
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            
            let zones = {json.dumps(zones_data)};
            let isDrawing = false;
            let startX = 0;
            let startY = 0;
            let currentRect = null;
            let scaleX = 1;
            let scaleY = 1;
            
            img.onload = function() {{
                // Устанавливаем размер canvas
                const maxWidth = 800;
                scaleX = img.width > maxWidth ? maxWidth / img.width : 1;
                scaleY = img.height * scaleX / img.width;
                
                canvas.width = img.width * scaleX;
                canvas.height = img.height * scaleY;
                
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                drawAllZones();
            }};
            
            function drawRect(x1, y1, x2, y2, color = '#00ff00') {{
                ctx.strokeStyle = color;
                ctx.lineWidth = 3;
                ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
            }}
            
            function drawAllZones() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                
                zones.forEach(zone => {{
                    drawRect(zone.x1 * scaleX, zone.y1 * scaleY, 
                            zone.x2 * scaleX, zone.y2 * scaleY);
                    ctx.fillStyle = 'rgba(0, 255, 0, 0.1)';
                    ctx.fillRect(zone.x1 * scaleX, zone.y1 * scaleY, 
                                (zone.x2 - zone.x1) * scaleX, 
                                (zone.y2 - zone.y1) * scaleY);
                    ctx.fillStyle = 'white';
                    ctx.font = '14px Arial';
                    ctx.fillText(zone.name, zone.x1 * scaleX + 5, zone.y1 * scaleY - 5);
                }});
                
                if (currentRect) {{
                    drawRect(currentRect.x1, currentRect.y1, 
                            currentRect.x2, currentRect.y2, '#ff0000');
                }}
            }}
            
            canvas.addEventListener('mousedown', function(e) {{
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) / scaleX;
                const y = (e.clientY - rect.top) / scaleY;
                
                isDrawing = true;
                startX = x;
                startY = y;
            }});
            
            canvas.addEventListener('mousemove', function(e) {{
                if (!isDrawing) return;
                
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) / scaleX;
                const y = (e.clientY - rect.top) / scaleY;
                
                currentRect = {{
                    x1: Math.min(startX, x) * scaleX,
                    y1: Math.min(startY, y) * scaleY,
                    x2: Math.max(startX, x) * scaleX,
                    y2: Math.max(startY, y) * scaleY
                }};
                
                drawAllZones();
            }});
            
            canvas.addEventListener('mouseup', function(e) {{
                if (!isDrawing) return;
                
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) / scaleX;
                const y = (e.clientY - rect.top) / scaleY;
                
                const x1 = Math.min(startX, x);
                const y1 = Math.min(startY, y);
                const x2 = Math.max(startX, x);
                const y2 = Math.max(startY, y);
                
                if (Math.abs(x2 - x1) > 10 && Math.abs(y2 - y1) > 10) {{
                    currentRect = {{
                        x1: x1, y1: y1, x2: x2, y2: y2
                    }};
                }}
                
                isDrawing = false;
            }});
            
            function addZone() {{
                const name = document.getElementById('zone-name').value.trim();
                if (!name || !currentRect) {{
                    alert('Введите название зоны и выделите область');
                    return;
                }}
                
                zones.push({{
                    name: name,
                    x1: Math.round(currentRect.x1 / scaleX),
                    y1: Math.round(currentRect.y1 / scaleY),
                    x2: Math.round(currentRect.x2 / scaleX),
                    y2: Math.round(currentRect.y2 / scaleY)
                }});
                
                currentRect = null;
                document.getElementById('zone-name').value = '';
                drawAllZones();
                updateZonesList();
            }}
            
            function updateZonesList() {{
                const list = document.getElementById('zones-list');
                list.innerHTML = '<h3>Зоны:</h3>';
                zones.forEach((zone, index) => {{
                    const div = document.createElement('div');
                    div.innerHTML = `${{zone.name}}: [${{zone.x1}}, ${{zone.y1}}] - [${{zone.x2}}, ${{zone.y2}}] 
                        <button onclick="deleteZone(${{index}})">Удалить</button>`;
                    list.appendChild(div);
                }});
            }}
            
            function deleteZone(index) {{
                zones.splice(index, 1);
                drawAllZones();
                updateZonesList();
            }}
            
            function clearZones() {{
                if (confirm('Очистить все зоны?')) {{
                    zones = [];
                    currentRect = null;
                    drawAllZones();
                    updateZonesList();
                }}
            }}
            
            function saveZones() {{
                // Отправляем данные обратно в Streamlit
                window.parent.postMessage({{
                    type: 'streamlit:setComponentValue',
                    value: zones
                }}, '*');
            }}
            
            // Инициализация
            updateZonesList();
        </script>
    </body>
    </html>
    """
    
    # Рендерим компонент
    result = components.html(html_code, height=600, key=key)
    
    # Конвертируем результат обратно в формат зон
    if result:
        zones_dict = {}
        for zone in result:
            zones_dict[zone['name']] = [
                (zone['x1'], zone['y1']),
                (zone['x2'], zone['y2'])
            ]
        return zones_dict
    
    return None

