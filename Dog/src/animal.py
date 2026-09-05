"""
统一动物状态机 - 状态表驱动 + 非移动状态位置锁定 + 全配置化。
所有参数从 Config 读取，新增动物无需修改本文件。
"""
import os
import random
import math
from typing import Optional

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from .config import Config


class Animal:
    # 方向常量
    DIR_RIGHT = 0
    DIR_LEFT = 1
    DIR_DOWN = 2
    DIR_UP = 3

    # 状态常量
    STATE_WALKING = "walking"
    STATE_IDLE = "idle"
    STATE_EATING = "eating"
    STATE_SLEEPING = "sleeping"
    STATE_SCARED = "scared"

    # 非移动状态集合（位置锁定 + 方向锁定）
    NON_MOVING_STATES = {STATE_IDLE, STATE_EATING, STATE_SLEEPING}

    def __init__(self, cfg: Config, screen_width: int, screen_height: int, base_dir: str):
        self.cfg = cfg
        self.screen_w = screen_width
        self.screen_h = screen_height
        self.base_dir = base_dir

        # 初始位置
        if cfg.spawn_random:
            self.x = random.uniform(60, screen_width - 60)
            self.y = random.uniform(screen_height * 0.15, screen_height - 50)
        else:
            self.x = screen_width * cfg.spawn_x_ratio
            self.y = screen_height * cfg.spawn_y_ratio

        # 状态
        self.state = self.STATE_IDLE
        self.direction = self.DIR_DOWN
        self.state_timer = random.uniform(cfg.min_idle_time, cfg.max_idle_time)
        self.state_time = 0.0

        # 非移动状态位置锁定（进入时记录，期间不修改 x/y）
        self.locked_x = self.x
        self.locked_y = self.y

        # 行走目标
        self.walk_target_x = self.x
        self.walk_target_y = self.y

        # 方向切换冷却
        self.direction_cooldown = 0.0

        # 动画
        self.anim_time = 0.0
        self.state_time = 0.0
        self.anim_frame = 0

        # 受惊跳跃
        self.jump_velocity = 0.0
        self.jump_offset = 0.0
        self.is_jumping = False

        # 声音
        self.sound_player: Optional[QMediaPlayer] = None
        self.audio_output: Optional[QAudioOutput] = None
        self.sound_timer = random.uniform(cfg.sound_min_interval, cfg.sound_max_interval)
        self.sound_burst_remaining = 0
        self.sound_burst_timer = 0.0
        self.walk_sound_timer = 0.0
        if cfg.sound_enabled and cfg.sound_files:
            self._init_sound()

    # ==================== 声音 ====================
    def _init_sound(self):
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(self.cfg.sound_volume)
        self.sound_player = QMediaPlayer()
        self.sound_player.setAudioOutput(self.audio_output)

    def _play_sound(self) -> bool:
        """播放叫声，返回True=成功开始播放，False=被跳过（上一声还没播完）"""
        if not self.cfg.sound_enabled or not self.sound_player or not self.cfg.sound_files:
            return False
        # 正在播放则跳过，避免声音重叠（如牛叫第一声没播完就播第二声）
        if self.sound_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            return False
        sound_file = random.choice(self.cfg.sound_files)
        sound_path = os.path.join(self.base_dir, self.cfg.sound_dir, sound_file)
        if os.path.exists(sound_path):
            self.sound_player.setSource(QUrl.fromLocalFile(sound_path))
            self.sound_player.play()
            return True
        return False

    # ==================== 方向判断 ====================
    def _direction_from_vector(self, dx: float, dy: float) -> int:
        """用尾巴根部→头朝向向量与移动方向做点积，选最匹配的方向
        加入方向粘性：只有新方向点积比当前方向大0.3以上才切换，避免斜向移动频繁跳变（参考星露谷 _directionChangeTimer）"""
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 50.0:  # 位移过小，不改变方向（更严格，参考星露谷 MinDeltaForDirectionChange）
            return self.direction
        mvx, mvy = dx / dist, dy / dist

        # 计算当前方向的点积
        current_dot = -2.0
        if self.direction in self.cfg.heading_markers:
            hx, hy, tx, ty = self.cfg.heading_markers[self.direction]
            vx, vy = hx - tx, hy - ty
            vlen = (vx * vx + vy * vy) ** 0.5
            if vlen >= 0.001:
                current_dot = mvx * (vx / vlen) + mvy * (vy / vlen)

        # 找最佳方向
        best_dir = self.direction
        best_dot = -2.0
        for d, (hx, hy, tx, ty) in self.cfg.heading_markers.items():
            vx, vy = hx - tx, hy - ty
            vlen = (vx * vx + vy * vy) ** 0.5
            if vlen < 0.001:
                continue
            dot = mvx * (vx / vlen) + mvy * (vy / vlen)
            if dot > best_dot:
                best_dot = dot
                best_dir = d

        # 方向粘性：只有新方向点积比当前方向大0.5以上才切换（更严格，参考星露谷 MinDeltaForDirectionChange）
        if best_dir != self.direction and best_dot - current_dot < 0.5:
            return self.direction
        return best_dir

    def _update_walk_direction(self):
        # 非walking状态彻底禁止改方向（idle/eat/sleep/scared都不碰direction）
        if self.state != self.STATE_WALKING:
            return
        dx = self.walk_target_x - self.x
        dy = self.walk_target_y - self.y
        if self.direction_cooldown <= 0:
            new_dir = self._direction_from_vector(dx, dy)
            if new_dir != self.direction:
                self.direction = new_dir
                self.direction_cooldown = self.cfg.direction_cooldown

    # ==================== 状态转换 ====================
    def _enter_walking(self):
        self.state = self.STATE_WALKING
        self.state_timer = random.uniform(self.cfg.min_walk_time, self.cfg.max_walk_time)
        # 初始方向：四方向等概率（各25%），水平移动占比50%
        self.direction = random.choice([self.DIR_RIGHT, self.DIR_LEFT, self.DIR_DOWN, self.DIR_UP])
        self.direction_cooldown = 1.5  # 方向冷却，期间不能换向
        self.anim_time = 0.0
        self.state_time = 0.0

    def _enter_idle(self):
        self.state = self.STATE_IDLE
        self.state_timer = random.uniform(self.cfg.min_idle_time, self.cfg.max_idle_time)
        # 位置锁定
        self.locked_x = self.x
        self.locked_y = self.y
        self.anim_time = 0.0
        self.state_time = 0.0

    def _enter_eating(self):
        self.state = self.STATE_EATING
        self.state_timer = self.cfg.eat_duration
        # 位置锁定
        self.locked_x = self.x
        self.locked_y = self.y
        self.anim_time = 0.0
        self.state_time = 0.0

    def _enter_sleeping(self):
        self.state = self.STATE_SLEEPING
        self.state_timer = self.cfg.sleep_duration
        # 位置锁定
        self.locked_x = self.x
        self.locked_y = self.y
        self.anim_time = 0.0
        self.state_time = 0.0

    def _enter_scared(self):
        """点击受惊：跳跃，可打断任何非SCARED状态"""
        if self.state == self.STATE_SCARED:
            return
        self.state = self.STATE_SCARED
        self.is_jumping = True
        self.jump_velocity = self.cfg.jump_velocity
        self.jump_offset = 0.0
        self.anim_time = 0.0
        self.state_time = 0.0
        # 随机跳向一个方向
        self.direction = random.choice([self.DIR_RIGHT, self.DIR_LEFT, self.DIR_DOWN, self.DIR_UP])

    def _pick_walk_target(self):
        """选择行走目标点：确保距离≥150px，屏幕边缘时往中心拉，避免短距离频繁换向"""
        margin_x = 60
        margin_y_top = int(self.screen_h * 0.15)
        margin_y_bottom = 50
        min_dist = 150.0

        # 随机选点，满足最小距离
        best_x, best_y = self.x, self.y
        for _ in range(20):
            tx = random.uniform(margin_x, self.screen_w - margin_x)
            ty = random.uniform(margin_y_top, self.screen_h - margin_y_bottom)
            dx = tx - self.x
            dy = ty - self.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist >= min_dist:
                best_x, best_y = tx, ty
                break

        # 如果没找到（可能在屏幕角落），往屏幕中心方向拉，确保距离≥150px
        if best_x == self.x and best_y == self.y:
            center_x = self.screen_w / 2
            center_y = self.screen_h / 2
            dx = center_x - self.x
            dy = center_y - self.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > 1:
                best_x = self.x + (dx / dist) * min_dist
                best_y = self.y + (dy / dist) * min_dist
            else:
                best_x = self.x + min_dist
                best_y = self.y

        # clamp 到屏幕范围
        best_x = max(margin_x, min(self.screen_w - margin_x, best_x))
        best_y = max(margin_y_top, min(self.screen_h - margin_y_bottom, best_y))

        # 最终检查：如果 clamp 后距离还是太近，直接用屏幕中心
        dx = best_x - self.x
        dy = best_y - self.y
        if (dx * dx + dy * dy) ** 0.5 < 100.0:
            best_x = self.screen_w / 2
            best_y = self.screen_h / 2

        self.walk_target_x = best_x
        self.walk_target_y = best_y
        self._update_walk_direction()

    def _transition_from_idle(self):
        """从 idle 转出：按概率选择 walking/eating/sleeping"""
        r = random.random()
        if r < self.cfg.eat_chance:
            self._enter_eating()
        elif r < self.cfg.eat_chance + self.cfg.sleep_chance:
            self._enter_sleeping()
        else:
            self._enter_walking()

    # ==================== 主更新 ====================
    def update(self, dt: float):
        self.state_time += dt
        # 声音
        if self.cfg.sound_enabled:
            walk_sound_only = getattr(self.cfg, 'walk_sound_only', False)

            # 走路声音（仅WALKING状态）
            walk_sound_enabled = getattr(self.cfg, 'walk_sound_enabled', False)
            if walk_sound_enabled and self.state == self.STATE_WALKING:
                self.walk_sound_timer -= dt
                if self.walk_sound_timer <= 0:
                    self._play_sound()
                    self.walk_sound_timer = getattr(self.cfg, 'walk_sound_interval', 0.5)

            # 随机叫（walk_sound_only时跳过）
            if not walk_sound_only:
                burst_min = getattr(self.cfg, 'sound_burst_min', 1)
                burst_max = getattr(self.cfg, 'sound_burst_max', 1)
                burst_interval = getattr(self.cfg, 'sound_burst_interval', 0.5)

                if self.sound_burst_remaining > 0:
                    self.sound_burst_timer -= dt
                    if self.sound_burst_timer <= 0:
                        if self._play_sound():
                            self.sound_burst_remaining -= 1
                            self.sound_burst_timer = burst_interval
                            if self.sound_burst_remaining <= 0:
                                self.sound_timer = random.uniform(self.cfg.sound_min_interval, self.cfg.sound_max_interval)
                        else:
                            # 上一声还没播完，0.3秒后重试，确保最终叫满burst数
                            self.sound_burst_timer = 0.3
                else:
                    self.sound_timer -= dt
                    if self.sound_timer <= 0:
                        if self._play_sound():
                            total = random.randint(burst_min, burst_max)
                            self.sound_burst_remaining = total - 1
                            self.sound_burst_timer = burst_interval
                            if self.sound_burst_remaining <= 0:
                                self.sound_timer = random.uniform(self.cfg.sound_min_interval, self.cfg.sound_max_interval)
                        else:
                            # 上一声还没播完，0.3秒后重试
                            self.sound_timer = 0.3

        # 方向冷却
        if self.direction_cooldown > 0:
            self.direction_cooldown -= dt

        # 受惊跳跃物理（所有状态都受重力影响）
        # jump_offset 为正表示向上偏移，渲染时 draw_y = y - anchor - jump_offset
        if self.is_jumping:
            self.jump_velocity -= self.cfg.gravity * dt
            self.jump_offset += self.jump_velocity * dt
            if self.jump_offset <= 0:
                self.jump_offset = 0
                self.is_jumping = False
                self.jump_velocity = 0
                if self.state == self.STATE_SCARED:
                    self._enter_walking()

        # 状态计时
        self.state_timer -= dt

        # 动画帧更新
        action = self._current_action()
        fps = self.cfg.get_anim_fps(action)
        frame_count = self.cfg.get_frame_count(action)
        self.anim_time += dt
        self.anim_frame = int(self.anim_time * fps) % frame_count

        # 分发到各状态更新
        if self.state == self.STATE_WALKING:
            self._update_walking(dt)
        elif self.state == self.STATE_IDLE:
            self._update_idle(dt)
        elif self.state == self.STATE_EATING:
            self._update_eating(dt)
        elif self.state == self.STATE_SLEEPING:
            self._update_sleeping(dt)
        # STATE_SCARED 只做跳跃物理，不修改位置

    def _current_action(self) -> str:
        """当前状态对应的动作名称（用于帧映射和动画）"""
        if self.state == self.STATE_WALKING:
            return "walk"
        elif self.state == self.STATE_IDLE:
            return "idle"
        elif self.state == self.STATE_EATING:
            return "eat"
        elif self.state == self.STATE_SLEEPING:
            return "sleep"
        elif self.state == self.STATE_SCARED:
            return "walk"  # 受惊时用行走帧
        return "idle"

    # ==================== 各状态更新 ====================
    def _update_walking(self, dt: float):
        """星露谷式走路：朝一个方向一直走，碰边缘选新方向，低概率随机换向（带冷却，不直接掉头）"""
        cfg = self.cfg
        move_dist = cfg.walk_speed * dt
        margin_x = 40
        margin_y_top = int(self.screen_h * 0.1)
        margin_y_bottom = 40
        hit_edge = False

        # 方向冷却递减
        if self.direction_cooldown > 0:
            self.direction_cooldown -= dt

        # 每帧约0.3%概率随机换向（参考星露谷 chancePerUpdateToChangeDirection=0.007，桌宠降低频率）
        # 必须方向冷却结束，不直接掉头
        if self.direction_cooldown <= 0 and random.random() < 0.003:
            candidates = [d for d in range(4) if d != (self.direction + 2) % 4]
            if candidates:
                self.direction = random.choice(candidates)
                self.direction_cooldown = 2.0

        # 按方向移动
        if self.direction == self.DIR_RIGHT:
            self.x += move_dist
            if self.x > self.screen_w - margin_x:
                self.x = self.screen_w - margin_x
                hit_edge = True
        elif self.direction == self.DIR_LEFT:
            self.x -= move_dist
            if self.x < margin_x:
                self.x = margin_x
                hit_edge = True
        elif self.direction == self.DIR_DOWN:
            self.y += move_dist
            if self.y > self.screen_h - margin_y_bottom:
                self.y = self.screen_h - margin_y_bottom
                hit_edge = True
        elif self.direction == self.DIR_UP:
            self.y -= move_dist
            if self.y < margin_y_top:
                self.y = margin_y_top
                hit_edge = True

        # 碰边缘后选新方向：不直接反向
        if hit_edge:
            candidates = [d for d in range(4) if d != (self.direction + 2) % 4]
            if candidates:
                self.direction = random.choice(candidates)
                self.direction_cooldown = 1.5

        # 行走超时 → idle
        if self.state_timer <= 0:
            self._enter_idle()

    def _update_idle(self, dt: float):
        # 位置锁定：不修改 x/y
        self.x = self.locked_x
        self.y = self.locked_y
        # 方向锁定：不修改 direction
        # idle 超时 → 按概率转换
        if self.state_timer <= 0:
            self._transition_from_idle()

    def _update_eating(self, dt: float):
        # 位置锁定：不修改 x/y
        self.x = self.locked_x
        self.y = self.locked_y
        # 方向锁定：不修改 direction
        # eating 超时 → idle
        if self.state_timer <= 0:
            self._enter_idle()

    def _update_sleeping(self, dt: float):
        # 位置锁定：不修改 x/y
        self.x = self.locked_x
        self.y = self.locked_y
        # 方向锁定：不修改 direction
        # sleeping 超时 → idle
        if self.state_timer <= 0:
            self._enter_idle()

    # ==================== 对外接口 ====================
    def on_click(self):
        """鼠标点击：受惊跳跃，可打断任何非SCARED状态"""
        self._enter_scared()

    def get_bob_offset(self) -> float:
        """星露谷式呼吸/走路起伏偏移（正值=向上）"""
        if self.state == self.STATE_WALKING:
            # 走路起伏：奇数帧向上1.5px（模拟抬脚）
            return 1.5 if self.anim_frame % 2 == 1 else 0.0
        elif self.state in self.NON_MOVING_STATES:
            # 呼吸浮动：sin波，周期约3秒，幅度1.5px，只向上
            return abs(math.sin(self.state_time * math.pi / 1.5)) * 1.5
        return 0.0

    def get_render_params(self):
        """获取渲染参数：(row, col, x, y, jump_offset, use_anchor, flip_h, bob_offset)"""
        action = self._current_action()
        row = self.cfg.get_frame_row(action, self.direction)
        use_anchor = True  # 星露谷式：全状态锚点固定，走路也不做帧重心补偿，避免太空步
        flip_h = self.direction in getattr(self.cfg, 'flip_h_directions', set())
        return (row, self.anim_frame, self.x, self.y, self.jump_offset, use_anchor, flip_h, self.get_bob_offset())
