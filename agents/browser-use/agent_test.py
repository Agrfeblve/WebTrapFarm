import asyncio
from datetime import datetime
from pathlib import Path

from config_loader import get_llm_profile
from browser_use import Agent, ChatV3
from browser_use.logging_config import setup_logging


log_dir = Path.cwd() / "cjg_logs"
log_dir.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file_path = log_dir / f"cjg_{timestamp}.log"
print(f"The agent log will be created at: {log_file_path}")

cjg_logger = open(log_file_path, "a", encoding="utf-8")
cjg_logger.flush()

setup_logging(
    debug_log_file=str(log_dir / f"{timestamp}_debug.log"),
    info_log_file=str(log_dir / f"{timestamp}_info.log"),
    force_setup=True,
)


async def main():
    _profile_name, llm_config = get_llm_profile(
        profile_selector="standalone_profile"
    )
    llm = ChatV3(model=llm_config["model"], llm_config=llm_config)
    agent = Agent(task="Search 4399", llm=llm, cjg_logger=cjg_logger)
    await agent.run(max_steps=5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        cjg_logger.close()
