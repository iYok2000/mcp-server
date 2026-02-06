import subprocess
import sys

CORE_BIN = "../core/target/release/core"

core = subprocess.Popen(
    [CORE_BIN],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        core.stdin.write(line + "\n")
        core.stdin.flush()

        response = core.stdout.readline()
        sys.stdout.write(response)
        sys.stdout.flush()

if __name__ == "__main__":
    main()
