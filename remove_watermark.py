#!/usr/bin/env python3
"""
图片左上角水印去除脚本

用法:
    # 处理单张图片
    python remove_watermark.py image.jpg

    # 处理目录下所有图片
    python remove_watermark.py /path/to/images/

    # 指定输出目录
    python remove_watermark.py image.jpg -o /path/to/output/

    # 自定义裁切比例（默认 左12% 上6%）
    python remove_watermark.py image.jpg --width 0.15 --height 0.08

    # 批量处理并覆盖原图
    python remove_watermark.py /path/to/images/ --inplace
"""

import argparse
import os
import sys
from pathlib import Path
from PIL import Image

# 支持的图片格式
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}


def remove_watermark(
    image_path: str,
    output_path: str = None,
    crop_width_ratio: float = 0.12,
    crop_height_ratio: float = 0.06,
) -> bool:
    """
    去除图片左上角水印

    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径，None 则覆盖原图
        crop_width_ratio: 从左侧裁切的宽度比例（默认 12%）
        crop_height_ratio: 从顶部裁切的高度比例（默认 6%）

    Returns:
        是否成功
    """
    try:
        img = Image.open(image_path)
        w, h = img.size

        # 计算裁切像素
        crop_w = int(w * crop_width_ratio)
        crop_h = int(h * crop_height_ratio)

        # 裁切：从 (crop_w, crop_h) 到 (w, h)
        cropped = img.crop((crop_w, crop_h, w, h))

        # 保存
        save_path = output_path or image_path
        save_kwargs = {"quality": 95}

        # PNG 保留透明通道
        if save_path.lower().endswith('.png'):
            save_kwargs = {}

        cropped.save(save_path, **save_kwargs)
        return True

    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        return False


def process_single(
    image_path: str,
    output_dir: str = None,
    crop_width_ratio: float = 0.12,
    crop_height_ratio: float = 0.06,
    inplace: bool = False,
) -> bool:
    """处理单张图片"""
    if not os.path.exists(image_path):
        print(f"❌ 文件不存在: {image_path}")
        return False

    # 确定输出路径
    if inplace:
        output_path = image_path
    elif output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, os.path.basename(image_path))
    else:
        # 默认在原目录生成 _nowm 后缀的文件
        name, ext = os.path.splitext(image_path)
        output_path = f"{name}_nowm{ext}"

    success = remove_watermark(
        image_path,
        output_path,
        crop_width_ratio,
        crop_height_ratio,
    )

    if success:
        orig_size = os.path.getsize(image_path) / 1024
        new_size = os.path.getsize(output_path) / 1024
        print(f"  ✅ {os.path.basename(image_path)}: {orig_size:.0f}KB → {new_size:.0f}KB")

    return success


def process_directory(
    dir_path: str,
    output_dir: str = None,
    crop_width_ratio: float = 0.12,
    crop_height_ratio: float = 0.06,
    inplace: bool = False,
) -> tuple:
    """处理目录下所有图片"""
    # 收集所有图片文件
    image_files = []
    for f in sorted(os.listdir(dir_path)):
        if Path(f).suffix.lower() in SUPPORTED_FORMATS:
            image_files.append(os.path.join(dir_path, f))

    if not image_files:
        print(f"⚠️ 目录中没有找到图片: {dir_path}")
        return 0, 0

    print(f"📂 找到 {len(image_files)} 张图片")
    print(f"   裁切比例: 左 {crop_width_ratio*100:.0f}% | 上 {crop_height_ratio*100:.0f}%")
    print()

    success_count = 0
    for img_path in image_files:
        if process_single(img_path, output_dir, crop_width_ratio, crop_height_ratio, inplace):
            success_count += 1

    return success_count, len(image_files)


def main():
    parser = argparse.ArgumentParser(
        description="去除图片左上角水印",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python remove_watermark.py image.jpg                    # 单张图片
  python remove_watermark.py /path/to/images/             # 批量处理目录
  python remove_watermark.py image.jpg -o output/         # 指定输出目录
  python remove_watermark.py image.jpg --width 0.15       # 自定义裁切宽度
  python remove_watermark.py images/ --inplace            # 覆盖原图
        """,
    )
    parser.add_argument(
        "input",
        help="图片文件或目录路径",
    )
    parser.add_argument(
        "-o", "--output",
        help="输出目录（不指定则生成 _nowm 后缀文件）",
    )
    parser.add_argument(
        "--width",
        type=float,
        default=0.12,
        help="从左侧裁切的宽度比例（默认 0.12 = 12%%）",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=0.06,
        help="从顶部裁切的高度比例（默认 0.06 = 6%%）",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="直接覆盖原图（慎用）",
    )

    args = parser.parse_args()

    print("=" * 50)
    print("✂️  图片水印去除工具")
    print("=" * 50)

    if os.path.isdir(args.input):
        success, total = process_directory(
            args.input,
            args.output,
            args.width,
            args.height,
            args.inplace,
        )
        print(f"\n{'=' * 50}")
        print(f"✨ 完成: {success}/{total} 张图片处理成功")
        print(f"{'=' * 50}")
    elif os.path.isfile(args.input):
        print(f"\n📷 处理: {args.input}")
        if process_single(args.input, args.output, args.width, args.height, args.inplace):
            print(f"\n✨ 处理完成！")
        else:
            print(f"\n❌ 处理失败")
            sys.exit(1)
    else:
        print(f"❌ 路径不存在: {args.input}")
        sys.exit(1)


if __name__ == "__main__":
    main()
