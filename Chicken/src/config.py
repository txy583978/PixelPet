"""
动物桌宠统一配置 - 所有参数集中在此，核心代码零硬编码。
新增动物 = 复制本文件 + 修改动物特定参数 + 准备 assets/。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Config:
    # ==================== Sprite 配置 ====================
    sprite_path: str = "assets/chicken.png"
    frame_width: int = 16
    frame_height: int = 16
    sprite_scale: float = 2.6       # 显示放大倍数
    sprite_cols: int = 4            # 帧列数（动画帧数）
    sprite_rows: int = 7            # 帧行数（动作数）

    # ==================== 帧行映射（标准行顺序） ====================
    # row0=正面(下), row1=朝右, row2=背面(上), row3=朝左, row4=吃, row5=睡, row6=下蛋
    # 羊式逻辑：只用朝右帧(row1)，左方向翻转
    frame_map: Dict[str, Dict[int, int]] = field(default_factory=lambda: {
        "walk":  {0: 1, 1: 2, 2: 3, 3: 0},
        "idle":  {0: 1, 1: 2, 2: 3, 3: 0},
        "eat":   {0: 6, 1: 6, 2: 6, 3: 6},
        "sleep": {0: 4, 1: 4, 2: 4, 3: 4},
    })

    # 每个动作的动画帧数（<= sprite_cols）
    frame_counts: Dict[str, int] = field(default_factory=lambda: {
        "walk": 4, "idle": 1, "eat": 4, "sleep": 1,
    })

    # 动画帧率（帧/秒）
    anim_fps: Dict[str, float] = field(default_factory=lambda: {
        "walk": 8.0, "idle": 1.0, "eat": 6.0, "sleep": 1.0,
    })

    # ==================== 朝向标记 ====================
    # direction -> (head_x, head_y, tail_root_x, tail_root_y)
    # 尾巴标记在尾巴与屁股连接处（尾巴根部），不是尾巴尖
    # 尾巴根部 -> 头 的向量 = 动物朝向
    heading_markers: Dict[int, Tuple[int, int, int, int]] = field(default_factory=lambda: {
        0: (12, 8, 4, 6),    # 右
        1: (4, 8, 12, 6),    # 左
        2: (8, 12, 8, 4),    # 下
        3: (8, 4, 8, 12),    # 上
    })

    # 需要水平翻转的方向（用于只有朝右帧的sprite，如马）
    flip_h_directions: set = field(default_factory=lambda: set())

    # ==================== 锚点 ====================
    # 两只脚之间的帧内坐标，非移动状态时锚点对齐屏幕位置
    anchor_x: int = 8
    anchor_y: int = 15

    # ==================== 运动参数 ====================
    walk_speed: float = 45.0
    direction_cooldown: float = 2.0   # 方向切换冷却（秒），防止斜向移动乱跳（参考星露谷 _directionChangeTimer）

    # ==================== 状态持续时间（秒） ====================
    min_walk_time: float = 4.0
    max_walk_time: float = 10.0
    min_idle_time: float = 3.0
    max_idle_time: float = 6.0
    eat_duration: float = 30.0
    sleep_duration: float = 30.0

    # 从 idle 转出时各状态的概率（合计应 <= 1.0，剩余概率回 walk）
    eat_chance: float = 0.20
    sleep_chance: float = 0.05

    # ==================== 声音配置 ====================
    sound_enabled: bool = True
    sound_dir: str = "assets/sounds"
    sound_files: List[str] = field(default_factory=lambda: ["cluck.wav", "cluck2.wav", "cluck3.wav"])
    sound_min_interval: float = 4.8
    sound_max_interval: float = 9.0
    sound_burst_min: int = 3
    sound_burst_max: int = 4
    sound_burst_interval: float = 0.6
    sound_volume: float = 0.5

    # ==================== 交互配置 ====================
    quit_alpha_increment: float = 0.0033  # ESC 长按退出速度（0.0033 ≈ 5秒）
    jump_velocity: float = 300.0           # 点击受惊跳跃初速度
    gravity: float = 800.0                  # 重力加速度

    # ==================== 显示配置 ====================
    shadow_alpha: int = 60

    # ==================== 初始位置 ====================
    spawn_random: bool = True               # True=随机位置，False=固定位置
    spawn_x_ratio: float = 0.5              # spawn_random=False 时的固定 x 比例
    spawn_y_ratio: float = 0.7              # spawn_random=False 时的固定 y 比例

    def get_frame_row(self, action: str, direction: int) -> int:
        """获取指定动作+方向的帧行（自动处理复用）"""
        action_map = self.frame_map.get(action, self.frame_map["walk"])
        return action_map.get(direction, action_map[0])

    def get_frame_count(self, action: str) -> int:
        """获取指定动作的动画帧数"""
        return self.frame_counts.get(action, 4)

    def get_anim_fps(self, action: str) -> float:
        """获取指定动作的动画帧率"""
        return self.anim_fps.get(action, 8.0)

    def validate(self) -> List[str]:
        """配置校验，返回错误列表（空列表=通过）"""
        errors = []
        # 帧行映射校验
        for action, dmap in self.frame_map.items():
            for d, row in dmap.items():
                if row < 0 or row >= self.sprite_rows:
                    errors.append(f"frame_map[{action}][{d}]={row} 超出范围 [0,{self.sprite_rows-1}]")
        # 帧数校验
        for action, cnt in self.frame_counts.items():
            if cnt < 1 or cnt > self.sprite_cols:
                errors.append(f"frame_counts[{action}]={cnt} 超出范围 [1,{self.sprite_cols}]")
        # 朝向标记校验
        for d, (hx, hy, tx, ty) in self.heading_markers.items():
            for name, val in [("head_x", hx), ("head_y", hy), ("tail_x", tx), ("tail_y", ty)]:
                if val < 0 or val >= max(self.frame_width, self.frame_height):
                    errors.append(f"heading_markers[{d}].{name}={val} 超出帧范围")
        # 概率校验
        if self.eat_chance + self.sleep_chance > 1.0:
            errors.append(f"eat_chance({self.eat_chance}) + sleep_chance({self.sleep_chance}) > 1.0")
        return errors
