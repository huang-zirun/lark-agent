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
