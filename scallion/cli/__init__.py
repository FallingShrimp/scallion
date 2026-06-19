from argparse import ArgumentParser
import os
from scallion.cli.structs import Arguments

parser = ArgumentParser()
parser.add_argument("filename")
parser.add_argument("-o", "--output", type=str, default="")

arguments = parser.parse_args(namespace=Arguments())

if not os.path.exists(arguments.filename):
    raise FileNotFoundError(arguments.filename)
