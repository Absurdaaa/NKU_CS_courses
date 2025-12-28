from PIL import Image
import os

def extract_frames_pillow(gif_path, output_dir="frames_pillow", fmt="png"):
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    # 打开GIF
    with Image.open(gif_path) as img:
        frame_count = 0
        try:
            while True:
                # 保存当前帧
                frame_path = os.path.join(output_dir, f"frame_{frame_count:04d}.{fmt}")
                img.save(frame_path)
                frame_count += 1
                # 切换到下一帧
                img.seek(img.tell()+1)
        except EOFError:
            # 遍历完所有帧
            pass
    print(f"导出完成，共 {frame_count} 帧，保存至 {output_dir}")

# 示例调用
extract_frames_pillow("dcgan (1).gif", output_dir="my_frames", fmt="png")