from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
from pathlib import Path
import json
import aiosqlite
import argparse

###########################################################################
# 1. 创建记录器（Logger）
logger = logging.getLogger('my_server')
logger.setLevel(logging.DEBUG)  # 设置记录器级别

# 2. 创建处理器（Handler）- 控制台输出
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)  # 控制台显示DEBUG及以上级别

# 3. 创建处理器（Handler）- 文件输出（支持日志轮换）
from logging import FileHandler
file_handler = FileHandler('server.log')
file_handler.setLevel(logging.DEBUG)  # 文件记录所有DEBUG及以上级别

# 4. 创建格式化器（Formatter）
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# 5. 将处理器添加到记录器
logger.addHandler(console_handler)
logger.addHandler(file_handler)
###########################################################################

# 数据库配置
# db_path = r"result.db"
# agent_name = "human"
# benchmark = "dwd"

parser = argparse.ArgumentParser(description='Server configuration')
parser.add_argument('--agent-name', required=True, help='Name of the agent')
parser.add_argument('--db-path', required=True, help='Path to the database file')
parser.add_argument('--benchmark-name', required=True, help='Name of the benchmark')
parser.add_argument('--host', default='127.0.0.1', help='Host address to bind to')
parser.add_argument('--port', type=int, default=3000, help='Port number to listen on')
args = parser.parse_args()

agent_name = args.agent_name
db_path = args.db_path
benchmark = args.benchmark_name

# 创建 FastAPI 应用实例
app = FastAPI(title="My API", description="API for saving emails and tweets")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法（GET, POST 等）
    allow_headers=["*"],  # 允许所有请求头
)

# 定义请求体模型
class RequestData(BaseModel):
    id: str = ""
    value: str = ""

##### 数据库存储的逻辑说明
#####
##### 1. 当Agent首次前往该任务对应的起始网站时，在数据库中添加这一task_id。把数据库中该task_id对应的content和button记录清空。
##### 2. 当该网站监听到相关value时，在数据库中记录content。原有content会被新content覆盖。
##### 3. 当该网站监听到相关button的点击时，在数据库中记录相关button对应的名称。这里的记录方式是在原有记录的基础上追加，因此原有的button信息不会丢失。

@app.post("/task")
async def task(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id
    
    async with aiosqlite.connect(db_path) as db:
        # 检查任务是否已完成
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            finish = row[0]
            if finish:
                return {"status": "success", "message": "Task is finished"}
            else:
                # 未完成任务 → 清除旧记录
                await db.execute(f"""
                    DELETE FROM {agent_name} WHERE task_id = ?
                """, (id,))

        # ★ 插入包含 benchmark 的新任务记录
        await db.execute(f"""
            INSERT INTO {agent_name} (task_id, benchmark, finish)
            VALUES (?, ?, ?)
        """, (id, benchmark, False))

        await db.commit()

    return {"status": "success", "message": "Task id is created"}

@app.post("/finish")
async def finish(request_data: RequestData):
    id = request_data.id
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # 1. 检查任务是否已完成
            async with db.execute(f"""
                SELECT finish FROM {agent_name} WHERE task_id = ?
            """, (id,)) as cursor:
                row = await cursor.fetchone()

            if not row:
                # 任务ID不存在，或者读取错误（但上下文管理器应清理）
                logger.error(f"Task ID not found or error during initial read [AGENT_NAME={agent_name}, TASK_ID={id}]")
                raise HTTPException(status_code=404, detail="Task ID not found")
            
            finish = row[0]
            if finish:
                return {"status": "success", "message": "Task is finished"}

            # 2. 读取 value
            async with db.execute(f"""
                SELECT value FROM {agent_name} WHERE task_id = ?
            """, (id,)) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                # 逻辑上不应该发生，但作为安全措施
                logger.error(f"Value row not found after initial check [AGENT_NAME={agent_name}, TASK_ID={id}]")
                raise HTTPException(status_code=404, detail="Internal Error: Task value missing")
                
            value = row[0]
                
            if value is None or value == "" or value == "{}":
                return {"status": "success", "message": "Content info received"}
            else:
                # 3. 更新 finish 标记
                await db.execute(f"""
                    UPDATE {agent_name} SET finish = ? WHERE task_id = ?
                """, (True, id))
                await db.commit()  # 异步提交

        return {"status": "success", "message": "Finish flag received"}
        
    except Exception as general_error:
        # 捕获任何未预料到的异常，记录它
        logger.error(f"Unhandled error in /finish for task {id}: {general_error}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error during database operation"
        )

@app.post("/content")
async def content(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

    # 数据库存储的代码
    async with aiosqlite.connect(db_path) as db:
        # 检查任务是否已完成
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: Row not found.")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )
        if finish:
            return {"status": "success", "message": "Task is finished"}

        # 读取原value字符串，解析成json_obj
        async with db.execute(f"""
            SELECT value FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            old_value_str = row[0]
            if old_value_str is None:
                old_value_obj = {}
            else:
                try:
                    old_value_obj = json.loads(old_value_str)
                except json.JSONDecodeError:
                    old_value_obj = {} # 如果旧数据格式错误，则重置
        else:
            logger.error(f"Error when updating content [AGENT_NAME={agent_name}, TASK_ID={id}]: Row not found.")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )

        # 更新json_obj：合并新数据
        try:
            new_dict_str = request_data.value
            new_dict_obj = json.loads(new_dict_str)
        except json.JSONDecodeError:
             logger.error(f"Invalid new content JSON: {new_dict_str}")
             return {"status": "error", "message": "Invalid content JSON"}


        new_value_obj = old_value_obj.copy()
        new_value_obj.update(new_dict_obj)

        new_value_str = json.dumps(new_value_obj, ensure_ascii=False)

        # 存储更新后的json_obj
        await db.execute(f"""
            UPDATE {agent_name} SET value = ? WHERE task_id = ?
        """, (new_value_str, id))
        await db.commit()  # 异步提交，不阻塞

    return {"status": "success", "message": "Content info received"}

@app.post("/button")
async def button(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

    # 数据库存储的代码
    async with aiosqlite.connect(db_path) as db:
        # 检查任务是否已完成
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: Row not found.")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )
        if finish:
            return {"status": "success", "message": "Task is finished"}

        # 读取原button字符串，解析成button_list
        async with db.execute(f"""
            SELECT button FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            clicked_button_str = row[0]
            if clicked_button_str is None:
                clicked_button_list = []
            else:
                clicked_button_list = clicked_button_str.split(",")
        else:
            logger.error(f"Error when update button [AGENT_NAME={agent_name}, TASK_ID={id}]: Row not found.")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )
        
        # 只有新按钮未被记录时才追加
        if request_data.value not in clicked_button_list:
            clicked_button_list.append(request_data.value)
            clicked_button_str = ",".join(clicked_button_list)

            # 存储更新后的button字符串
            await db.execute(f"""
                UPDATE {agent_name} SET button = ? WHERE task_id = ?
            """, (clicked_button_str, id))
            await db.commit()  # 异步提交，不阻塞

    return {"status": "success", "message": "Button info received"}

@app.post("/content_with_key")
async def content_with_key(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

    # 数据库存储的代码
    async with aiosqlite.connect(db_path) as db:
        # 检查任务是否已完成
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: Row not found.")
            raise HTTPbutton(
                status_code=500,
                detail="Internal Server Error"
            )
        if finish:
            return {"status": "success", "message": "Task is finished"}
            
        # 读取原value字符串，解析成value_list
        async with db.execute(f"""
            SELECT value FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            old_value_str = row[0]
            if old_value_str is None:
                old_value_obj = {}
            else:
                try:
                    old_value_obj = json.loads(old_value_str)
                except json.JSONDecodeError:
                    old_value_obj = {} # 如果旧数据格式错误，则重置
        else:
            logger.error(f"Error when update content with key [AGENT_NAME={agent_name}, TASK_ID={id}]: Row not found.")
            raise HTTPbutton(
                status_code=500,
                detail="Internal Server Error"
            )
        
        # 解析新数据
        try:
            new_data_str = request_data.value
            new_data_obj = json.loads(new_data_str)
            key = list(new_data_obj.keys())[0]
            data = new_data_obj[key]
        except (json.JSONDecodeError, IndexError, KeyError):
            logger.error(f"Invalid new content with key JSON: {request_data.value}")
            return {"status": "error", "message": "Invalid content JSON format"}

        # 更新json_obj
        new_value_obj = old_value_obj.copy()
        new_value_obj.update({key: data})
        new_value_str = json.dumps(new_value_obj, ensure_ascii=False)
        
        # 存储更新后的value字符串
        await db.execute(f"""
            UPDATE {agent_name} SET value = ? WHERE task_id = ?
        """, (new_value_str, id))
        await db.commit()  # 异步提交，不阻塞

    return {"status": "success", "message": "Content info received"}

if __name__ == "__main__":
    import uvicorn
    # 使用 argparse 解析出来的 host 和 port
    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)