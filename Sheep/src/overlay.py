"""
统一覆盖层 - 小窗口透明 + 渲染 + ESC退出 + 鼠标碰撞检测。
窗口只覆盖动物周围区域，大幅降低 GPU 占用。
"""
import sys

from PyQt6.QtCore import Qt, QTimer, QTime, QPoint
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from .animal import Animal
from .config import Config
from .renderer import Renderer


class Overlay(QWidget):
    def __init__(self, cfg: Config, base_dir: str):
        super().__init__()
        self.cfg = cfg
        self.base_dir = base_dir

        # 窗口设置：透明、无边框、置顶
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        screen = QApplication.primaryScreen().geometry()
        self.screen_w = screen.width()
        self.screen_h = screen.height()

        # 窗口大小：sprite尺寸*scale + 边距（跳跃空间+阴影）
        self.win_w = int(cfg.frame_width * cfg.sprite_scale + 120)
        self.win_h = int(cfg.frame_height * cfg.sprite_scale + 140)
        self.resize(self.win_w, self.win_h)

        # 动物和渲染器
        self.animal = Animal(cfg, self.screen_w, self.screen_h, base_dir)
        self.renderer = Renderer(cfg, base_dir)

        # ESC 长按退出（3秒）
        self.esc_held = False
        self.esc_hold_time = 0.0
        self.quit_hold_seconds = 3.0

        # 渲染定时器（60fps）
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.last_tick_time = QTime.currentTime()
        self.timer.start(16)

        # 初始窗口位置
        self._update_window_pos()

    def _update_window_pos(self):
        """窗口跟随动物移动，保持动物在窗口中心偏下位置"""
        x = int(self.animal.x - self.win_w / 2)
        y = int(self.animal.y - self.win_h + 60)
        # 限制在屏幕内
        x = max(0, min(self.screen_w - self.win_w, x))
        y = max(0, min(self.screen_h - self.win_h, y))
        self.move(x, y)

    def _screen_to_window(self, sx: float, sy: float) -> QPoint:
        """屏幕坐标转窗口坐标"""
        return QPoint(int(sx - self.x()), int(sy - self.y()))

    def _tick(self):
        # 用实际帧间隔计算 dt
        now = QTime.currentTime()
        dt = self.last_tick_time.msecsTo(now) / 1000.0
        self.last_tick_time = now
        if dt > 0.1:
            dt = 0.1
        if dt <= 0:
            dt = 0.001

        # ESC 长按退出（3秒，松开快速回退）
        if self.esc_held:
            self.esc_hold_time += dt
            if self.esc_hold_time >= self.quit_hold_seconds:
                QApplication.quit()
                return
        else:
            self.esc_hold_time = max(0.0, self.esc_hold_time - dt * 3.0)

        # 更新动物
        self.animal.update(dt)
        # 窗口跟随动物
        self._update_window_pos()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取渲染参数（屏幕坐标）
        row, col, x, y, jump_offset, use_anchor, flip_h, bob_offset = self.animal.get_render_params()

        # 转换为窗口坐标
        win_x = x - self.x()
        win_y = y - self.y()

        # 渲染动物
        self.renderer.render(painter, win_x, win_y, row, col, jump_offset, use_anchor, flip_h, bob_offset)

        # ESC 长按退出进度条
        if self.esc_hold_time > 0.01:
            progress = self.esc_hold_time / self.quit_hold_seconds
            bar_w = min(220, self.win_w - 40)
            bar_h = 8
            bar_x = (self.win_w - bar_w) // 2
            bar_y = self.win_h - 30

            # 背景
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)

            # 进度（从白到红）
            r = int(255 * progress)
            g = int(255 * (1 - progress))
            painter.setBrush(QColor(r, g, 60, 230))
            painter.drawRoundedRect(bar_x, bar_y, int(bar_w * progress), bar_h, 4, 4)

            # 文字
            painter.setPen(QColor(255, 255, 255, 230))
            font = QFont("Microsoft YaHei", 10)
            painter.setFont(font)
            text = f"长按ESC退出 {self.esc_hold_time:.1f}/{self.quit_hold_seconds:.0f}s"
            painter.drawText(0, bar_y - 18, self.win_w, 16, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.esc_held = True
            event.accept()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.esc_held = False
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 碰撞检测：只有点中动物本身才受惊
            click_x = event.position().x()
            click_y = event.position().y()
            row, col, ax, ay, jump_offset, use_anchor, flip_h, bob_offset = self.animal.get_render_params()
            # 动物在窗口中的位置
            win_ax = ax - self.x()
            win_ay = ay - self.y()
            # 动物碰撞区域（sprite大小*scale）
            sprite_w = self.cfg.frame_width * self.cfg.sprite_scale
            sprite_h = self.cfg.frame_height * self.cfg.sprite_scale
            # 动物的绘制区域（以锚点为基准）
            if use_anchor:
                draw_x = win_ax - self.cfg.anchor_x * self.cfg.sprite_scale
                draw_y = win_ay - self.cfg.anchor_y * self.cfg.sprite_scale - jump_offset
            else:
                draw_x = win_ax - sprite_w / 2
                draw_y = win_ay - sprite_h - jump_offset
            # 碰撞检测（放大一点范围方便点击）
            hit_margin = 10
            if (draw_x - hit_margin <= click_x <= draw_x + sprite_w + hit_margin and
                draw_y - hit_margin <= click_y <= draw_y + sprite_h + hit_margin):
                self.animal.on_click()
            event.accept()
