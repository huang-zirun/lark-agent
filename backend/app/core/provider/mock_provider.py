from app.shared.logging import get_logger

logger = get_logger(__name__)


class MockProvider:
    async def generate(
        self,
        prompt: str,
        schema: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict | str:
        logger.info("MockProvider.generate called")
        if schema:
            return self._generate_from_schema(schema)
        return "Mock response"

    async def validate(self) -> bool:
        return True

    def _generate_from_schema(self, schema: dict) -> dict:
        result = {}
        if "properties" in schema:
            for key, prop in schema["properties"].items():
                prop_type = prop.get("type", "string")
                if prop_type == "string":
                    result[key] = f"mock_{key}"
                elif prop_type == "integer":
                    result[key] = 0
                elif prop_type == "number":
                    result[key] = 0.0
                elif prop_type == "boolean":
                    result[key] = True
                elif prop_type == "array":
                    result[key] = []
                elif prop_type == "object":
                    result[key] = {}
        return result
