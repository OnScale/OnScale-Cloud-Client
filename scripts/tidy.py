#!/usr/bin/env python
import re
import os


def main():
    path = os.path.join(os.path.dirname(__file__), "datamodel.py")

    with open(path, "r") as f:
        code = f.read()

    enum_pattern = re.compile(r"\s+[a-zA-Z0-9_-]+\s=\s'[a-zA-Z0-9_-]+'")

    new_code = list()
    in_enum = False
    for line in code.split("\n"):
        # Fix bad artifacts from the generation
        if "_code__owner_" in line or "_write_" in line or "_read_" in line:
            line = f'    """ {line.strip()} """'

        # Make Enums uppercase
        elif "(Enum):" in line:
            in_enum = True
        elif in_enum:
            if not line or line.isspace():
                in_enum = False
            elif enum_pattern.search(line):
                line = line.upper()

        new_code.append(line)
    new_code = "\n".join(new_code)
    if not new_code.endswith("\n"):
        new_code = f"{new_code}\n"

    with open(path, "w") as f:
        f.write(new_code)


if __name__ == "__main__":
    main()
