class DevFlowError(Exception):
    pass


class InputError(DevFlowError):
    pass


class PrecheckError(DevFlowError):
    pass


class ExecutionError(DevFlowError):
    pass


class SystemError(DevFlowError):
    pass


class StateTransitionError(DevFlowError):
    pass


class AuthenticationError(DevFlowError):
    pass


class RateLimitError(DevFlowError):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class OutputValidationError(DevFlowError):
    pass
