"""
Core BF code emitter with compile-time pointer tracking.

The BFEmitter maintains a virtual pointer position so that
move_to(cell) emits the minimal number of > or < instructions.
"""


class BFEmitter:
    def __init__(self):
        self.code = []       # List of BF instruction strings
        self.ptr = 0         # Current compile-time pointer position
        self._indent = 0     # For readable output (ignored in BF)

    def emit(self, bf_code):
        """Emit raw BF code."""
        self.code.append(bf_code)

    def move_to(self, cell):
        """Move the data pointer to the given cell."""
        diff = cell - self.ptr
        if diff > 0:
            self.emit('>' * diff)
        elif diff < 0:
            self.emit('<' * (-diff))
        self.ptr = cell

    def set_val(self, cell, value):
        """Set a cell to a specific value (assuming it's currently 0)."""
        self.move_to(cell)
        if value > 0:
            self.emit('+' * value)

    def clear(self, cell):
        """Clear a cell to 0."""
        self.move_to(cell)
        self.emit('[-]')

    def set_cell(self, cell, value):
        """Clear and set a cell to a specific value."""
        self.clear(cell)
        value = value % 256
        if value > 0:
            self.move_to(cell)
            if value <= 128:
                self.emit('+' * value)
            else:
                self.emit('-' * (256 - value))

    def inc(self, cell, amount=1):
        """Increment a cell by amount."""
        self.move_to(cell)
        self.emit('+' * (amount % 256))

    def dec(self, cell, amount=1):
        """Decrement a cell by amount."""
        self.move_to(cell)
        self.emit('-' * (amount % 256))

    def output(self, cell):
        """Output the character at cell."""
        self.move_to(cell)
        self.emit('.')

    def input(self, cell):
        """Read input into cell."""
        self.move_to(cell)
        self.emit(',')

    def open_loop(self, cell):
        """Open a loop on cell. Pointer must be at cell."""
        self.move_to(cell)
        self.emit('[')

    def close_loop(self, cell):
        """Close a loop on cell. Pointer must be at cell."""
        self.move_to(cell)
        self.emit(']')

    def loop(self, cell):
        """Context manager-style: returns (open, close) callables."""
        # Not a real context manager - just emits [ and ]
        self.move_to(cell)
        self.emit('[')

    def end_loop(self, cell):
        """End a loop (emit ] at cell)."""
        self.move_to(cell)
        self.emit(']')

    def comment(self, text):
        """Emit a comment (non-BF chars are ignored by interpreter)."""
        # Only emit safe characters that aren't BF instructions
        safe = ''.join(c for c in text if c not in '><+-.,[]')
        if safe:
            self.emit(f' {safe} ')

    def add_to(self, src, dst, tmp=None):
        """Add src to dst (destructive to src). dst += src; src = 0."""
        self.move_to(src)
        self.emit('[')
        self.move_to(dst)
        self.emit('+')
        self.move_to(src)
        self.emit('-')
        self.emit(']')

    def copy_to(self, src, dst, tmp):
        """Copy src to dst using tmp. All of dst, tmp assumed 0 initially."""
        self.clear(dst)
        self.clear(tmp)
        # src -> dst + tmp
        self.move_to(src)
        self.emit('[')
        self.move_to(dst)
        self.emit('+')
        self.move_to(tmp)
        self.emit('+')
        self.move_to(src)
        self.emit('-')
        self.emit(']')
        # tmp -> src (restore)
        self.move_to(tmp)
        self.emit('[')
        self.move_to(src)
        self.emit('+')
        self.move_to(tmp)
        self.emit('-')
        self.emit(']')

    def move_cell(self, src, dst):
        """Move src to dst (destructive). dst += src; src = 0.
        Assumes dst is already 0."""
        self.move_to(src)
        self.emit('[')
        self.move_to(dst)
        self.emit('+')
        self.move_to(src)
        self.emit('-')
        self.emit(']')

    def print_char(self, char_val):
        """Print a specific ASCII character using a temp cell."""
        t = 229  # Dedicated print temp cell (between INPUT_LEN=228 and SCRATCH=230)
        self.set_cell(t, char_val)
        self.output(t)

    def print_string(self, s):
        """Print a string literal."""
        t = 229  # Dedicated print temp cell
        self.clear(t)
        current_val = 0
        for ch in s:
            target = ord(ch)
            diff = (target - current_val) % 256
            if diff <= 128:
                self.move_to(t)
                self.emit('+' * diff)
            else:
                self.move_to(t)
                self.emit('-' * (256 - diff))
            current_val = target
            self.output(t)

    def move_stride(self, src_off, stride):
        """Destructive move: cell[ptr+src_off] -> cell[ptr+src_off+stride].
        Assumes destination is already 0. Leaves ptr unchanged (conceptually).
        src_off is relative to current self.ptr."""
        abs_src = self.ptr + src_off
        abs_dst = abs_src + stride
        self.move_to(abs_src)
        self.emit('[')
        self.move_to(abs_dst)
        self.emit('+')
        self.move_to(abs_src)
        self.emit('-')
        self.emit(']')

    def get_output(self):
        """Return the complete BF program as a string."""
        return ''.join(self.code)

    def output_size(self):
        """Return current code size."""
        return sum(len(c) for c in self.code)
