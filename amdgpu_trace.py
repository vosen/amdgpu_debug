import gdb
import sys
import io
import re
import os


class AmdgpuTraceBreakpoint(gdb.Breakpoint):
    def __init__(self, fn_name, lane, log_file, fn_address, instruction_offset, instruction, registers):
        self.fn_name = fn_name
        self.lane = lane
        self.log_file = log_file
        self.instruction_offset = instruction_offset
        self.instruction = instruction
        self.registers = registers
        location = "*(%s+%d) if $_lane == %d" % (fn_address, instruction_offset, lane)
        super(AmdgpuTraceBreakpoint, self).__init__(location, internal=True)

    def stop(self):
        if len(self.registers) == 0:
            self.log_file.write(f"{self.fn_name}+{self.instruction_offset}: {self.instruction}\n")
        else:
            reg_values = [self.format_register(reg) for reg in self.registers]
            formatted_reg_values = ", ".join(reg_values)
            self.log_file.write(f"{self.fn_name}+{self.instruction_offset}: {self.instruction}: {formatted_reg_values}\n")
        self.log_file.flush()
        return False

    def format_register(self, reg):
        value = gdb.execute(f"print/x ${reg}[{self.lane}]", to_string=True) if reg.startswith('v') else gdb.execute(f"print/x ${reg}", to_string=True)
        value_start =value.find("0x")
        return f"{reg}={value[value_start:-1]}" # string returned by gdb.execute contains newline


class AmdgpuTraceCommand(gdb.Command):
    """Trace execution of a function\nUSE: amdgpu_trace <SYMBOL> <LANEID> <FILE> [MIN_OFFSET] [MAX_OFFSET]"""

    def __init__(self):
        super(AmdgpuTraceCommand, self).__init__(
            "amdgpu_trace", gdb.COMMAND_USER
        )
        self.fun_address = re.compile(r"0x[a-fA-F0-9]+")
        self.fun_offset = re.compile(r"\<\+\d+\>")
        self.register = re.compile(r"[sv]\d+")
        self.multi_register = re.compile(r"[sv]\[\d+\:\d+\]")

    def complete(self, text, word):
        return gdb.COMPLETE_SYMBOL

    def invoke(self, args, from_tty):
        split_args = args.split()
        # gdb.parse_and_eval finds only one occurence of the function
        # gdb.lookup_symbol does not find amdgpu functions
        functions = gdb.execute(f"i functions {split_args[0]}", to_string=True).splitlines()
        functions = [f for f in [self.extract_fn_address(f) for f in functions] if f is not None]
        if len(functions) == 0:
            raise gdb.GdbError (f"`info function {split_args[0]}` returned no addresses")
        lane = int(split_args[1])
        path = split_args[2]
        min_offset = int(split_args[3]) if len(split_args) > 3 else 0
        max_offset = int(split_args[4]) if len(split_args) > 4 else 0
        max_offset = sys.maxsize if max_offset == 0 else max_offset
        log_file = open(path, "w")
        for fn_address in functions:
            reader = io.StringIO(gdb.execute(f"disassemble {fn_address}", to_string = True))
            reader.readline()
            for line in reader:
                if line.startswith('End'):
                    continue
                fun_offset_match = self.fun_offset.search(line)
                instruction_offset = int(fun_offset_match[0][2:-1])
                if instruction_offset < min_offset or instruction_offset > max_offset:
                    continue
                instruction_end = line.find('#')
                # if .find() finds no comment it returns -1, which is actually what we want, because we want to strip trailing newline
                instruction = line[fun_offset_match.end()+2:instruction_end]
                registers = list(map(lambda m: (m.start(), m[0]), self.register.finditer(line)))
                multi_registers = map(AmdgpuTraceCommand.extract_from_multiregister, self.multi_register.finditer(line))
                multi_registers = [item for sublist in multi_registers for item in sublist]
                all_registers = registers + multi_registers
                all_registers.sort(key = lambda x: x[0])
                AmdgpuTraceBreakpoint(split_args[0], lane, log_file, fn_address, instruction_offset, instruction, [j for i, j in all_registers])

    def extract_from_multiregister(match):
        text = match[0]
        kind = text[0]
        divider = text.find(':')
        reg_start = int(text[2:divider])
        reg_end = int(text[divider+1:-1])
        return map(lambda x: (match.start(), str(kind) + str(x)), iter(range(reg_start, reg_end+1)))

    def extract_fn_address(self, line):
        match = self.fun_address.match(line)
        if not match:
            return None
        return match.group()


AmdgpuTraceCommand()
