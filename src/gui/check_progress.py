"""Progress tracking for the "Start Checks" pipeline.

The check pipeline (see field_checking.py) doesn't have a step count that's
knowable exactly in advance:

- IF/THEN rules only run their nested rules when the condition holds at that
  point in the run, which depends on values entered earlier in the same run.
- CHECK rules can resolve silently (skip_matching_defaults, auto_fill_missing)
  without ever showing a dialog.
- Multi-block runs repeat the whole rule pass per selected block in
  "independent" mode, or run it once with per-block fallbacks only where
  values diverge in "shared" mode.

So `CheckProgressTracker.total` is an *upper-bound estimate*, computed once
at the start of a run by `count_rule_steps` plus one coarse step per data
block for each of the non-rule pipeline phases (data-name validation,
absolute-structure checks, duplicate/alias resolution, audit-method update).
`current` advances once per step actually reached - whether or not it shows
a dialog - so it reliably reaches the total even when some steps resolve
silently. If a run needs more steps than estimated (e.g. a shared-mode
per-block fallback), `total` grows to match rather than letting the display
show something like "61/60".
"""

from __future__ import annotations


def count_rule_steps(fields) -> int:
    """Recursively count the CHECK/CALCULATE/action rules in a rule set.

    An IF block is not itself a step; its `then_fields` are counted
    unconditionally (as if the condition always held), since whether it
    actually will is only known at run time. This makes the result an
    upper bound on how many rule-steps a run can reach, not an exact
    prediction of how many will run.
    """
    total = 0
    for field_def in fields:
        if getattr(field_def, 'action', 'CHECK') == 'IF':
            total += count_rule_steps(getattr(field_def, 'then_fields', None) or [])
        else:
            total += 1
    return total


class CheckProgressTracker:
    """Tracks progress through a single "Start Checks" run.

    Consumers register with `on_change(callback)` to be notified of every
    update as `(current, total)`; the status bar and the per-field check
    dialogs both read from the same tracker so they stay in sync.
    """

    def __init__(self):
        self.total = 0
        self.current = 0
        self._listeners = []

    def on_change(self, callback):
        """Register callback(current, total), invoked on every update."""
        self._listeners.append(callback)

    def reset(self, total: int) -> None:
        """Start a new run (or clear the indicator when total <= 0)."""
        self.total = max(total, 0)
        self.current = 0
        self._notify()

    def advance(self, steps: int = 1) -> None:
        """Record that `steps` more pipeline steps have been reached.

        Grows `total` on the fly if the run needed more steps than the
        initial estimate, so the displayed fraction never exceeds 1.0.
        """
        self.current += steps
        if self.current > self.total:
            self.total = self.current
        self._notify()

    def snapshot(self):
        """Return (current, total) for passing into a dialog's constructor."""
        return (self.current, self.total)

    def _notify(self) -> None:
        for callback in self._listeners:
            callback(self.current, self.total)
