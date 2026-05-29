"""
猫咪桌面宠物素材准备脚本
用法：
    python prepare_pet.py --video cat_walk.mp4 --name MyCat --action walk --size 200

它会：
1. 从视频中抽帧
2. 用 rembg 去背景
3. 统一缩放到指定大小
4. 输出到 DyberPet 的 res/role/<name>/action/ 目录
5. 自动生成 pet_conf.json 和 act_conf.json 配置文件
"""

import argparse
import os
import json
from pathlib import Path
from PIL import Image
from rembg import remove
import subprocess


def extract_frames(video_path, output_dir, fps=8):
    """用 ffmpeg 从视频中抽帧"""
    os.makedirs(output_dir, exist_ok=True)
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-y",
        os.path.join(output_dir, "frame_%04d.png")
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    frames = sorted(Path(output_dir).glob("frame_*.png"))
    print(f"  抽取了 {len(frames)} 帧")
    return frames


def remove_background(frames, output_dir):
    """批量去背景"""
    os.makedirs(output_dir, exist_ok=True)
    result_paths = []
    for i, frame_path in enumerate(frames):
        img = Image.open(frame_path)
        output = remove(img)
        out_path = os.path.join(output_dir, f"nobg_{i:04d}.png")
        output.save(out_path)
        result_paths.append(out_path)
        print(f"  去背景: {i+1}/{len(frames)}", end="\r")
    print()
    return result_paths


def resize_and_export(image_paths, output_dir, action_name, size):
    """缩放并导出为 DyberPet 格式: action_0.png, action_1.png, ..."""
    os.makedirs(output_dir, exist_ok=True)
    exported = []
    for i, img_path in enumerate(image_paths):
        img = Image.open(img_path).convert("RGBA")
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        # 放到正方形画布中心
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        x = (size - img.width) // 2
        y = (size - img.height) // 2
        canvas.paste(img, (x, y))
        out_path = os.path.join(output_dir, f"{action_name}_{i}.png")
        canvas.save(out_path)
        exported.append(out_path)
    print(f"  导出了 {len(exported)} 帧到 {output_dir}")
    return exported


def generate_configs(role_dir, pet_name, actions, size):
    """生成 pet_conf.json 和 act_conf.json"""

    # act_conf.json
    act_conf = {}
    for action_name, frame_count in actions.items():
        conf = {
            "images": action_name,
            "act_num": 1,
            "frame_refresh": 0.12
        }
        if "walk" in action_name or "left" in action_name or "right" in action_name:
            conf["need_move"] = True
            conf["direction"] = "left" if "left" in action_name else "right"
            conf["act_num"] = 3
        elif "sleep" in action_name:
            conf["act_num"] = 5
            conf["frame_refresh"] = 0.5
        else:
            conf["act_num"] = 1
        act_conf[action_name] = conf

    # 确保有基本动作
    if "default" not in act_conf:
        # 用第一个动作作为 default
        first_action = list(actions.keys())[0]
        act_conf["default"] = {"images": first_action, "act_num": 1, "frame_refresh": 0.12}
    if "drag" not in act_conf:
        first_action = list(actions.keys())[0]
        act_conf["drag"] = {"images": first_action, "act_num": 1}
    if "fall" not in act_conf:
        first_action = list(actions.keys())[0]
        act_conf["fall"] = {"images": first_action, "act_num": 1}

    # pet_conf.json
    pet_conf = {
        "width": size,
        "height": size,
        "scale": 1.0,
        "refresh": 5,
        "interact_speed": 0.02,
        "default": "default",
        "up": "default",
        "down": "default",
        "left": "left_walk" if "left_walk" in act_conf else "default",
        "right": "right_walk" if "right_walk" in act_conf else "default",
        "drag": "drag",
        "fall": "fall",
        "random_act": []
    }

    # 自动生成 random_act
    for action_name in actions.keys():
        if action_name in ("default", "drag", "fall"):
            continue
        entry = {
            "name": action_name,
            "act_list": [action_name],
            "act_prob": 0.3,
            "act_type": [2, 0]
        }
        if "walk" in action_name:
            entry["act_prob"] = 0.1
            entry["act_type"] = [3, 0]
            # 如果有左右走，组合起来
        if "sleep" in action_name:
            entry["act_prob"] = 0.05
            entry["act_type"] = [1, 0]
        pet_conf["random_act"].append(entry)

    # 默认站立
    if "default" in actions:
        pet_conf["random_act"].insert(0, {
            "name": "站立",
            "act_list": ["default"],
            "act_prob": 1.0,
            "act_type": [2, 0]
        })

    with open(os.path.join(role_dir, "act_conf.json"), "w", encoding="utf-8") as f:
        json.dump(act_conf, f, ensure_ascii=False, indent=2)

    with open(os.path.join(role_dir, "pet_conf.json"), "w", encoding="utf-8") as f:
        json.dump(pet_conf, f, ensure_ascii=False, indent=2)

    print(f"  配置文件已生成: {role_dir}/pet_conf.json, act_conf.json")


def process_single_video(video_path, pet_name, action_name, size, fps):
    """处理单个视频"""
    role_dir = os.path.join("res", "role", pet_name)
    action_dir = os.path.join(role_dir, "action")
    tmp_dir = os.path.join("/tmp", f"dyber_pet_{pet_name}")
    frames_dir = os.path.join(tmp_dir, "frames")
    nobg_dir = os.path.join(tmp_dir, "nobg")

    print(f"\n[1/3] 从视频抽帧 ({fps} fps)...")
    frames = extract_frames(video_path, frames_dir, fps)

    print(f"[2/3] 去除背景...")
    nobg_frames = remove_background(frames, nobg_dir)

    print(f"[3/3] 缩放并导出...")
    resize_and_export(nobg_frames, action_dir, action_name, size)

    return len(nobg_frames)


def process_images(image_dir, pet_name, action_name, size):
    """处理一组已有的图片（已经去好背景的）"""
    role_dir = os.path.join("res", "role", pet_name)
    action_dir = os.path.join(role_dir, "action")

    images = sorted(Path(image_dir).glob("*.png")) + sorted(Path(image_dir).glob("*.jpg"))
    if not images:
        print(f"错误: {image_dir} 中没有找到图片")
        return 0

    print(f"\n处理 {len(images)} 张图片...")
    image_paths = [str(p) for p in images]
    resize_and_export(image_paths, action_dir, action_name, size)
    return len(images)


def main():
    parser = argparse.ArgumentParser(description="猫咪桌面宠物素材准备工具")
    parser.add_argument("--video", help="输入视频路径")
    parser.add_argument("--images", help="输入图片文件夹路径（已去背景的图片）")
    parser.add_argument("--name", required=True, help="宠物名称（英文）")
    parser.add_argument("--action", required=True, help="动作名称，如: default, left_walk, right_walk, sleep")
    parser.add_argument("--size", type=int, default=200, help="输出图片尺寸（像素，默认200）")
    parser.add_argument("--fps", type=int, default=8, help="抽帧帧率（默认8）")
    parser.add_argument("--no-rembg", action="store_true", help="跳过去背景步骤（图片已经是透明背景）")
    parser.add_argument("--gen-config", action="store_true", help="根据已有的 action 文件夹生成配置")

    args = parser.parse_args()

    role_dir = os.path.join("res", "role", args.name)
    action_dir = os.path.join(role_dir, "action")

    if args.gen_config:
        # 扫描 action 目录，自动生成配置
        if not os.path.exists(action_dir):
            print(f"错误: {action_dir} 不存在")
            return
        action_files = list(Path(action_dir).glob("*.png"))
        actions = {}
        for f in action_files:
            name = f.stem.rsplit("_", 1)[0]
            actions[name] = actions.get(name, 0) + 1
        print(f"检测到动作: {actions}")
        generate_configs(role_dir, args.name, actions, args.size)
        return

    if args.video:
        frame_count = process_single_video(args.video, args.name, args.action, args.size, args.fps)
    elif args.images:
        if args.no_rembg:
            frame_count = process_images(args.images, args.name, args.action, args.size)
        else:
            # 先去背景再处理
            images = sorted(Path(args.images).glob("*.png")) + sorted(Path(args.images).glob("*.jpg"))
            tmp_dir = os.path.join("/tmp", f"dyber_pet_{args.name}", "nobg")
            print(f"\n[1/2] 去除背景...")
            nobg_frames = remove_background([str(p) for p in images], tmp_dir)
            print(f"[2/2] 缩放并导出...")
            resize_and_export(nobg_frames, action_dir, args.action, args.size)
            frame_count = len(nobg_frames)
    else:
        print("错误: 请指定 --video 或 --images")
        return

    # 扫描所有已有动作并生成配置
    action_files = list(Path(action_dir).glob("*.png"))
    actions = {}
    for f in action_files:
        name = f.stem.rsplit("_", 1)[0]
        actions[name] = actions.get(name, 0) + 1
    generate_configs(role_dir, args.name, actions, args.size)

    print(f"\n✅ 完成！宠物 '{args.name}' 动作 '{args.action}' 已准备好 ({frame_count} 帧)")
    print(f"   运行桌宠: /Users/yangyunzhe/dyber_env/bin/python run_DyberPet.py")


if __name__ == "__main__":
    main()
