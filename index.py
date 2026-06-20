from scallion import Scallion, visualizer
from scallion.cli import arguments


scallion = Scallion()

script = scallion.parse_file(arguments.filename)
dumper = visualizer.print_ast(script)

with open(arguments.output, "w", encoding="utf8") as f:
    f.write(
        script.model_dump_json(
            indent=arguments.format if arguments.format > 0 else None,
            by_alias=True,
        )
    )
print(dumper)
