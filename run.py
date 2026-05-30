#!/usr/bin/env python3
"""
统一启动脚本 — 按顺序执行 generate → doubao → byte

用法:
    python run.py                          # 默认主题"美女"
    python run.py "你的主题"                # 指定主题
    python run.py "主题" --type article    # 指定类型 (article|image|video)
    python run.py "主题" --step 2          # 从第 2 步开始 (1=generate, 2=doubao, 3=byte)
    python run.py "主题" --only 1          # 只运行第 1 步
"""

import subprocess
import sys
import os
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_step(step_num: int, step_name: str, cmd: list[str]) -> bool:
    """执行一个步骤，返回是否成功"""
    print("\n" + "=" * 60)
    print(f"🚀 第 {step_num} 步: {step_name}")
    print(f"   命令: {' '.join(cmd)}")
    print("=" * 60 + "\n")

    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"\n❌ 第 {step_num} 步 ({step_name}) 执行失败，退出码: {result.returncode}")
        return False
    print(f"\n✅ 第 {step_num} 步 ({step_name}) 完成")
    return True


def main():
    parser = argparse.ArgumentParser(description="按顺序运行 generate → doubao → byte")
    parser.add_argument("topic", nargs="?", default="美女", help="内容主题（默认: 美女）")
    parser.add_argument("--type", default="image", choices=["article", "image", "video"],
                        help="内容类型（默认: image）")
    parser.add_argument("--count", type=int, default=3, help="豆包 prompt 数量（默认: 3）")
    parser.add_argument("--step", type=int, choices=[1, 2, 3], default=1,
                        help="从第几步开始执行（默认: 1）")
    parser.add_argument("--only", type=int, choices=[1, 2, 3],
                        help="只运行指定步骤")

    args = parser.parse_args()

    python = sys.executable  # 使用当前 Python 解释器

    # 定义三个步骤
    steps = [
        {
            "num": 1,
            "name": "Kimi 生成内容",
            "cmd": [
                python, "generate.py",
                args.topic,
                "--type", args.type,
                "--count", str(args.count),
            ],
        },
        {
            "num": 2,
            "name": "豆包生成图片",
            "cmd": [
                python, "doubao.py",
            ],
        },
        {
            "num": 3,
            "name": "抖音发布",
            "cmd": [
                python, "byte.py",
            ],
        },
    ]

    # 确定运行范围
    if args.only:
        steps_to_run = [s for s in steps if s["num"] == args.only]
    else:
        steps_to_run = [s for s in steps if s["num"] >= args.step]

    print(f"📋 将执行以下步骤: {' → '.join(s['name'] for s in steps_to_run)}")

    for step in steps_to_run:
        success = run_step(step["num"], step["name"], step["cmd"])
        if not success:
            print(f"\n⛔ 流程在第 {step['num']} 步中断")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 全部流程执行完毕！")
    print("=" * 60)


if __name__ == "__main__":
    main()
