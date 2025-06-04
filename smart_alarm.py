import time
import json
import threading
from datetime import datetime, timedelta
from pynput import mouse, keyboard
from pynput.mouse import Listener as MouseListener
from pynput.keyboard import Listener as KeyboardListener
import matplotlib.pyplot as plt
import numpy as np
from playsound import playsound
import schedule
from sklearn.linear_model import LinearRegression

class SleepAnalyzer:
    def __init__(self):
        self.activity_log = []
        self.last_activity = time.time()
        self.sleep_threshold = 1800  # 30 минут без активности = сон
        self.is_sleeping = False
        self.sleep_start = None
        self.sleep_end = None
        self.daily_stats = {}

        # Учёт экранного времени
        self.current_date = datetime.now().date()
        self.screen_time_today = 0
        self.last_check_time = time.time()

        # Модель для прогнозирования качества сна
        self.quality_model = None
        
        # Настройки будильника
        self.alarm_time = None
        self.smart_wake_window = 30  # минут до установленного времени

        # Обучение модели при инициализации (если есть данные)
        self.load_sleep_data()
        
    def on_mouse_move(self, x, y):
        self.register_activity('mouse_move')
        
    def on_mouse_click(self, x, y, button, pressed):
        if pressed:
            self.register_activity('mouse_click')
            
    def on_key_press(self, key):
        self.register_activity('key_press')
        
    def register_activity(self, activity_type):
        current_time = time.time()
        self.activity_log.append({
            'timestamp': current_time,
            'type': activity_type,
            'datetime': datetime.now().isoformat()
        })
        
        # Проверка на пробуждение
        if self.is_sleeping and current_time - self.last_activity < 60:
            self.wake_up_detected()
            
        self.last_activity = current_time
        
    def wake_up_detected(self):
        """Обнаружено пробуждение"""
        if self.is_sleeping:
            self.sleep_end = datetime.now()
            self.is_sleeping = False
            
            # Анализ качества сна
            sleep_quality = self.analyze_sleep_quality()
            self.save_sleep_data(sleep_quality)
            
            print(f"🌅 Доброе утро! Вы спали {self.get_sleep_duration()}")
            print(f"📊 Качество сна: {sleep_quality['quality']}/10")
            
    def check_sleep_status(self):
        """Проверка статуса сна"""
        current_time = time.time()
        time_since_activity = current_time - self.last_activity

        # учёт времени за компьютером
        delta = current_time - self.last_check_time
        self.last_check_time = current_time

        if datetime.now().date() != self.current_date:
            self.current_date = datetime.now().date()
            self.screen_time_today = 0

        if not self.is_sleeping:
            self.screen_time_today += delta
        
        if not self.is_sleeping and time_since_activity > self.sleep_threshold:
            # Пользователь заснул
            self.is_sleeping = True
            self.sleep_start = datetime.now() - timedelta(seconds=self.sleep_threshold)
            print(f"😴 Обнаружен сон в {self.sleep_start.strftime('%H:%M')}")
            
    def analyze_sleep_quality(self):
        """Анализ качества сна"""
        if not self.sleep_start or not self.sleep_end:
            return {'quality': 5, 'notes': 'Недостаточно данных'}
            
        sleep_duration = (self.sleep_end - self.sleep_start).total_seconds() / 3600
        
        # Простой алгоритм оценки качества
        quality_score = 5  # базовая оценка
        
        # Длительность сна
        if 7 <= sleep_duration <= 9:
            quality_score += 2
        elif 6 <= sleep_duration < 7 or 9 < sleep_duration <= 10:
            quality_score += 1
        elif sleep_duration < 5:
            quality_score -= 2
            
        # Время засыпания
        sleep_hour = self.sleep_start.hour
        if 22 <= sleep_hour <= 23:
            quality_score += 1
        elif sleep_hour >= 2:
            quality_score -= 1
            
        # Активность перед сном
        pre_sleep_activity = self.get_activity_before_sleep()
        if pre_sleep_activity < 10:  # мало активности перед сном = хорошо
            quality_score += 1
            
        return {
            'quality': max(1, min(10, quality_score)),
            'duration': sleep_duration,
            'sleep_time': self.sleep_start.strftime('%H:%M'),
            'wake_time': self.sleep_end.strftime('%H:%M'),
            'notes': self.generate_sleep_advice(quality_score, sleep_duration)
        }
        
    def get_activity_before_sleep(self):
        """Подсчет активности за час перед сном"""
        if not self.sleep_start:
            return 0
            
        hour_before = self.sleep_start - timedelta(hours=1)
        activity_count = 0
        
        for activity in reversed(self.activity_log):
            activity_time = datetime.fromisoformat(activity['datetime'])
            if activity_time > hour_before:
                activity_count += 1
            else:
                break
                
        return activity_count
        
    def generate_sleep_advice(self, score, duration):
        """Генерация советов по улучшению сна"""
        advice = []
        
        if duration < 6:
            advice.append("Спите больше - минимум 7-8 часов")
        elif duration > 10:
            advice.append("Возможно, вы переспали")
            
        if score < 5:
            advice.append("Попробуйте ложиться раньше")
            advice.append("Уменьшите активность перед сном")
            
        return "; ".join(advice) if advice else "Отличный сон!"
        
    def get_sleep_duration(self):
        """Получение длительности сна"""
        if self.sleep_start and self.sleep_end:
            duration = self.sleep_end - self.sleep_start
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            return f"{hours}ч {minutes}мин"
        return "Неизвестно"
        
    def save_sleep_data(self, quality_data):
        """Сохранение данных о сне"""
        date_key = datetime.now().strftime('%Y-%m-%d')
        quality_data['screen_time'] = self.get_today_screen_time()
        self.daily_stats[date_key] = quality_data
        
        # Сохранение в файл
        with open('sleep_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.daily_stats, f, ensure_ascii=False, indent=2)

        # Обучение модели после сохранения новых данных
        self.train_quality_model()
            
    def load_sleep_data(self):
        """Загрузка исторических данных"""
        try:
            with open('sleep_data.json', 'r', encoding='utf-8') as f:
                self.daily_stats = json.load(f)
        except FileNotFoundError:
            self.daily_stats = {}

        # Обучение модели после загрузки данных
        self.train_quality_model()
            
    def set_smart_alarm(self, target_time):
        """Установка умного будильника"""
        self.alarm_time = datetime.strptime(target_time, '%H:%M').time()
        print(f"⏰ Умный будильник установлен на {target_time}")
        
    def check_smart_alarm(self):
        """Проверка умного будильника"""
        if not self.alarm_time:
            return
            
        now = datetime.now().time()
        alarm_datetime = datetime.combine(datetime.now().date(), self.alarm_time)
        
        # Окно для умного пробуждения (30 минут до будильника)
        wake_window_start = alarm_datetime - timedelta(minutes=self.smart_wake_window)
        
        if wake_window_start.time() <= now <= self.alarm_time:
            # Проверяем активность - если есть, значит уже проснулся
            if time.time() - self.last_activity < 300:  # активность в последние 5 минут
                print("🎵 Умный будильник: Вы уже проснулись!")
                self.play_gentle_alarm()
                self.alarm_time = None  # сбросить будильник
                
        elif now >= self.alarm_time:
            print("⏰ Время будильника!")
            self.play_regular_alarm()
            self.alarm_time = None
            
    def play_gentle_alarm(self):
        """Мягкий звук будильника"""
        print("🔔 Играет мягкая мелодия...")
        # playsound('gentle_alarm.mp3')  # раскомментировать при наличии файла
        
    def play_regular_alarm(self):
        """Обычный звук будильника"""
        print("🚨 Играет будильник...")
        # playsound('alarm.mp3')  # раскомментировать при наличии файла
        
    def generate_sleep_report(self):
        """Генерация отчета о сне за неделю"""
        if len(self.daily_stats) < 2:
            return "Недостаточно данных для отчета"
            
        dates = list(self.daily_stats.keys())[-7:]  # последние 7 дней
        qualities = [self.daily_stats[date]['quality'] for date in dates]
        durations = [self.daily_stats[date]['duration'] for date in dates]
        
        avg_quality = sum(qualities) / len(qualities)
        avg_duration = sum(durations) / len(durations)
        
        report = f"""
📊 ОТЧЕТ О СНЕ (последние {len(dates)} дней)
═══════════════════════════════════════
📈 Среднее качество сна: {avg_quality:.1f}/10
⏰ Средняя длительность: {avg_duration:.1f}ч
🏆 Лучший день: {dates[qualities.index(max(qualities))]} ({max(qualities)}/10)
📉 Худший день: {dates[qualities.index(min(qualities))]} ({min(qualities)}/10)

💡 РЕКОМЕНДАЦИИ:
- Оптимальное время сна: 7-8 часов
- Ложитесь до 23:00
- Избегайте активности за час до сна
        """
        return report

    def handle_external_signal(self, action: str):
        """Обработка внешних сигналов от мобильного устройства"""
        if action == 'sleep_start':
            self.is_sleeping = True
            self.sleep_start = datetime.now()
            print(f"📱 Сигнал: пользователь лег спать в {self.sleep_start.strftime('%H:%M')}")
        elif action == 'wake_up':
            self.last_activity = time.time()
            if self.is_sleeping:
                self.sleep_end = datetime.now()
                self.is_sleeping = False
                self.wake_up_detected()
            print(f"📱 Сигнал: пользователь проснулся в {datetime.now().strftime('%H:%M')}")

    def get_today_screen_time(self) -> float:
        """Получить экранное время за сегодня в часах"""
        return round(self.screen_time_today / 3600, 2)

    def train_quality_model(self):
        """Обучение простой модели линейной регрессии"""
        features = []
        labels = []
        for day in self.daily_stats.values():
            try:
                duration = float(day.get('duration', 0))
                screen = float(day.get('screen_time', 0))
                hour = int(str(day.get('sleep_time', '23:00')).split(':')[0])
            except ValueError:
                continue
            features.append([duration, screen, hour])
            labels.append(day.get('quality', 5))

        if len(features) >= 2:
            self.quality_model = LinearRegression()
            self.quality_model.fit(features, labels)
        else:
            self.quality_model = None

    def predict_quality(self, duration: float, screen_time: float, sleep_time: str):
        """Прогноз качества сна на основе модели"""
        if not self.quality_model:
            self.train_quality_model()

        if not self.quality_model:
            return None

        hour = int(sleep_time.split(':')[0])
        pred = self.quality_model.predict([[duration, screen_time, hour]])
        return round(float(pred[0]), 1)
        
    def start_monitoring(self):
        """Запуск мониторинга"""
        print("🔍 Запуск мониторинга активности...")
        self.load_sleep_data()

        # напоминание о подготовке ко сну
        schedule.every().day.at("22:30").do(lambda: print("🔔 Пора готовиться ко сну!"))

        # Запуск слушателей
        mouse_listener = MouseListener(
            on_move=self.on_mouse_move,
            on_click=self.on_mouse_click
        )
        keyboard_listener = KeyboardListener(on_press=self.on_key_press)
        
        mouse_listener.start()
        keyboard_listener.start()
        
        # Основной цикл
        try:
            while True:
                self.check_sleep_status()
                self.check_smart_alarm()
                schedule.run_pending()
                time.sleep(60)  # проверка каждую минуту
                
        except KeyboardInterrupt:
            print("\n📊 Генерация финального отчета...")
            print(self.generate_sleep_report())
            mouse_listener.stop()
            keyboard_listener.stop()

# Пример использования
if __name__ == "__main__":
    analyzer = SleepAnalyzer()
    
    # Установка будильника
    analyzer.set_smart_alarm("07:30")
    
    print("💤 Умный будильник-аналитик запущен!")
    print("Нажмите Ctrl+C для остановки и просмотра отчета")
    
    analyzer.start_monitoring()