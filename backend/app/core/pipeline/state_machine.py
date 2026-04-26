from app.models.pipeline import PipelineRunStatus
from app.models.stage import StageRunStatus
from app.shared.errors import StateTransitionError


PIPELINE_TRANSITIONS = {
    PipelineRunStatus.DRAFT: [PipelineRunStatus.READY],
    PipelineRunStatus.READY: [PipelineRunStatus.RUNNING],
    PipelineRunStatus.RUNNING: [PipelineRunStatus.WAITING_CHECKPOINT, PipelineRunStatus.PAUSED, PipelineRunStatus.SUCCEEDED, PipelineRunStatus.FAILED, PipelineRunStatus.TERMINATED],
    PipelineRunStatus.WAITING_CHECKPOINT: [PipelineRunStatus.RUNNING],
    PipelineRunStatus.PAUSED: [PipelineRunStatus.RUNNING, PipelineRunStatus.TERMINATED],
    PipelineRunStatus.SUCCEEDED: [],
    PipelineRunStatus.FAILED: [],
    PipelineRunStatus.TERMINATED: [],
}

STAGE_TRANSITIONS = {
    StageRunStatus.PENDING: [StageRunStatus.RUNNING, StageRunStatus.SKIPPED],
    StageRunStatus.RUNNING: [StageRunStatus.SUCCEEDED, StageRunStatus.FAILED],
    StageRunStatus.SUCCEEDED: [],
    StageRunStatus.FAILED: [StageRunStatus.RETRYING],
    StageRunStatus.SKIPPED: [],
    StageRunStatus.RETRYING: [StageRunStatus.RUNNING, StageRunStatus.PENDING, StageRunStatus.FAILED],
}


class PipelineRunStateMachine:
    @staticmethod
    def can_transition(current: PipelineRunStatus, target: PipelineRunStatus) -> bool:
        return target in PIPELINE_TRANSITIONS.get(current, [])

    @staticmethod
    def transition(current: PipelineRunStatus, target: PipelineRunStatus) -> PipelineRunStatus:
        if not PipelineRunStateMachine.can_transition(current, target):
            raise StateTransitionError(
                f"Invalid transition: {current.value} -> {target.value}"
            )
        return target


class StageRunStateMachine:
    @staticmethod
    def can_transition(current: StageRunStatus, target: StageRunStatus) -> bool:
        return target in STAGE_TRANSITIONS.get(current, [])

    @staticmethod
    def transition(current: StageRunStatus, target: StageRunStatus) -> StageRunStatus:
        if not StageRunStateMachine.can_transition(current, target):
            raise StateTransitionError(
                f"Invalid stage transition: {current.value} -> {target.value}"
            )
        return target
