"""
Higher-level BF patterns: compare, if/else, switch, multi-way dispatch.

All patterns use the BFEmitter's pointer tracking and temp cells.
"""

from bf_memory import TEMP


def if_nonzero(e, cell, body_fn, tmp=None):
    """
    Execute body_fn if cell is nonzero. Destroys cell.

    Pattern: cell [ body; cell [-] ]
    """
    e.move_to(cell)
    e.emit('[')
    body_fn(e)
    e.clear(cell)
    e.move_to(cell)
    e.emit(']')


def if_zero(e, cell, body_fn, tmp=None):
    """
    Execute body_fn if cell is zero.
    Uses tmp (defaults to TEMP+0). Destroys cell and tmp.

    Pattern:
      tmp = 1
      cell [ tmp = 0; cell [-] ]
      tmp [ body; tmp [-] ]
    """
    if tmp is None:
        tmp = TEMP + 0
    e.set_cell(tmp, 1)
    e.move_to(cell)
    e.emit('[')
    e.clear(tmp)
    e.clear(cell)
    e.move_to(cell)
    e.emit(']')
    e.move_to(tmp)
    e.emit('[')
    body_fn(e)
    e.clear(tmp)
    e.move_to(tmp)
    e.emit(']')


def if_else(e, cell, if_fn, else_fn, tmp=None):
    """
    If cell nonzero: run if_fn. Else: run else_fn.
    Uses tmp. Destroys cell and tmp.
    """
    if tmp is None:
        tmp = TEMP + 0
    e.set_cell(tmp, 1)
    e.move_to(cell)
    e.emit('[')
    if_fn(e)
    e.clear(tmp)
    e.clear(cell)
    e.move_to(cell)
    e.emit(']')
    e.move_to(tmp)
    e.emit('[')
    else_fn(e)
    e.clear(tmp)
    e.move_to(tmp)
    e.emit(']')


def compare_eq(e, val_cell, target_val, result_cell, tmp):
    """
    Set result_cell to 1 if val_cell == target_val, else 0.
    Destroys tmp. Preserves val_cell via copy.

    Strategy: copy val_cell to tmp, subtract target_val,
    if tmp is 0 -> result=1.
    """
    # Copy val_cell to result_cell via tmp
    e.copy_to(val_cell, result_cell, tmp)
    # result_cell now has val_cell's value
    # Subtract target
    if target_val > 0:
        e.dec(result_cell, target_val)
    # Now result_cell is 0 if equal, nonzero otherwise
    # We need to invert: 1 if was zero, 0 if was nonzero
    e.clear(tmp)
    e.set_cell(tmp, 1)
    e.move_to(result_cell)
    e.emit('[')  # if result_cell nonzero (not equal)
    e.clear(tmp)  # tmp = 0
    e.clear(result_cell)
    e.move_to(result_cell)
    e.emit(']')
    # tmp has 1 if equal, 0 if not
    e.move_cell(tmp, result_cell)


def subtract_val(e, cell, val):
    """Subtract a constant value from a cell."""
    if val > 0:
        e.move_to(cell)
        e.emit('-' * (val % 256))


def switch_on_value(e, val_cell, cases, default_fn=None, tmp1=None, tmp2=None, tmp3=None):
    """
    Switch-like dispatch on val_cell's value.

    cases: dict mapping int values to callables (fn(e))
    default_fn: called if no case matches (optional)

    Strategy: for each case value, check equality and branch.
    Uses a 'handled' flag to skip remaining cases.

    Destroys val_cell, tmp1, tmp2, tmp3.
    """
    if tmp1 is None:
        tmp1 = TEMP + 1
    if tmp2 is None:
        tmp2 = TEMP + 2
    if tmp3 is None:
        tmp3 = TEMP + 3

    handled = tmp3

    e.clear(handled)

    for case_val, case_fn in cases.items():
        # Check if already handled
        # tmp1 = (val_cell == case_val) ? 1 : 0
        compare_eq(e, val_cell, case_val, tmp1, tmp2)
        # Only execute if tmp1==1 AND handled==0
        # Check handled==0: tmp2 = 1-handled (if handled is 0, tmp2=1)
        e.copy_to(handled, tmp2, TEMP + 4)
        # Invert tmp2: if 0->1, if nonzero->0
        e.clear(TEMP + 4)
        e.set_cell(TEMP + 4, 1)
        e.move_to(tmp2)
        e.emit('[')
        e.clear(TEMP + 4)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')
        e.move_cell(TEMP + 4, tmp2)
        # tmp2 = 1 if not handled, 0 if handled
        # Now AND: tmp1 AND tmp2
        # If both are 1, execute. Simple: decrement both, check sum==0 trick
        # Simpler: if tmp1 nonzero, check tmp2
        e.move_to(tmp1)
        e.emit('[')  # if match
        e.move_to(tmp2)
        e.emit('[')  # if not handled
        case_fn(e)
        e.set_cell(handled, 1)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')

    if default_fn is not None:
        # If handled == 0, run default
        e.copy_to(handled, tmp1, tmp2)
        e.clear(tmp2)
        e.set_cell(tmp2, 1)
        e.move_to(tmp1)
        e.emit('[')
        e.clear(tmp2)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')
        e.move_to(tmp2)
        e.emit('[')
        default_fn(e)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')
