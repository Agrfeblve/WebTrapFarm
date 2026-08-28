import argparse
import asyncio

from config_loader import get_llm_profile, load_app_config

# Import browser_use only after config_loader has populated legacy provider settings.
from browser_use import Agent, BrowserProfile, ChatV3
from browser_use.logging_config import setup_logging


def _vision_setting(value):
    normalized = str(value).lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    if normalized == "auto":
        return "auto"
    raise ValueError("runtime.use_vision must be true, false, or auto")


async def main(
    prompt,
    starting_website,
    max_steps,
    cjg_logger_dir,
    cjg_task_id,
    no_dom_filter=False,
):
    app_config = load_app_config()
    runtime_config = app_config["runtime"]
    llm_name, llm_config = get_llm_profile()
    use_vision_name = str(runtime_config["use_vision"]).lower()
    use_vision = _vision_setting(use_vision_name)
    seaweedfs_root_dir = app_config["seaweedfs"]["root_dir"]

    # Record execution logs under the task logger directory.
    print(f"[CJG_DEBUG] cjg_logger_dir: {cjg_logger_dir}")
    setup_logging(
        debug_log_file=f"{cjg_logger_dir}/debug.log",
        info_log_file=f"{cjg_logger_dir}/info.log",
        force_setup=True,
    )

    llm = ChatV3(model=llm_config["model"], llm_config=llm_config)
    browser_profile = BrowserProfile(no_dom_filter=no_dom_filter)
    agent = Agent(
        task=prompt,
        llm=llm,
        browser_profile=browser_profile,
        cjg_logger_dir=cjg_logger_dir,
        use_vision=use_vision,
        starting_website=starting_website,
    )
    await agent.run(
        max_steps=max_steps,
        cjg_logger_dir=cjg_logger_dir,
        cjg_task_id=cjg_task_id,
        cjg_llm=llm_name,
        cjg_use_vision=use_vision_name,
        seaweedfs_root_dir=seaweedfs_root_dir,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, default="Search 4399", help="Task prompt")
    parser.add_argument("--max_steps", type=int, default=5, help="Maximum agent steps")
    parser.add_argument(
        "--cjg_logger_dir",
        type=str,
        default="cjg_logs",
        help="Task log directory",
    )
    parser.add_argument(
        "--starting_website",
        type=str,
        default="",
        help="Starting website URL",
    )
    parser.add_argument("--task_id", type=str, default="", help="Task ID")
    parser.add_argument(
        "--no-dom-filter",
        action="store_true",
        help="Pass the complete, unfiltered DOM representation to the agent",
    )
    args = parser.parse_args()

    runtime_no_dom_filter = bool(
        load_app_config()["runtime"].get("no_dom_filter", False)
    )
    asyncio.run(
        main(
            args.prompt,
            args.starting_website,
            args.max_steps,
            args.cjg_logger_dir,
            args.task_id,
            args.no_dom_filter or runtime_no_dom_filter,
        )
    )
