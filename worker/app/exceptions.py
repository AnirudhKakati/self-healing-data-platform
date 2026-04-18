class InvalidPipelineRunStatus(Exception):
    """Raised when a pipeline run is not in 'queued' status"""
    pass

class UnknownStepTypeError(Exception):
    """Raised when a pipeline step type doesn't have a corresponding execution function"""
    pass