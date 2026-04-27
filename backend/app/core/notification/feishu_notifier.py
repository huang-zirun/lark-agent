import httpx

from app.shared.logging import get_logger

logger = get_logger(__name__)


async def send_delivery_notification(webhook_url: str, delivery_info: dict) -> bool:
    goal = delivery_info.get("goal", "N/A")
    commit_hash = delivery_info.get("commit_hash", "N/A")
    branch_name = delivery_info.get("branch_name", "N/A")
    changed_files = delivery_info.get("changed_files", [])
    test_summary = delivery_info.get("test_summary", "N/A")
    has_changes = delivery_info.get("has_changes", False)

    status_text = "✅ 交付成功" if has_changes else "ℹ️ 无代码变更"
    files_text = f"{len(changed_files)} 个文件" if changed_files else "无"
    short_hash = commit_hash[:8] if commit_hash and commit_hash != "N/A" else "N/A"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"DevFlow Engine 交付通知 - {status_text}",
                },
                "template": "green" if has_changes else "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**需求目标**: {goal}\n**Commit**: `{short_hash}`\n**Branch**: `{branch_name}`\n**变更文件**: {files_text}\n**测试结果**: {test_summary}",
                    },
                },
            ],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=card)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info("Feishu delivery notification sent successfully")
                    return True
                else:
                    logger.warning(f"Feishu API error: {result}")
                    return False
            else:
                logger.warning(f"Feishu webhook HTTP error: {response.status_code}")
                return False
    except Exception as e:
        logger.warning(f"Failed to send Feishu notification: {e}")
        return False
