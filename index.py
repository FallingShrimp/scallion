from scallion import Scallion, visualizer
from scallion.cli import arguments


scallion = Scallion()

script = scallion.parse_file(arguments.filename)
dumper = visualizer.print_ast(script)

print(dumper)
