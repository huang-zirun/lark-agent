from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pipeline import PipelineTemplate
from app.models.stage import StageDefinition
from app.shared.ids import generate_id
from app.shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TEMPLATE_ID = "feature_delivery_default"

DEFAULT_STAGES = [
    {
        "key": "requirement_analysis",
        "name": "Requirement Analysis",
        "stage_type": "agent",
        "order_index": 0,
        "depends_on": None,
        "agent_profile_id": "requirement_agent",
        "approve_target": None,
        "reject_target": None,
    },
    {
        "key": "solution_design",
        "name": "Solution Design",
        "stage_type": "agent",
        "order_index": 1,
        "depends_on": "requirement_analysis",
        "agent_profile_id": "design_agent",
        "approve_target": None,
        "reject_target": None,
    },
    {
        "key": "checkpoint_design_approval",
        "name": "Design Approval Checkpoint",
        "stage_type": "checkpoint",
        "order_index": 2,
        "depends_on": "solution_design",
        "agent_profile_id": None,
        "approve_target": "code_generation",
        "reject_target": "solution_design",
    },
    {
        "key": "code_generation",
        "name": "Code Generation",
        "stage_type": "agent",
        "order_index": 3,
        "depends_on": "checkpoint_design_approval",
        "agent_profile_id": "code_patch_agent",
        "approve_target": None,
        "reject_target": None,
    },
    {
        "key": "test_generation_and_execution",
        "name": "Test Generation & Execution",
        "stage_type": "agent",
        "order_index": 4,
        "depends_on": "code_generation",
        "agent_profile_id": "test_agent",
        "approve_target": None,
        "reject_target": None,
    },
    {
        "key": "code_review",
        "name": "Code Review",
        "stage_type": "agent",
        "order_index": 5,
        "depends_on": "test_generation_and_execution",
        "agent_profile_id": "review_agent",
        "approve_target": None,
        "reject_target": None,
    },
    {
        "key": "checkpoint_final_approval",
        "name": "Final Approval Checkpoint",
        "stage_type": "checkpoint",
        "order_index": 6,
        "depends_on": "code_review",
        "agent_profile_id": None,
        "approve_target": "delivery_integration",
        "reject_target": "code_generation",
    },
    {
        "key": "delivery_integration",
        "name": "Delivery Integration",
        "stage_type": "agent",
        "order_index": 7,
        "depends_on": "checkpoint_final_approval",
        "agent_profile_id": "delivery_agent",
        "approve_target": None,
        "reject_target": None,
    },
]


async def ensure_default_template(session: AsyncSession):
    result = await session.execute(
        select(PipelineTemplate).where(PipelineTemplate.id == DEFAULT_TEMPLATE_ID)
    )
    template = result.scalar_one_or_none()

    if template:
        logger.info("Default template already exists")
        return

    stage_keys = [s["key"] for s in DEFAULT_STAGES]

    template = PipelineTemplate(
        id=DEFAULT_TEMPLATE_ID,
        name="Feature Delivery Default",
        description="Default pipeline for feature delivery: requirement -> design -> approval -> code -> test -> review -> approval -> delivery",
        version="1.0",
        template_kind="feature_delivery",
        stages={"keys": stage_keys},
        entry_stage_key="requirement_analysis",
        default_provider_id=None,
    )
    session.add(template)

    for stage_def in DEFAULT_STAGES:
        sd = StageDefinition(
            id=generate_id(),
            template_id=DEFAULT_TEMPLATE_ID,
            key=stage_def["key"],
            name=stage_def["name"],
            stage_type=stage_def["stage_type"],
            order_index=stage_def["order_index"],
            depends_on=stage_def["depends_on"],
            agent_profile_id=stage_def["agent_profile_id"],
            approve_target=stage_def["approve_target"],
            reject_target=stage_def["reject_target"],
        )
        session.add(sd)

    await session.flush()
    logger.info(f"Created default template with {len(DEFAULT_STAGES)} stages")


async def get_stage_definitions(session: AsyncSession, template_id: str) -> list[StageDefinition]:
    result = await session.execute(
        select(StageDefinition)
        .where(StageDefinition.template_id == template_id)
        .order_by(StageDefinition.order_index)
    )
    return list(result.scalars().all())


async def get_stage_definition_by_key(session: AsyncSession, template_id: str, stage_key: str) -> StageDefinition | None:
    result = await session.execute(
        select(StageDefinition).where(
            StageDefinition.template_id == template_id,
            StageDefinition.key == stage_key,
        )
    )
    return result.scalar_one_or_none()
