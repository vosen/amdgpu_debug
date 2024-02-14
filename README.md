My helpers for debugging AMD GPU issues:

- `amdgpu_trace.py`

  Sometimes you run into a corrupted value in a register, but it has been produced by a series of other instructions. Instead of debugging every instruction one by one you can use this script. For a given function, on every instruction it will save the values in registers of a single GPU lane. It works by getting function disassembly from gdb and scanning it for instructions offsets and then registers used by the instruction. Keep in mind some things:
  * It's meant to work with only a single wavefront running (for some reason `$_streq($_dispatch_pos,"(X,Y,Z)/W")` does not work in conditional breakpoints)
  * There's a limitation in rocgdb (or a bug?) where it can't set breakpoints with offsets before GPU function is broken into, so the pattern of use is:
    ```
    b foobar
    c
    # once foobar is broken into
    amdgpu_trace foobar ...
    ```
  * It is extremally slow
  
  
  Load it like this:
  ```
  source <PATH_TO_REPO>/amdgpu_trace.py
  ```
  and check the usage with
  ```
  help amdgpu_trace
  ```

- `.gdbinit`

  Function `amdgpu_reg_dump` to print the content of every vector register. Useful if you are suspecting a function is miscompiled (fill/spill mismatch, unbalanced stack, signature mismatch, etc). Print the regsters before and after and compare. Add it to your `.gdbinit` like this:
  ```
  source <PATH_TO_REPO>/.gdbinit
  ```

- `split_llvm_print.py`

  When using Clang with `-mllvm -print-after-all` or `-mllvm -print-before-all` Clang will output all the passes in one big vomit to console. This script takes this (piped to file) output and splits it into separate files by passes