from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
import threading
import time
from smart_alarm import SleepAnalyzer

app = Flask(__name__)
CORS(app)

class SleepWebServer:
    def __init__(self, sleep_analyzer=None):
        self.sleep_analyzer = sleep_analyzer
        self.sleep_data_file = 'sleep_data.json'
        
    def load_sleep_data(self):
        """Загрузка данных о сне"""
        try:
            with open(self.sleep_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return self.generate_demo_data()
    
    def generate_demo_data(self):
        """Генерация демо-данных для показа"""
        demo_data = {}
        base_date = datetime.now() - timedelta(days=7)
        
        for i in range(7):
            date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            demo_data[date] = {
                'quality': round(6.5 + (i * 0.3) + ((-1)**i * 0.2), 1),
                'duration': round(6.8 + (i * 0.1), 1),
                'sleep_time': f"{22 + (i % 2)}:{15 + (i * 5)}",
                'wake_time': f"6:{30 + (i * 2)}",
                'notes': f"Сон {i+1} день"
            }
        return demo_data
    
    def get_stats_summary(self, data):
        """Получение сводной статистики"""
        if not data:
            return {}
            
        qualities = [day['quality'] for day in data.values()]
        durations = [day['duration'] for day in data.values()]
        
        return {
            'avg_quality': round(sum(qualities) / len(qualities), 1),
            'avg_duration': round(sum(durations) / len(durations), 1),
            'best_quality': max(qualities),
            'worst_quality': min(qualities),
            'total_nights': len(data),
            'quality_trend': self.calculate_trend(qualities),
            'duration_trend': self.calculate_trend(durations)
        }
    
    def calculate_trend(self, values):
        """Вычисление тренда"""
        if len(values) < 2:
            return 'neutral'
            
        recent = sum(values[-3:]) / 3 if len(values) >= 3 else values[-1]
        older = sum(values[:3]) / 3 if len(values) >= 3 else values[0]
        
        if recent > older + 0.2:
            return 'up'
        elif recent < older - 0.2:
            return 'down'
        return 'neutral'
    
    def get_recommendations(self, data):
        """Генерация рекомендаций"""
        if not data:
            return []
            
        recommendations = []
        
        # Анализ качества сна
        avg_quality = sum(day['quality'] for day in data.values()) / len(data)
        if avg_quality < 7:
            recommendations.append({
                'icon': '🌙',
                'title': 'Улучшите режим сна',
                'description': 'Ваше среднее качество сна ниже оптимального'
            })
        
        # Анализ длительности
        avg_duration = sum(day['duration'] for day in data.values()) / len(data)
        if avg_duration < 7:
            recommendations.append({
                'icon': '⏰',
                'title': 'Спите больше',
                'description': 'Рекомендуется 7-9 часов сна для взрослых'
            })
        
        # Анализ времени сна
        late_sleep_count = sum(1 for day in data.values() 
                             if int(day.get('sleep_time', '23:00').split(':')[0]) >= 24 or 
                                int(day.get('sleep_time', '23:00').split(':')[0]) <= 1)
        
        if late_sleep_count > len(data) * 0.5:
            recommendations.append({
                'icon': '🕐',
                'title': 'Ложитесь раньше',
                'description': 'Оптимальное время сна: 22:00-23:00'
            })
        
        return recommendations

# Создание экземпляра анализатора и веб-сервера
sleep_analyzer = SleepAnalyzer()
web_server = SleepWebServer(sleep_analyzer)

@app.route('/')
def dashboard():
    """Главная страница дашборда"""
    return render_template('dashboard.html')

@app.route('/api/sleep-data')
def get_sleep_data():
    """API для получения данных о сне"""
    data = web_server.load_sleep_data()
    
    # Преобразование данных для последних 7 дней
    last_7_days = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).strftime('%Y-%m-%d')
        if date in data:
            day_data = data[date]
            day_data['date'] = datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m')
            last_7_days.append(day_data)
    
    return jsonify({
        'last_7_days': last_7_days,
        'stats': web_server.get_stats_summary(data),
        'recommendations': web_server.get_recommendations(data)
    })

@app.route('/api/current-status')
def get_current_status():
    """API для получения текущего статуса"""
    current_hour = datetime.now().hour
    
    if 22 <= current_hour or current_hour <= 6:
        status = {
            'icon': '😴',
            'text': 'Время сна - минимальная активность',
            'activity_level': 'sleep'
        }
    elif 7 <= current_hour <= 9:
        status = {
            'icon': '🌅',
            'text': 'Утренняя активность',
            'activity_level': 'morning'
        }
    else:
        status = {
            'icon': '💻',
            'text': 'Активный период',
            'activity_level': 'active'
        }
    
    return jsonify(status)

@app.route('/api/add-sleep-record', methods=['POST'])
def add_sleep_record():
    """API для добавления записи о сне"""
    data = request.json
    
    sleep_data = web_server.load_sleep_data()
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    sleep_data[date] = {
        'quality': data.get('quality', 7.0),
        'duration': data.get('duration', 8.0),
        'sleep_time': data.get('sleep_time', '23:00'),
        'wake_time': data.get('wake_time', '07:00'),
        'notes': data.get('notes', '')
    }
    
    # Сохранение данных
    with open(web_server.sleep_data_file, 'w', encoding='utf-8') as f:
        json.dump(sleep_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'status': 'success'})

@app.route('/api/sleep-trends')
def get_sleep_trends():
    """API для получения трендов сна"""
    data = web_server.load_sleep_data()
    
    # Подготовка данных для графиков
    dates = sorted(data.keys())[-30:]  # последние 30 дней
    
    trends = {
        'dates': [datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m') for date in dates],
        'quality': [data[date]['quality'] for date in dates],
        'duration': [data[date]['duration'] for date in dates],
        'sleep_times': [data[date].get('sleep_time', '23:00') for date in dates],
        'wake_times': [data[date].get('wake_time', '07:00') for date in dates]
    }
    
    return jsonify(trends)

@app.route('/api/signal', methods=['POST'])
def mobile_signal():
    """Получение сигнала о начале сна или пробуждении с мобильного"""
    data = request.json
    action = data.get('action')
    if web_server.sleep_analyzer and action:
        web_server.sleep_analyzer.handle_external_signal(action)
    return jsonify({'status': 'ok'})

@app.route('/api/screen-time')
def screen_time():
    """Получение экранного времени за сегодня"""
    if not web_server.sleep_analyzer:
        return jsonify({'screen_time': 0})
    return jsonify({'screen_time': web_server.sleep_analyzer.get_today_screen_time()})

@app.route('/api/weather')
def weather():
    """Погода от сервиса open-meteo.com"""
    lat = request.args.get('lat', '55.75')
    lon = request.args.get('lon', '37.61')
    url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true'
    try:
        import requests
        resp = requests.get(url, timeout=5)
        weather = resp.json().get('current_weather', {})
    except Exception:
        weather = {}
    return jsonify(weather)

# HTML шаблон (сохранить как templates/dashboard.html)
dashboard_template = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sleep Analytics Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        /* Тот же CSS что и в предыдущем артефакте */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        /* ... остальные стили ... */
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💤 Sleep Analytics Dashboard</h1>
            <p>Персональная аналитика качества сна</p>
        </div>
        
        <div id="dashboard-content">
            <!-- Контент будет загружен через JavaScript -->
        </div>
    </div>
    
    <script>
        // Загрузка данных с сервера
        async function loadDashboardData() {
            try {
                const response = await fetch('/api/sleep-data');
                const data = await response.json();
                renderDashboard(data);
            } catch (error) {
                console.error('Ошибка загрузки данных:', error);
            }
        }
        
        function renderDashboard(data) {
            // Здесь код для отрисовки дашборда с данными с сервера
            console.log('Данные получены:', data);
        }
        
        // Загрузка при старте
        document.addEventListener('DOMContentLoaded', loadDashboardData);
    </script>
</body>
</html>
'''

def run_web_server(host='localhost', port=5000, debug=True):
    """Запуск веб-сервера"""
    
    # Создание папки templates если не существует
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Сохранение HTML шаблона
    with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(dashboard_template)

    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    # Запуск анализатора в отдельном потоке
    threading.Thread(target=sleep_analyzer.start_monitoring, daemon=True).start()
    run_web_server()

