"""
统一渲染器 - 帧重心补偿 + 动作分级判定 + 锚点锁定。
所有阈值从 Config 读取，零硬编码。
"""
import os
from typing import Dict, Tuple

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap

from .config import Config


class Renderer:
    def __init__(self, cfg: Config, base_dir: str):
        self.cfg = cfg
        # 用基于 base_dir 的绝对路径加载 sprite（打包后从任意目录启动都能找到）
        sprite_path = os.path.join(base_dir, cfg.sprite_path)
        self.sprite = QPixmap(sprite_path)
        # 预计算每帧的重心（alpha>10 的像素加权中心）
        self.frame_centers: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._compute_frame_centers()

    def _compute_frame_centers(self):
        """用 constBits() 直接读 ARGB32 字节计算每帧重心（比逐像素 pixelColor 快且稳定）"""
        if self.sprite.isNull():
            return
        img = self.sprite.toImage()
        if img.format() != img.Format.Format_ARGB32:
            img = img.convertToFormat(img.Format.Format_ARGB32)
        ptr = img.constBits()
        ptr.setsize(img.sizeInBytes())
        bytes_per_line = img.bytesPerLine()
        fw, fh = self.cfg.frame_width, self.cfg.frame_height
        for row in range(self.cfg.sprite_rows):
            for col in range(self.cfg.sprite_cols):
                sx, sy = col * fw, row * fh
                sum_x, sum_y, count = 0.0, 0.0, 0
                for py in range(fh):
                    line_offset = (sy + py) * bytes_per_line
                    for px in range(fw):
                        # ARGB32: 字节序 B,G,R,A（小端），alpha 在第4字节
                        # QByteArray 索引在不同环境下可能返回 bytes 或 int，统一转 int
                        alpha_raw = ptr[line_offset + (sx + px) * 4 + 3]
                        alpha = alpha_raw[0] if isinstance(alpha_raw, (bytes, bytearray)) else alpha_raw
                        if alpha > 10:
                            sum_x += px
                            sum_y += py
                            count += 1
                if count > 0:
                    self.frame_centers[(row, col)] = (sum_x / count, sum_y / count)
                else:
                    self.frame_centers[(row, col)] = (fw / 2, fh / 2)

    def render(self, painter: QPainter, x: float, y: float,
               row: int, col: int, jump_offset: float = 0.0,
               use_anchor: bool = False, flip_h: bool = False,
               bob_offset: float = 0.0):
        if self.sprite is None or self.sprite.isNull():
            return

        fw = self.cfg.frame_width
        fh = self.cfg.frame_height
        scale = self.cfg.sprite_scale

        # 阴影（固定在脚下，不随帧偏移补偿）
        shadow_w = fw * scale * 0.7
        shadow_h = fh * scale * 0.15
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, self.cfg.shadow_alpha))
        painter.drawEllipse(QPointF(x, y + 2), shadow_w / 2, shadow_h / 2)

        draw_w = fw * scale
        draw_h = fh * scale

        # 计算当前帧相对于第0帧的重心偏移量（仅移动状态使用）
        base = self.frame_centers.get((row, 0))
        cur = self.frame_centers.get((row, col))

        if use_anchor:
            # 非移动状态：x/y 都用锚点固定（参考星露谷 AnimatedSprite 机制）
            draw_x = x - self.cfg.anchor_x * scale
            draw_y = y - self.cfg.anchor_y * scale - jump_offset - bob_offset
        else:
            # 移动状态：正常渲染，帧重心补偿（x方向对齐，y自由）
            ox = (base[0] - cur[0]) * scale if (base and cur) else 0.0
            draw_x = x - draw_w / 2 + ox
            draw_y = y - draw_h - jump_offset - bob_offset

        # 绘制当前帧（支持水平翻转，用于只有朝右帧的sprite如马）
        src_x = col * fw
        src_y = row * fh
        if flip_h:
            painter.save()
            painter.translate(draw_x + draw_w, draw_y)
            painter.scale(-1, 1)
            painter.drawPixmap(0, 0, int(draw_w), int(draw_h),
                               self.sprite, src_x, src_y, fw, fh)
            painter.restore()
        else:
            painter.drawPixmap(int(draw_x), int(draw_y), int(draw_w), int(draw_h),
                               self.sprite, src_x, src_y, fw, fh)
