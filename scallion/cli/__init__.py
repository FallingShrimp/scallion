from argparse import ArgumentParser
import os
from scallion.cli.structs import Arguments

parser = ArgumentParser()
parser.add_argument("filename")
parser.add_argument("-o", "--output", type=str, default="")
parser.add_argument("-f", "--format", type=int, default=0)
parser.add_argument("-w", "--watch", action="store_true", default=False)
parser.add_argument("-p", "--port", type=int, default=0)

arguments = parser.parse_args(namespace=Arguments())
arguments.is_workspace = os.path.isdir(arguments.filename)

if not os.path.exists(arguments.filename):
    raise FileNotFoundError(arguments.filename)

if arguments.is_workspace:
    if arguments.output:
        output_path = os.path.abspath(arguments.output)
        if os.path.isfile(output_path):
            raise ValueError(
                f"--output 在 workspace 模式下必须是目录，不能指向已有文件: {arguments.output}"
            )
    # 默认输出到输入目录同名
    if not arguments.output:
        arguments.output = arguments.filename
else:
    # 单文件模式：传入文件时必须 .sdl 或 .txt 结尾（不改进行为，仅记录）
    pass
