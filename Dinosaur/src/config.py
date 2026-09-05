"""
动物桌宠统一配置 - 恐龙
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Config:
    # ==================== Sprite 配置 ====================
    sprite_path: str = "assets/dinosaur.png"
    frame_width: int = 16
    frame_height: int = 16
    sprite_scale: float = 5.625
    sprite_cols: int = 4
    sprite_rows: int = 7

    # ==================== 帧行映射 ====================
    # direction: 0=右, 1=左, 2=下, 3=上
    # 标准行顺序：row0=正面(下), row1=朝右, row2=背面(上), row3=朝左, row4=吃, row5=睡
    # 羊式逻辑：只用朝右帧(row1)，左方向翻转
    frame_map: Dict[str, Dict[int, int]] = field(default_factory=lambda: {
        "walk":  {0: 1, 1: 0, 2: 2, 3: 3},
        "idle":  {0: 1, 1: 0, 2: 2, 3: 3},
        "eat":   {0: 6, 1: 6, 2: 6, 3: 6},
        "sleep": {0: 4, 1: 4, 2: 4, 3: 4},
    })

    frame_counts: Dict[str, int] = field(default_factory=lambda: {
        "walk": 4, "idle": 1, "eat": 4, "sleep": 1,
    })

    anim_fps: Dict[str, float] = field(default_factory=lambda: {
        "walk": 8.0, "idle": 1.0, "eat": 6.0, "sleep": 1.0,
    })

    # ==================== 朝向标记 ====================
    heading_markers: Dict[int, Tuple[int, int, int, int]] = field(default_factory=lambda: {
        0: (12, 8, 4, 8),
        1: (4, 8, 12, 8),
        2: (8, 12, 8, 4),
        3: (8, 4, 8, 12),
    })

    flip_h_directions: set = field(default_factory=lambda: set())

    # ==================== 锚点 ====================
    anchor_x: int = 8
    anchor_y: int = 15

    # ==================== 运动参数 ====================
    walk_speed: float = 70.0
    direction_cooldown: float = 2.0

    # ==================== 状态持续时间 ====================
    min_walk_time: float = 4.0
    max_walk_time: float = 10.0
    min_idle_time: float = 3.0
    max_idle_time: float = 6.0
    eat_duration: float = 30.0
    sleep_duration: float = 30.0

    eat_chance: float = 0.20
    sleep_chance: float = 0.05

    # ==================== 声音配置 ====================
    sound_enabled: bool = False
    sound_dir: str = "assets"
    sound_files: List[str] = field(default_factory=list)
    sound_min_interval: float = 15.0
    sound_max_interval: float = 30.0
    sound_burst_min: int = 1
    sound_burst_max: int = 2
    sound_burst_interval: float = 1.0
    sound_volume: float = 0.5

    # ==================== 交互配置 ====================
    quit_alpha_increment: float = 0.0033
    jump_velocity: float = 300.0
    gravity: float = 800.0

    # ==================== 显示配置 ====================
    shadow_alpha: int = 60

    # ==================== 初始位置 ====================
    spawn_random: bool = True
    spawn_x_ratio: float = 0.5
    spawn_y_ratio: float = 0.7

    def get_frame_row(self, action: str, direction: int) -> int:
        action_map = self.frame_map.get(action, self.frame_map["walk"])
        return action_map.get(direction, action_map[0])

    def get_frame_count(self, action: str) -> int:
        return self.frame_counts.get(action, 4)

    def get_anim_fps(self, action: str) -> float:
        return self.anim_fps.get(action, 8.0)

    def validate(self) -> List[str]:
        errors = []
        for action, dmap in self.frame_map.items():
            for d, row in dmap.items():
                if row < 0 or row >= self.sprite_rows:
                    errors.append(f"frame_map[{action}][{d}]={row} 超出范围 [0,{self.sprite_rows-1}]")
        for action, cnt in self.frame_counts.items():
            if cnt < 1 or cnt > self.sprite_cols:
                errors.append(f"frame_counts[{action}]={cnt} 超出范围 [1,{self.sprite_cols}]")
        for d, (hx, hy, tx, ty) in self.heading_markers.items():
            for name, val in [("head_x", hx), ("head_y", hy), ("tail_x", tx), ("tail_y", ty)]:
                if val < 0 or val >= max(self.frame_width, self.frame_height):
                    errors.append(f"heading_markers[{d}].{name}={val} 超出帧范围")
        if self.eat_chance + self.sleep_chance > 1.0:
            errors.append(f"eat_chance({self.eat_chance}) + sleep_chance({self.sleep_chance}) > 1.0")
        return errors
