# radius2 -- Agent Skill Guide

`radius2` is a command-line symbolic execution tool. Given a binary, it finds inputs that reach desired code paths and avoid others. You build a command, run it, read the output, and iterate if needed.

## Installation

```bash
r2pm -ci radius2
# or
cargo install radius2
```

Requires `radare2` installed from git.

## Basic Syntax

```bash
radius2 -p <binary> [flags] [options]
```

The only required argument is `-p` (path to binary). Everything else is optional.

## Core Workflow

1. **Create symbolic input**: `-s <name> <bits>` -- a variable the solver will find a value for
2. **Guide execution**: tell radius2 what code to reach (`-B`, `-b`) and what to avoid (`-X`, `-x`)
3. **Run and read output**: radius2 prints the solved value of each symbolic variable
4. **Iterate if needed**: adjust size, constraints, merge points, or optimization flags

## Quick Examples

Solve a crackme that prints "Incorrect" on failure:

```bash
radius2 -p ./crackme -s stdin 96 -X Incorrect
```

Solve a CTF flag checker with known prefix:

```bash
radius2 -p ./challenge -s flag 320 -c flag 'CTF{' -X Wrong -B Correct
```

Get JSON output for programmatic use:

```bash
radius2 -p ./binary -s input 64 -X Bad -B Good -j
```

## Argument Reference

### Symbolic Values (`-s`)

```
-s <NAME> <BITS>[n]
```

- `NAME`: identifier for the variable (printed in output)
- `BITS`: size in bits (8 = 1 byte, 64 = 8 bytes, 96 = 12 bytes, etc.)
- Append `n` to force numeric output instead of string: `-s count 32n`
- The special name `stdin` is automatically wired as the program's standard input

**Common sizes**: 8 (char), 32 (int), 64 (long/pointer), 96 (12-char string), 128 (16 bytes), 256 (32 bytes).

**Estimating size**: if you know the expected input is N characters, use `N * 8` bits. When unsure, overestimate slightly -- extra bytes will be null.

### Guiding Execution

| Flag | What it does | Example |
|------|-------------|---------|
| `-X <string>` | Avoid code referencing this string | `-X "Invalid"` |
| `-B <string>` | Break (stop+solve) at code referencing this string | `-B "Success"` |
| `-x <addr>` | Avoid this address | `-x 0x400790` |
| `-b <addr>` | Break at this address | `-b 0x4007a1` |
| `-a <addr>` | Start execution at address (instead of entrypoint) | `-a 0x4006fd` |

Addresses can be hex (`0x400790`), decimal, symbol names, or symbol+offset (`main+109`).

String-based flags (`-X`, `-B`) are the easiest way to guide execution. They use cross-references found by radare2. If a string isn't found, add `-r aae` to run additional analysis.

Multiple avoid/break points can be combined: `-X Error -X Invalid -B Success -B Flag`.

### Constraints (`-c`, `-C`)

Constrain symbol values before execution:

```
-c <SYMBOL> <EXPR>
```

| Pattern | Meaning |
|---------|---------|
| `-c flag 'CTF{'` | First bytes must equal "CTF{" |
| `-c flag '[a-z]'` | Each byte must be lowercase letter |
| `-c flag '[a-zA-Z0-9]'` | Alphanumeric only |
| `-c flag '[ -~]'` | Printable ASCII only |
| `-c flag '[0-9a-f]'` | Hex digits only |

Constrain after execution (useful for matching program output):

```
-C <SYMBOL_OR_FD> <EXPR>
```

File descriptors: `0` = stdin, `1` = stdout, `2` = stderr.

```bash
# Constrain stdout to contain this string after execution
radius2 -p binary -s hex 128 -C1 'Output: 875cd4f2e18f8fc4'
```

### Setting Registers and Memory (`-S`)

```
-S <REG_OR_ADDR> <VALUE> <BITS>
```

```bash
# Set register rdi to an address, then write symbolic value there
radius2 -p binary -s flag 96 -S rdi 0x100000 64 -S 0x100000 flag 96
```

### Program Arguments (`-A`)

```bash
# argv[1] = the symbolic variable "flag"
radius2 -p binary -s flag 128 -A . flag

# Mix concrete and symbolic args
radius2 -p binary -s key 64 -A programname key
```

Any argument name that matches a defined symbol becomes that symbol's value. Other strings are passed literally.

Note: if a symbolic value is defined but not explicitly placed via `-S`, `-A`, or `-f`, it is automatically used as `argv[1]`.

### Symbolic Files (`-f`)

```
-f <PATH> <SYMBOL>
```

```bash
# Program reads config.txt -- make its contents symbolic
radius2 -p binary -s data 256 -f ./config.txt data -B Valid
```

Numeric paths are treated as file descriptors (`-f 0 stdin` = stdin).

### Include / Exclude Substrings

```bash
-i <SYMBOL> <EXPR>    # symbol must contain substring
-I <SYMBOL> <EXPR>    # symbol must NOT contain substring
```

### ESIL Hooks (`-H`)

Inject custom logic at an address:

```
-H <ADDR> <ESIL_EXPR>
```

```bash
# Print value of flag at address
radius2 -p binary -s flag 64 -H 0x401000 'flag,.'

# If eax == 0 at this address, print stdin
radius2 -p binary -s stdin 48 -H 0x400849 'eax,!,?{,stdin,.,}'

# Set breakpoint conditionally
radius2 -p binary -s x 32 -H 0x400800 'eax,100,>,?{,!!,}'
```

Key ESIL operators for hooks:

| Operator | Meaning |
|----------|---------|
| `.` | Evaluate and print top of stack |
| `!!` | Mark state as breakpoint hit |
| `!_` | Mark state as avoid hit |
| `_` | Constrain top of stack to be nonzero |
| `?{,...,}` | Conditional: execute if top != 0 |
| `!` | Logical NOT |
| `==`, `<`, `>` | Comparisons |

### State Merging

When execution is slow due to loops with symbolic conditions (state explosion), set merge points:

```bash
# Merge states at a specific address (typically between loops)
radius2 -p binary -s stdin 48 -X Incorrect -m 0x4007ba

# Auto-merge all states
radius2 -p binary -s input 64 -M -B Success

# Merge all finished states
radius2 -p binary -s input 64 -K -B Success
```

### Optimization Flags

| Flag | Effect | When to use |
|------|--------|------------|
| `-z` | Lazy solving (less frequent SAT checks) | First optimization to try; often 2-10x speedup |
| `-N` | Disable self-modifying code tracking | When binary doesn't modify its own code |
| `-M` | Auto-merge states | When state explosion is suspected |
| `--max <N>` | Limit active states | To prevent memory exhaustion |

### Output Flags

| Flag | Effect |
|------|--------|
| `-j` | JSON output: `{"symbols":{"name":"value"},"stdout":"","stderr":""}` |
| `-1` | Print program's stdout |
| `-2` | Print program's stderr |
| `-v` | Verbose: show instruction trace |
| `-V` | Verbose with color |
| `-P` | Print performance profile (times in microseconds) |

### Test Case Generation

```bash
radius2 -p binary -s flag 256 -F ./testcases -P
# Creates testcases/flag0000, testcases/flag0001, ... for each execution path
```

### Radare2 Commands at Startup (`-r`)

```bash
# Run additional analysis for string xrefs
radius2 -p binary -r aae -s input 64 -X Wrong
```

## Output Format

**Default** (human-readable):
```
  flag : "grey{d1d_y0u_s0lv3_by_emul4t1ng?_1e4b8a}"
```

**JSON** (`-j`):
```json
{"symbols":{"flag":"0x..."},"stdout":"","stderr":""}
```

**Profile** (`-P`):
```
init time:      74039
run time:       194957
instructions:   2226
instr/usec:     0.011418
generated:      5
total time:     269024
```

If the solver cannot find a solution, the output will indicate the state is unsatisfiable (red "unsat" in color mode).

## Practical Recipes

### Crackme with stdin input

```bash
radius2 -p ./crackme -s stdin 96 -X Incorrect
```

### Crackme with argv input

```bash
radius2 -p ./crackme -s flag 256 -A . flag -X Wrong -B Correct
```

### CTF flag with known prefix and printable constraint

```bash
radius2 -p ./ctf -s flag 320 -c flag 'flag{' -c flag '[ -~]' -B Correct -X Wrong
```

### Reverse from expected output

```bash
radius2 -p ./encoder -s input 128 -C1 'expected output string'
```

### Binary with loops (needs merging)

```bash
radius2 -p ./loopy -s stdin 48 -X Bad -m 0x4007ba
```

### Fast mode for large binaries

```bash
radius2 -p ./big_binary -s input 64 -X Fail -B Win -z -N
```

### Generate all test cases

```bash
radius2 -p ./binary -s flag 256 -F ./testcases -P
```

### Debug: see what's happening

```bash
radius2 -p ./binary -s input 64 -V 2>&1 | head -200
```

### Remote targets

```bash
# Debugger
radius2 -p dbg://192.168.1.123:5555 -a 0x400800 -s input 64

# Frida
radius2 -p frida://usb/attach//process_name -a free -s input 64

# GDB/QEMU/JTAG
radius2 -p gdb://host:port -a 0x400800 -s input 64
```

## Troubleshooting

### No solution / timeout

1. **Verify strings exist**: use `-r aae` to improve string cross-reference detection
2. **Reduce symbolic size**: try smaller bit width first, increase if needed
3. **Add `-z`**: lazy solving is faster and often sufficient
4. **Add merge points** (`-m`): look for addresses between loops
5. **Add more avoid points** (`-x`): prune dead paths early
6. **Profile** (`-P`): check if bottleneck is init or run time

### Unsatisfiable ("unsat")

1. Remove constraints (`-c`) one at a time to find the conflicting one
2. Remove merge points -- bad placement can create contradictions
3. Try a larger symbolic size -- too few bits may make the problem impossible

### Out of memory

1. `--max 50` to cap active states
2. `-K` to merge all finished states
3. Reduce symbolic size
4. Add more avoid points to prune early

### String not found for `-X` / `-B`

Add `-r aae` to run radare2's emulation-based analysis which finds more cross-references:

```bash
radius2 -p binary -r aae -s input 64 -X "Error" -B "OK"
```

## Supported Architectures

**Fully supported**: x86, x86-64, ARM, Thumb, AArch64, PowerPC

**Partial support**: MIPS, RISC-V, Dalvik, cBPF, eBPF, Gameboy, 6502, 8051, AVR, and others

## Agent Usage Tips

- Start with the simplest command: `-p binary -s stdin <bits> -X <error_string>`
- Use `-j` for machine-readable output when parsing results programmatically
- If the first run doesn't work, iterate: adjust size, add constraints, add `-z`, add merge points
- Check the binary's strings first (e.g. with `rabin2 -z binary` or `r2 -qc izq binary`) to find good targets for `-X` and `-B`
- When size is unknown, start with a reasonable estimate (e.g. 256 bits = 32 bytes) and adjust based on results
- Combine multiple optimizations for tough binaries: `-z -N -M`
- Use `-P` to diagnose performance issues before guessing at optimizations
