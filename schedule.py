#!/usr/bin/env python3
"""
Распорядок дня — ретро-терминальное приложение в стиле 80-х

Управление:
  В режиме редактирования:
    - Печатайте название задачи
    - Tab: переключение между названием и слотами
    - Enter: новая задача
    - Стрелки: перемещение по слотам
    - Space: поставить/убрать рабочий слот
    - R: поставить/убрать слот отдыха
    - F5: запустить таймер

  В режиме работы:
    - Q: выход
"""

import curses
import time
import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional

# Символы для отображения слотов
EMPTY = '▢'      # пустой (будущее)
CURRENT = '▣'    # текущий слот
FILLED = '■'     # прошедший
REST = '▨'       # отдых

# Временные настройки
START_HOUR = 8   # 08:00
END_HOUR = 21    # 21:00
TOTAL_SLOTS = (END_HOUR - START_HOUR) * 2  # 26 получасовых слотов

# Размеры интерфейса
LEFT_PANEL_WIDTH = 22
MAX_TASKS = 5

@dataclass
class Task:
    name: str = ""
    slots: List[int] = field(default_factory=list)      # индексы рабочих слотов
    rest_slots: List[int] = field(default_factory=list)  # слоты отдыха

@dataclass
class AppState:
    tasks: List[Task] = field(default_factory=list)
    cursor_row: int = 0       # текущая строка (задача)
    cursor_col: int = 0       # текущий слот (0 до TOTAL_SLOTS-1)
    mode: str = 'edit'        # 'edit' или 'run'
    edit_focus: str = 'name'  # 'name' или 'slots'

    def __post_init__(self):
        # Инициализируем пустые задачи
        if not self.tasks:
            self.tasks = [Task() for _ in range(MAX_TASKS)]

def get_current_slot() -> int:
    """Возвращает индекс текущего получасового слота (0-25) или -1 если вне диапазона"""
    now = datetime.now()
    if now.hour < START_HOUR or now.hour >= END_HOUR:
        return -1
    minutes_from_start = (now.hour - START_HOUR) * 60 + now.minute
    return minutes_from_start // 30

def get_elapsed_time() -> tuple:
    """Возвращает (часы, получасы) с начала дня"""
    now = datetime.now()
    if now.hour < START_HOUR:
        return (0, 0)
    minutes_from_start = (now.hour - START_HOUR) * 60 + now.minute
    hours = minutes_from_start // 60
    half_hours = (minutes_from_start % 60) // 30
    return (hours, half_hours * 3)  # 0 или 3 (отображается как X:0 или X:3)

def beep():
    """Звуковой сигнал"""
    sys.stdout.write('\a')
    sys.stdout.flush()

def format_slot_bar(slots: List[int], rest_slots: List[int], current_slot: int, is_running: bool) -> str:
    """Форматирует строку слотов для отображения"""
    result = ""
    for i in range(TOTAL_SLOTS):
        if i in rest_slots:
            char = REST
        elif i in slots:
            if is_running:
                if i < current_slot:
                    char = FILLED
                elif i == current_slot:
                    char = CURRENT
                else:
                    char = EMPTY
            else:
                char = EMPTY
        else:
            char = " "

        result += char * 2  # Каждый слот = 2 символа

        # Точка-разделитель после каждого слота (кроме последнего)
        if i < TOTAL_SLOTS - 1:
            result += "."

    return result

def format_header_bar(current_slot: int, is_running: bool) -> str:
    """Форматирует верхнюю шкалу времени"""
    result = ""
    for i in range(TOTAL_SLOTS):
        if is_running:
            if i < current_slot:
                char = FILLED
            elif i == current_slot:
                char = CURRENT
            else:
                char = EMPTY
        else:
            char = EMPTY

        result += char * 2

        if i < TOTAL_SLOTS - 1:
            result += "."

    return result

def draw_interface(stdscr, state: AppState):
    """Отрисовка всего интерфейса"""
    stdscr.clear()

    is_running = state.mode == 'run'
    current_slot = get_current_slot() if is_running else -1
    elapsed = get_elapsed_time()

    # === Строка 0: Заголовок ===
    if is_running:
        time_display = f"[{elapsed[0]:02d}:{elapsed[1]}]"
    else:
        time_display = "[tt:m]"

    left_header = f"{START_HOUR:02d}:00.{END_HOUR}:00   {time_display}  "
    separator = "|"
    right_header = "  .9a      .12      .3p      .6p      .9p"

    try:
        stdscr.addstr(0, 0, left_header)
        stdscr.addstr(0, len(left_header), separator, curses.A_DIM)
        stdscr.addstr(0, len(left_header) + 1, right_header)
    except curses.error:
        pass

    # === Строка 1: Легенда + шкала времени ===
    legend = f"{EMPTY}.{CURRENT}.{FILLED}.{REST}               "
    header_bar = format_header_bar(current_slot, is_running)

    try:
        stdscr.addstr(1, 0, legend)
        stdscr.addstr(1, len(legend), separator, curses.A_DIM)
        stdscr.addstr(1, len(legend) + 1, header_bar)
    except curses.error:
        pass

    # === Строки 2-6: Задачи ===
    for row_idx in range(MAX_TASKS):
        task = state.tasks[row_idx]

        # Левая часть — название задачи (с квадратиками перед ним)
        total_task_slots = len(task.slots) + len(task.rest_slots)
        if total_task_slots > 0:
            prefix = EMPTY * total_task_slots + " "
        else:
            prefix = ""

        name_display = prefix + task.name
        name_display = name_display[:LEFT_PANEL_WIDTH-1].ljust(LEFT_PANEL_WIDTH-1)

        try:
            # Подсветка текущей строки в режиме редактирования
            if state.mode == 'edit' and row_idx == state.cursor_row:
                stdscr.addstr(2 + row_idx, 0, name_display, curses.A_REVERSE if state.edit_focus == 'name' else curses.A_NORMAL)
            else:
                stdscr.addstr(2 + row_idx, 0, name_display)

            stdscr.addstr(2 + row_idx, LEFT_PANEL_WIDTH - 1, separator, curses.A_DIM)
        except curses.error:
            pass

        # Правая часть — слоты
        slot_bar = format_slot_bar(task.slots, task.rest_slots, current_slot, is_running)

        try:
            stdscr.addstr(2 + row_idx, LEFT_PANEL_WIDTH, slot_bar)
        except curses.error:
            pass

        # Курсор на слотах
        if state.mode == 'edit' and row_idx == state.cursor_row and state.edit_focus == 'slots':
            # Позиция курсора: каждый слот = 2 символа + 1 точка
            cursor_x = LEFT_PANEL_WIDTH + state.cursor_col * 3
            try:
                stdscr.addstr(2 + row_idx, cursor_x, "▼▼", curses.A_BLINK)
            except curses.error:
                pass

    # === Строка 7: Пустая разделительная ===

    # === Строка 8: Статус/помощь ===
    if state.mode == 'edit':
        if state.edit_focus == 'name':
            status = "NAME: Введите название | Tab→слоты | Enter→след.задача | F5→СТАРТ"
        else:
            status = "SLOTS: ←→↑↓ Space=слот R=отдых | Tab→имя | F5→СТАРТ"
    else:
        now = datetime.now()
        status = f"RUN {now.strftime('%H:%M:%S')} | Q=выход"

    try:
        stdscr.addstr(8, 0, status)
    except curses.error:
        pass

    # Позиционируем системный курсор
    if state.mode == 'edit' and state.edit_focus == 'name':
        task = state.tasks[state.cursor_row]
        total_task_slots = len(task.slots) + len(task.rest_slots)
        prefix_len = total_task_slots + 1 if total_task_slots > 0 else 0
        cursor_x = min(prefix_len + len(task.name), LEFT_PANEL_WIDTH - 2)
        try:
            stdscr.move(2 + state.cursor_row, cursor_x)
        except curses.error:
            pass

def handle_edit_input(state: AppState, key: int) -> bool:
    """Обработка ввода в режиме редактирования. Возвращает True если нужно запустить."""

    # F5 — запуск
    if key == curses.KEY_F5:
        return True

    # Tab — переключение фокуса
    if key == ord('\t') or key == 9:
        state.edit_focus = 'slots' if state.edit_focus == 'name' else 'name'
        return False

    # Стрелки вверх/вниз — переключение между задачами
    if key == curses.KEY_UP:
        state.cursor_row = max(0, state.cursor_row - 1)
        return False

    if key == curses.KEY_DOWN:
        state.cursor_row = min(MAX_TASKS - 1, state.cursor_row + 1)
        return False

    if state.edit_focus == 'name':
        # Ввод названия задачи
        task = state.tasks[state.cursor_row]

        if key == ord('\n') or key == curses.KEY_ENTER or key == 10 or key == 13:
            # Enter — перейти к следующей задаче
            state.cursor_row = min(MAX_TASKS - 1, state.cursor_row + 1)
            return False

        if key == curses.KEY_BACKSPACE or key == 127 or key == 8:
            # Backspace
            task.name = task.name[:-1]
            return False

        if 32 <= key <= 126:
            # Печатаемый символ
            if len(task.name) < 15:
                task.name += chr(key)
            return False

    else:  # edit_focus == 'slots'
        task = state.tasks[state.cursor_row]

        if key == curses.KEY_LEFT:
            state.cursor_col = max(0, state.cursor_col - 1)
            return False

        if key == curses.KEY_RIGHT:
            state.cursor_col = min(TOTAL_SLOTS - 1, state.cursor_col + 1)
            return False

        if key == ord(' '):
            # Пробел — переключить рабочий слот
            col = state.cursor_col
            if col in task.slots:
                task.slots.remove(col)
            elif col in task.rest_slots:
                task.rest_slots.remove(col)
                task.slots.append(col)
            else:
                task.slots.append(col)
            return False

        if key == ord('r') or key == ord('R'):
            # R — переключить слот отдыха
            col = state.cursor_col
            if col in task.rest_slots:
                task.rest_slots.remove(col)
            elif col in task.slots:
                task.slots.remove(col)
                task.rest_slots.append(col)
            else:
                task.rest_slots.append(col)
            return False

    return False

def main(stdscr):
    # Настройка curses
    curses.curs_set(1)
    stdscr.nodelay(False)
    stdscr.timeout(2000)  # Обновление каждые 2 секунды

    try:
        curses.start_color()
        curses.use_default_colors()
    except:
        pass

    state = AppState()
    last_minute = -1
    last_beep_slot = -1

    while True:
        draw_interface(stdscr, state)
        stdscr.refresh()

        # В режиме работы — проверяем звук
        if state.mode == 'run':
            now = datetime.now()
            current_slot = get_current_slot()

            # Писк каждую минуту
            if now.minute != last_minute:
                last_minute = now.minute
                beep()

            # Проверка окончания дня
            if current_slot == -1 or current_slot >= TOTAL_SLOTS:
                # Финальные звуки
                for _ in range(5):
                    beep()
                    time.sleep(0.3)
                break

        # Ввод
        try:
            key = stdscr.getch()
        except:
            key = -1

        if key == -1:
            continue  # Таймаут

        if state.mode == 'edit':
            if handle_edit_input(state, key):
                state.mode = 'run'
                last_minute = -1
        else:
            if key == ord('q') or key == ord('Q'):
                break

if __name__ == '__main__':
    # Проверяем, что запущено в терминале
    if not sys.stdin.isatty():
        print("Это приложение требует интерактивный терминал!")
        sys.exit(1)

    try:
        curses.wrapper(main)
        print("\nРабота завершена!")
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
    except Exception as e:
        print(f"\nОшибка: {e}")
