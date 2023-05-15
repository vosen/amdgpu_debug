import gdb
import sys
import io
import re


class AmdgpuTraceBreakpoint(gdb.Breakpoint):
    def __init__(self, fn_name, lane, file, fn_address, instruction_offset, instruction, registers):
        self.fn_name = fn_name
        self.lane = lane
        self.file = file
        self.instruction_offset = instruction_offset
        self.instruction = instruction
        self.registers = registers
        location = "*(%s+%d)" % (fn_address, instruction_offset)
        super(AmdgpuTraceBreakpoint, self).__init__(location, internal=True)

    def stop(self):
        if len(self.registers) == 0:
            self.file.write(f"{self.fn_name}+{self.instruction_offset}: {self.instruction}\n")
        else:
            reg_values = [self.format_register(reg) for reg in self.registers]
            formatted_reg_values = ", ".join(reg_values)
            self.file.write(f"{self.fn_name}+{self.instruction_offset}: {self.instruction}: {formatted_reg_values}\n")
        self.file.flush()
        return False

    def format_register(self, reg):
        value = gdb.execute(f"print/x ${reg}[{self.lane}]", to_string=True) if reg.startswith('v') else gdb.execute(f"print/x ${reg}", to_string=True)
        value_start =value.find("0x")
        return f"{reg}={value[value_start:-1]}" # string returned by gdb.execute contains newline


class AmdgpuTraceCommand(gdb.Command):
    """Trace execution of a function"""

    def __init__(self):
        super(AmdgpuTraceCommand, self).__init__(
            "amdgpu_trace", gdb.COMMAND_USER
        )
        self.fun_offset = re.compile(r"\<\+\d+\>")
        self.register = re.compile(r"[sv]\d+")
        self.multi_register = re.compile(r"[sv]\[\d+\:\d+\]")

    def complete(self, text, word):
        return gdb.COMPLETE_SYMBOL

    def invoke(self, args, from_tty):
        split_args = args.split()
        fn_ = gdb.parse_and_eval(split_args[0])
        if fn_.address is None:
            raise gdb.GdbError ("%s is not addressable" % str(args))
        lane = int(split_args[1])
        path = split_args[2]
        file = open(path, 'w')
        fn_address = fn_.address.format_string(format = "x")
        reader = io.StringIO(gdb.execute("disassemble {0}".format(fn_.address.format_string(format = "x")), to_string = True))
        # Dump of assembler code for function foobar:
        reader.readline()
        for line in reader:
            if line.startswith('End'):
                continue
            fun_offset_match = self.fun_offset.search(line)
            instruction_offset = int(fun_offset_match[0][2:-1])
            instruction_end = line.find('#')
            # if .find() finds no comment it returns -1, which is actually what we want, because we want to strip trailing newline
            instruction = line[fun_offset_match.end()+2:instruction_end]
            registers = list(map(lambda m: (m.start(), m[0]), self.register.finditer(line)))
            multi_registers = map(AmdgpuTrace.extract_from_multiregister, self.multi_register.finditer(line))
            multi_registers = [item for sublist in multi_registers for item in sublist]
            all_registers = registers + multi_registers
            all_registers.sort(key = lambda x: x[0])
            AmdgpuTraceBreakpoint(split_args[0], lane, file, fn_address, instruction_offset, instruction, [j for i, j in all_registers])

    def extract_from_multiregister(match):
        text = match[0]
        kind = text[0]
        divider = text.find(':')
        reg_start = int(text[2:divider])
        reg_end = int(text[divider+1:-1])
        return map(lambda x: (match.start(), str(kind) + str(x)), iter(range(reg_start, reg_end+1)))


AmdgpuTraceCommand()
