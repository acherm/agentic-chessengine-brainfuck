#!/usr/bin/env python3
"""
Main generator: assembles all BF modules into chess.bf
"""

import sys
import time

from bf_emitter import BFEmitter
from bf_uci import emit_uci_loop


def main():
    print("Generating chess.bf...", file=sys.stderr)
    start = time.time()

    e = BFEmitter()

    # Emit the UCI main loop (includes board init, move gen, etc.)
    emit_uci_loop(e)

    # Get the output
    bf_code = e.get_output()

    # Write to file
    with open("chess.bf", "w") as f:
        f.write(bf_code)

    elapsed = time.time() - start
    size_kb = len(bf_code) / 1024
    size_mb = size_kb / 1024
    print(f"Generated chess.bf: {len(bf_code)} bytes ({size_kb:.1f} KB / {size_mb:.2f} MB) in {elapsed:.1f}s",
          file=sys.stderr)
    if size_mb > 1.0:
        print(f"WARNING: chess.bf is {size_mb:.2f} MB, exceeds 1 MB target!", file=sys.stderr)


if __name__ == "__main__":
    main()
