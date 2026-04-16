class DuplicateStepOrderError(Exception):
    """Raised when a pipeline already has a step with the same step_order."""
    pass

class DuplicateScheduleError(Exception):
    """Raised when pipeline already has a schedule"""
    pass