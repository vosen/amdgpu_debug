# Clang has an ability to print IR for a function after/before every pas with 
# -mllvm -print-after-all -mllvm -filter-print-funcs=foobar
# The problem is that it prints one big log file, which is a bit unwieldy
# This script takes that output and splits it into separate files
import sys
import os
import re


def main(file_path, out_dir):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    pattern1 = re.compile(r"(?:# )?\*\*\* IR Dump (?:Before|After) (.+) on .+ \*\*\*")
    pattern2 = re.compile(r"(?:# )?\*\*\* IR Dump (?:Before|After) .+ \((.+)\) \*\*\*")
    pass_number = 0
    pass_name = ""
    output = ""
    with open(file_path) as file:
        for line in file.readlines():
            if line.startswith("*** IR Dump") or line.startswith("# *** IR Dump"):
                new_pass_name = None
                match = pattern1.match(line)
                if match:
                    new_pass_name = match.group(1)
                else:
                    match = pattern2.match(line)
                    if not match:
                        raise Exception(f"Unexpected pattern {line}")
                    new_pass_name = match.group(1)
                if pass_number == 0:
                    if output != "":
                        raise Exception(f"Unexpected pattern at the start of the file")
                else:
                    write_pass(out_dir, pass_number, pass_name, output)
                pass_number += 1
                pass_name = new_pass_name
                output = ""
            output += line
    write_pass(out_dir, pass_number, pass_name, output)
    

def write_pass(out_dir, pass_number, pass_name, output):
    file_path = os.path.join(out_dir, f"{str(pass_number).zfill(3)}-{pass_name}.txt")
    with open(file_path, 'w') as f:
        f.write(output)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if 2 < len(sys.argv) else None)