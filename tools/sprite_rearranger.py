"""
Sprite 行重排工具
将星露谷动物 sprite 的行顺序统一为标准格式：
  row0=正面(朝下), row1=朝右, row2=背面(朝上), row3=朝左, row4=吃, row5=睡, row6+=其他

用法：
  python sprite_rearranger.py            # 重排所有配置了映射的动物
  python sprite_rearranger.py Pig        # 只重排指定动物

映射表格式：{目标行: 原始行}，例如 {0:2, 1:1, 2:0, 3:3} 表示
  新row0 = 原row2, 新row1 = 原row1, 新row2 = 原row0, 新row3 = 原row3

自动备份原始文件为 .png.bak，已有备份的跳过（防止重复重排）。
"""
import os
import sys
import shutil
from PIL import Image

# 项目根目录（tools/ 的上一级）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 动物配置：(文件夹名, sprite相对路径, 帧宽, 帧高, 映射表)
# 映射表为空 {} 表示已符合标准，跳过
ANIMALS = [
    ("Chicken", "assets/chicken.png", 16, 16, {0: 3, 1: 1, 2: 0, 3: 2, 4: 4, 5: 5, 6: 6}),
    ("Duck",    "assets/duck.png",    16, 16, {0: 2, 1: 3, 2: 1, 3: 0, 4: 4, 5: 5}),
    ("Cat",     "assets/cat.png",      32, 32, {1: 1, 3: 3, 4: 0, 5: 2, 6: 4, 7: 5}),
    ("Dog",     "assets/dog.png",      32, 32, {1: 1, 3: 3, 4: 0, 5: 2, 6: 4, 7: 5}),
    ("Ostrich", "assets/ostrich.png",  32, 32, {0: 2, 1: 1, 2: 3, 3: 0, 4: 4}),
    ("Dinosaur","assets/dinosaur.png", 16, 16, {0: 2, 1: 1, 2: 3, 3: 0, 4: 4, 5: 5, 6: 6}),
    # 以下动物原始 sprite 已符合标准行顺序，无需重排
    ("Pig",     "assets/pig.png",      32, 32, {}),
    ("Cow",     "assets/cow.png",      32, 32, {}),
    ("Sheep",   "assets/sheep.png",    32, 32, {}),
    ("Horse",   "assets/horse.png",    32, 32, {}),
]


def rearrange_sprite(sprite_path, frame_w, frame_h, row_map):
    """重排 sprite 行顺序。返回 True=成功, False=跳过"""
    if not row_map:
        return False

    bak_path = sprite_path + ".bak"
    if os.path.exists(bak_path):
        print(f"  跳过（已有备份 .bak）: {sprite_path}")
        return False

    if not os.path.exists(sprite_path):
        print(f"  文件不存在: {sprite_path}")
        return False

    shutil.copy2(sprite_path, bak_path)

    img = Image.open(sprite_path).convert("RGBA")
    width, height = img.size
    total_rows = height // frame_h
    cols = width // frame_w

    max_target = max(row_map.keys()) if row_map else 0
    out_rows = max(total_rows, max_target + 1)

    out_img = Image.new("RGBA", (width, out_rows * frame_h), (0, 0, 0, 0))

    for target_row, source_row in row_map.items():
        if source_row >= total_rows:
            print(f"  警告: 源行 {source_row} 超出范围 (共{total_rows}行)，跳过")
            continue
        for col in range(cols):
            src_x = col * frame_w
            src_y = source_row * frame_h
            dst_x = col * frame_w
            dst_y = target_row * frame_h
            frame = img.crop((src_x, src_y, src_x + frame_w, src_y + frame_h))
            out_img.paste(frame, (dst_x, dst_y))

    out_img.save(sprite_path)
    print(f"  重排完成: {sprite_path} ({total_rows}行 -> {out_rows}行)")
    return True


def main():
    only_animal = sys.argv[1] if len(sys.argv) > 1 else None
    rearranged = 0
    skipped = 0

    for folder, sprite_rel, fw, fh, row_map in ANIMALS:
        if only_animal and folder.lower() != only_animal.lower():
            continue

        sprite_path = os.path.join(PROJECT_ROOT, folder, sprite_rel)
        print(f"[{folder}]")

        if not row_map:
            print(f"  跳过（已符合标准）: {sprite_rel}")
            skipped += 1
            continue

        if rearrange_sprite(sprite_path, fw, fh, row_map):
            rearranged += 1
        else:
            skipped += 1

    print(f"\n完成: 重排 {rearranged} 个, 跳过 {skipped} 个")
    print("提示: 原始文件已备份为 .png.bak，如需恢复直接覆盖回 .png")


if __name__ == "__main__":
    main()
