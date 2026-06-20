from scallion import Scallion
from scallion.cli import arguments
from scallion.visualizer import Visualizer
from rich.console import Console

scallion = Scallion()
visualizer = Visualizer()
console = Console(highlight=False)

script = scallion.parse_file(arguments.filename)
dumper = visualizer.print(script)

with open(arguments.output, "w", encoding="utf8") as f:
    f.write(
        script.model_dump_json(
            indent=arguments.format if arguments.format > 0 else None,
            by_alias=True,
        )
    )
console.print(dumper)
