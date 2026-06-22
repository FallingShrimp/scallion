from argparse import Namespace


class Arguments(Namespace):
    filename: str
    output: str
    format: int
    watch: bool
    port: int
