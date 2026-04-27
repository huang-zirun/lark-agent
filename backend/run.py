#!/usr/bin/env python3
"""DevFlow Engine 启动脚本"""

import uvicorn
from app.shared.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
    )
