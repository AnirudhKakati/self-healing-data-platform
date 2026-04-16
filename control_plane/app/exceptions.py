class DuplicateStepOrderError(Exception):
    """Raised when a pipeline already has a step with the same step_order."""
    pass