# Pixel Pet - 像素风桌面宠物

星露谷风格的多动物桌面宠物。10个动物独立可运行，透明窗口，60fps帧动画，参考星露谷反编译源码的动物行为逻辑。

> 非官方粉丝项目。Stardew Valley 及所有相关素材版权归 ConcernedApe 所有。本项目仅用于学习交流。

## 特性

- 10个动物：鸡、鸭、猫、狗、猪、牛、羊、马、鸵鸟、恐龙
- 透明无边框窗口，始终置顶
- 60fps 帧动画渲染，呼吸浮动，走路起伏
- 星露谷式行为逻辑：随机方向行走、碰边缘换向、低概率随机转向
- 状态机：行走 / 待机 / 吃东西 / 睡觉 / 受惊跳跃
- 鼠标点击交互（点中动物会受惊跳起来）
- 真实动物叫声音频（防重叠播放）
- ESC 长按 3 秒退出
- 每个动物独立文件夹，下载即用

## 快速开始

### 方式一：直接运行（推荐）

每个动物文件夹里都有打包好的 exe，双击即可运行：

```
Chicken/chicken.exe
Cat/cat.exe
Dog/dog.exe
Pig/pig.exe
Cow/cow.exe
Sheep/sheep.exe
Horse/horse.exe
Duck/duck.exe
Ostrich/ostrich.exe
Dinosaur/dinosaur.exe
```

### 方式二：源码运行

```bash
pip install -r requirements.txt
cd Pig
python main.py
```

### 退出

长按 `ESC` 键 3 秒退出（屏幕底部会显示进度条）。

## 动物大小比例

以猪（64px）为基准 1.0：

| 动物 | 显示尺寸 | 相对比例 |
|---|---|---|
| 猫 | 38px | 0.6 |
| 鸡/鸭 | 42px | 0.65 |
| 狗 | 54px | 0.85 |
| 猪/羊 | 64px | 1.0 |
| 牛/马/鸵鸟/恐龙 | 90px | 1.4 |

恐龙特殊：移速快、迈腿慢，营造压迫感。

---

## 代码架构讲解（以 Pig 为代表）

每个动物文件夹结构完全一致，以 `Pig/` 为例：

```
Pig/
├── main.py              # 入口（48行）
├── pig.exe              # 打包好的可执行文件
├── assets/
│   ├── pig.png          # sprite 精灵图（32x32帧，5行4列）
│   └── sounds/          # 叫声音频
└── src/
    ├── __init__.py
    ├── config.py        # 动物独有配置（115行）
    ├── animal.py        # 状态机+行为逻辑（461行）
    ├── renderer.py      # 帧动画渲染器（102行）
    └── overlay.py       # 透明窗口+交互（172行）
```

### main.py - 入口

做三件事：高DPI支持、配置校验、启动窗口。

```python
app = QApplication(sys.argv)
cfg = Config()           # 加载猪的配置
errors = cfg.validate()  # 校验配置是否合法（帧索引越界等）
overlay = Overlay(cfg, base_dir)
overlay.show()
```

### config.py - 配置驱动

所有动物差异都在这个文件里，新增动物只需改配置，不用动逻辑。

核心配置项：
- `sprite_path / frame_width / frame_height / sprite_scale`：精灵图和缩放
- `frame_map`：状态+方向 → sprite行号的映射（核心！见下方）
- `frame_counts / anim_fps`：每动作帧数和动画速度
- `anchor_x / anchor_y`：锚点（动物脚底位置，固定不飘）
- `walk_speed / direction_cooldown`：移速和换向冷却
- `sound_files / sound_min_interval`：音频和叫声间隔

**frame_map 是整个项目最关键的配置**，决定了动物朝哪个方向用哪一帧：

```python
frame_map = {
    "walk":  {0: 1, 1: 1, 2: 0, 3: 2},  # 方向0(右)→第1行, 方向1(左)→第1行(翻转), 方向2(下)→第0行, 方向3(上)→第2行
    "idle":  {0: 1, 1: 1, 2: 0, 3: 2},  # 待机复用行走第0帧
    "eat":   {0: 4, 1: 4, 2: 4, 3: 4},  # 吃东西→第4行
    "sleep": {0: 3, 1: 3, 2: 3, 3: 3},  # 睡觉→第3行
}
flip_h_directions = {1}  # 左方向用朝右帧水平翻转
```

方向常量：`0=右, 1=左, 2=下(正面), 3=上(背面)`

星露谷标准 sprite 行顺序：`row0=正面, row1=朝右, row2=背面, row3=朝左, row4=吃, row5=睡`

### animal.py - 状态机+行为逻辑

核心是一个状态机，5个状态：`walking / idle / eating / sleeping / scared`

**关键设计：**

1. **非移动状态位置锁定**：idle/eat/sleep 时记录 `locked_x/locked_y`，期间不修改坐标，避免动物飘走

2. **星露谷式走路**（参考 FarmAnimal.cs 反编译源码）：
   - 不设目标点，朝一个方向一直走
   - 每帧 0.3% 概率随机换向（带 2 秒冷却，不直接掉头）
   - 碰边缘选新方向（排除反向）
   - 方向权重：上下各 1/3，左右各 1/6

3. **方向粘性**：用头尾向量与移动方向做点积，只有新方向点积比当前大 0.5 以上才切换，避免斜向移动频繁跳变

4. **声音防重叠**：`_play_sound()` 检查 `QMediaPlayer.PlaybackState.PlayingState`，上一声没播完则跳过，0.3秒后重试

5. **受惊跳跃**：鼠标点击触发，物理模拟（初速度+重力），落地后回到 walking

6. **呼吸浮动**：非移动状态用 `sin` 波做 1.5px 幅度的呼吸，走路用奇数帧上抬 1.5px 模拟抬脚

### renderer.py - 帧动画渲染器

**关键技术：**

1. **帧重心预计算**：启动时用 `constBits()` 直接读 ARGB32 字节，计算每帧的 alpha 加权重心，比逐像素 `pixelColor` 快且稳定

2. **锚点固定**：`use_anchor=True` 时，所有状态用 `anchor_x/anchor_y` 固定绘制位置，不做帧重心补偿——这是解决"太空步"（脚在动但位置不移动）的关键

3. **水平翻转**：只有朝右帧的 sprite（如马），左方向用 `painter.scale(-1, 1)` 水平翻转

4. **阴影**：固定在动物脚下的椭圆，不随帧偏移，增强空间感

### overlay.py - 透明窗口+交互

**关键技术：**

1. **透明窗口**：`FramelessWindowHint + WindowStaysOnTopHint + WA_TranslucentBackground`，无边框置顶透明

2. **小窗口策略**：窗口只覆盖动物周围区域（sprite尺寸+120px边距），而不是全屏，大幅降低 GPU 占用。窗口跟随动物移动

3. **60fps 定时器**：`QTimer.start(16)`，用实际帧间隔计算 `dt`，避免帧率波动导致移速不稳

4. **ESC 长按退出**：按住 ESC 累计时间，3 秒触发退出；松开快速回退（3倍速衰减），底部显示白→红渐变进度条

5. **鼠标碰撞检测**：点击时计算动物在窗口中的绘制区域（锚点基准），放大 10px 边距方便点击，命中则触发受惊跳跃

---

## 新增动物教程

1. 复制任意动物文件夹，重命名（如 `Rabbit/`）
2. 替换 `assets/` 里的 sprite 图和音频
3. 修改 `src/config.py`：
   - `sprite_path` 指向新图
   - `frame_width / frame_height` 设为帧尺寸
   - `sprite_scale` 调整显示大小
   - `frame_map` 按 sprite 实际行顺序配置
   - `sound_files` 配置音频
4. 运行 `python main.py` 测试
5. 打包：`pyinstaller --onefile --windowed --name rabbit --add-data "assets;assets" main.py`

## 工具

### sprite_rearranger.py

Sprite 行重排工具。星露谷不同动物的 sprite 行顺序不统一，这个工具按映射表重排为标准顺序（row0=正面, row1=朝右, row2=背面, row3=朝左, row4=吃, row5=睡），自动备份原始文件。

```bash
python tools/sprite_rearranger.py
```

## 技术栈

- Python 3.10+
- PyQt6（GUI + 音频 + 帧动画）
- Pillow（sprite 处理工具）
- PyInstaller（打包 exe）

## 许可证

代码部分 MIT。精灵图和音频版权归 ConcernedApe / Stardew Valley 所有，仅用于学习交流，请勿商用。
