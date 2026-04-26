import pytest

from app.models.pipeline import PipelineRunStatus
from app.models.stage import StageRunStatus
from app.core.pipeline.state_machine import PipelineRunStateMachine, StageRunStateMachine
from app.shared.errors import StateTransitionError


class TestPipelineRunStateMachine:
    def test_valid_transition_draft_to_ready(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.DRAFT, PipelineRunStatus.READY
        )
        assert result == PipelineRunStatus.READY

    def test_valid_transition_ready_to_running(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.READY, PipelineRunStatus.RUNNING
        )
        assert result == PipelineRunStatus.RUNNING

    def test_valid_transition_running_to_waiting_checkpoint(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.RUNNING, PipelineRunStatus.WAITING_CHECKPOINT
        )
        assert result == PipelineRunStatus.WAITING_CHECKPOINT

    def test_valid_transition_running_to_succeeded(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.RUNNING, PipelineRunStatus.SUCCEEDED
        )
        assert result == PipelineRunStatus.SUCCEEDED

    def test_valid_transition_running_to_failed(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.RUNNING, PipelineRunStatus.FAILED
        )
        assert result == PipelineRunStatus.FAILED

    def test_valid_transition_waiting_checkpoint_to_running(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.WAITING_CHECKPOINT, PipelineRunStatus.RUNNING
        )
        assert result == PipelineRunStatus.RUNNING

    def test_valid_transition_running_to_paused(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.RUNNING, PipelineRunStatus.PAUSED
        )
        assert result == PipelineRunStatus.PAUSED

    def test_valid_transition_paused_to_running(self):
        result = PipelineRunStateMachine.transition(
            PipelineRunStatus.PAUSED, PipelineRunStatus.RUNNING
        )
        assert result == PipelineRunStatus.RUNNING

    def test_invalid_transition_draft_to_running(self):
        with pytest.raises(StateTransitionError):
            PipelineRunStateMachine.transition(
                PipelineRunStatus.DRAFT, PipelineRunStatus.RUNNING
            )

    def test_invalid_transition_succeeded_to_running(self):
        with pytest.raises(StateTransitionError):
            PipelineRunStateMachine.transition(
                PipelineRunStatus.SUCCEEDED, PipelineRunStatus.RUNNING
            )

    def test_invalid_transition_failed_to_running(self):
        with pytest.raises(StateTransitionError):
            PipelineRunStateMachine.transition(
                PipelineRunStatus.FAILED, PipelineRunStatus.RUNNING
            )

    def test_can_transition_valid(self):
        assert PipelineRunStateMachine.can_transition(
            PipelineRunStatus.DRAFT, PipelineRunStatus.READY
        )

    def test_can_transition_invalid(self):
        assert not PipelineRunStateMachine.can_transition(
            PipelineRunStatus.DRAFT, PipelineRunStatus.RUNNING
        )


class TestStageRunStateMachine:
    def test_valid_transition_pending_to_running(self):
        result = StageRunStateMachine.transition(
            StageRunStatus.PENDING, StageRunStatus.RUNNING
        )
        assert result == StageRunStatus.RUNNING

    def test_valid_transition_running_to_succeeded(self):
        result = StageRunStateMachine.transition(
            StageRunStatus.RUNNING, StageRunStatus.SUCCEEDED
        )
        assert result == StageRunStatus.SUCCEEDED

    def test_valid_transition_running_to_failed(self):
        result = StageRunStateMachine.transition(
            StageRunStatus.RUNNING, StageRunStatus.FAILED
        )
        assert result == StageRunStatus.FAILED

    def test_valid_transition_failed_to_retrying(self):
        result = StageRunStateMachine.transition(
            StageRunStatus.FAILED, StageRunStatus.RETRYING
        )
        assert result == StageRunStatus.RETRYING

    def test_valid_transition_retrying_to_running(self):
        result = StageRunStateMachine.transition(
            StageRunStatus.RETRYING, StageRunStatus.RUNNING
        )
        assert result == StageRunStatus.RUNNING

    def test_invalid_transition_succeeded_to_running(self):
        with pytest.raises(StateTransitionError):
            StageRunStateMachine.transition(
                StageRunStatus.SUCCEEDED, StageRunStatus.RUNNING
            )

    def test_invalid_transition_pending_to_succeeded(self):
        with pytest.raises(StateTransitionError):
            StageRunStateMachine.transition(
                StageRunStatus.PENDING, StageRunStatus.SUCCEEDED
            )
