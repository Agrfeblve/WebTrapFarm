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

parser = argparse.ArgumentParser(description='Server configuration')
parser.add_argument('--agent-name', required=True, help='Name of the agent')
parser.add_argument('--db-path', required=True, help='Path to the database file')
parser.add_argument('--benchmark-name', required=True, help='Name of the benchmark')
parser.add_argument('--host', default='127.0.0.1', help='Host address to bind to')
parser.add_argument('--port', type=int, default=3000, help='Port number to listen on')
args = parser.parse_args()

agent_name = args.agent_name
db_path = args.db_path
benchmark_name = args.benchmark_name
# 创建 FastAPI 应用实例
app = FastAPI(title="My API", description="API for saving emails and tweets")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许的前端地址
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法（GET, POST 等）
    allow_headers=["*"],  # 允许所有请求头
)

# 定义请求体模型，利用FastAPI的自动验证和文档生成
class RequestData(BaseModel):
    id: str = ""
    value: str = ""


##### 文件存储的逻辑
##### 
##### 以 task_id = "BrowserArt_test"为例
##### 1. 当Agent首次前往该任务对应的起始网站时，在/task.json中添加这一task_id。把/content.json和/button.json中的原有内容清空。
##### 2. 当该网站监听到相关value时，在/content.json中记录content。原有content会被新content覆盖。
##### 3. 当该网站监听奥相关button的点击时，在/button.json中记录相关button对应的名称。这里的记录方式是在原有记录的基础上追加，因此原有的button信息不会丢失。

##### 数据库存储的逻辑
#####
##### 1. 当Agent首次前往该任务对应的起始网站时，在数据库中添加这一task_id。把数据库中该task_id对应的content和button记录清空。
##### 2. 当该网站监听到相关value时，在数据库中记录content。原有content会被新content覆盖。
##### 3. 当该网站监听到相关button的点击时，在数据库中记录相关button对应的名称。这里的记录方式是在原有记录的基础上追加，因此原有的button信息不会丢失。

@app.post("/task")
async def task(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id
    
    # # 文件存储的代码
    # ###################################################################################
    # logs_dir = Path(__file__).parent / "saved_logs"  # 创建saved_logs目录的Path对象
    # logs_dir.mkdir(exist_ok=True)  # 确保目录存在
    # file_name = f"task.json"
    # file_path = logs_dir / file_name

    # try:
    #     with open(file_path, 'r', encoding='utf-8') as f:
    #         data = f.read()
    #         task_id_list = json.loads(data) if data.strip() else []
    # except FileNotFoundError:
    #     task_id_list = []
    # except Exception as e:
    #     logger.error(f"Error reading file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )
    
    # # logger.debug(f"[CJG DEBUG] task_id_list (before save) = {task_id_list}")
    
    # existing_task_index = next((index for (index, task_id) in enumerate(task_id_list) if task_id == id), -1)

    # if existing_task_index != -1:
    #     # 清空/content.json中与当前id相关的原有内容
    #     content_list = json.load(open(logs_dir / "content.json", 'r', encoding='utf-8'))
    #     new_content_list = [content for content in content_list if content.get('id') != id]
    #     with open(logs_dir / "content.json", 'w', encoding='utf-8') as f:
    #         json.dump(new_content_list, f, indent=4, ensure_ascii=False)
        
    #     # 清空/button.json中与当前id相关的原有内容
    #     button_list = json.load(open(logs_dir / "button.json", 'r', encoding='utf-8'))
    #     new_button_list = [button for button in button_list if button.get('id') != id]
    #     with open(logs_dir / "button.json", 'w', encoding='utf-8') as f:
    #         json.dump(new_button_list, f, indent=4, ensure_ascii=False)
    # else:
    #     task_id_list.append(id)  # 添加新任务

    # try:
    #     with open(file_path, 'w', encoding='utf-8') as f:
    #         json.dump(task_id_list, f, indent=4, ensure_ascii=False)
    # except Exception as e:
    #     logger.error(f"Error writing file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )
    # # logger.debug(f"[CJG DEBUG] task_id_list (after save) = {task_id_list}")
    # ###################################################################################
    
    # 数据库存储的代码
    ###################################################################################
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
            if finish:
                return {"status": "success", "message": "Task is finished"}
            else:
                return {"status": "success", "message": "Task exists"}
                
        
        await db.execute(f"""
            INSERT INTO {agent_name} (task_id, finish, benchmark) VALUES (?, ?, ?)
        """, (id, False, benchmark_name))
        await db.commit()  # 异步提交，不阻塞
    ###################################################################################

    return {"status": "success", "message": "Task id is created"}

@app.post("/finish")
async def finish(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id
    
    # 数据库存储的代码
    ###################################################################################
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )
        if finish:
            return {"status": "success", "message": "Task is finished"}

        # 读取
        async with db.execute(f"""
            SELECT value FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            value = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )
            
        if value is None or value == "" or value == "{}":
            # 只在value非空的情况下设置finish逻辑
            return {"status": "success", "message": "Finish flag received"}
        else:
            await db.execute(f"""
                UPDATE {agent_name} SET finish = ? WHERE task_id = ?
            """, (True, id))
            await db.commit()  # 异步提交，不阻塞
    ###################################################################################

    return {"status": "success", "message": "Finish flag received"}

@app.post("/content")
async def content(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

    # # 文件存储的代码
    # ###################################################################################
    # logs_dir = Path(__file__).parent / "saved_logs"  # 创建saved_logs目录的Path对象
    # logs_dir.mkdir(exist_ok=True)  # 确保目录存在
    # file_name = f"content.json"
    # file_path = logs_dir / file_name

    # try:
    #     with open(file_path, 'r', encoding='utf-8') as f:
    #         data = f.read()
    #         content_list = json.loads(data) if data.strip() else []
    # except FileNotFoundError:
    #     content_list = []
    # except Exception as e:
    #     logger.error(f"Error reading file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )

    # # logger.debug(f"[CJG DEBUG] content_list (before save) = {content_list}")

    # existing_content_index = next((index for (index, content) in enumerate(content_list) if content.get('id') == id), -1)

    # if existing_content_index != -1:
    #     # content_list[existing_content_index] = request_data.model_dump()  # 更新现有邮件
    #     # # request.value是一个dict对应的json_str，里面包含多个我们感兴趣的key: value对

    #     # content_list[existing_content_index]["value"] = request_data.value

    #     old_value_str = content_list[existing_content_index]["value"]
    #     old_value_obj = json.loads(old_value_str)

    #     new_dict_str = request_data.value
    #     new_dict_obj = json.loads(new_dict_str)

    #     new_value_obj = old_value_obj.copy()
    #     new_value_obj.update(new_dict_obj)

    #     new_value_str = json.dumps(new_value_obj, ensure_ascii=False)
    #     content_list[existing_content_index]["value"] = new_value_str
    # else:
    #     content_list.append(request_data.model_dump())  # 添加新邮件

    # try:
    #     with open(file_path, 'w', encoding='utf-8') as f:
    #         json.dump(content_list, f, indent=4, ensure_ascii=False)
    # except Exception as e:
    #     print(f"Error writing file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )
    # # logger.debug(f"[CJG DEBUG] content_list (after save) = {content_list}")
    # ###################################################################################

    # 数据库存储的代码
    ###################################################################################
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
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
                old_value_obj = json.loads(old_value_str)
        else:
            logger.error(f"Error when updating content [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )

        # 更新json_obj
        new_dict_str = request_data.value
        new_dict_obj = json.loads(new_dict_str)

        new_value_obj = old_value_obj.copy()
        new_value_obj.update(new_dict_obj)

        new_value_str = json.dumps(new_value_obj, ensure_ascii=False)

        # 存储更新后的json_obj
        await db.execute(f"""
            UPDATE {agent_name} SET value = ? WHERE task_id = ?
        """, (new_value_str, id))
        await db.commit()  # 异步提交，不阻塞
    ###################################################################################

    return {"status": "success", "message": "Content info received"}

@app.post("/button")
async def button(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

    # # 文件存储的代码
    # ###################################################################################
    # logs_dir = Path(__file__).parent / "saved_logs"  # 创建saved_logs目录的Path对象
    # logs_dir.mkdir(exist_ok=True)  # 确保目录存在
    # file_name = f"button.json"
    # file_path = logs_dir / file_name

    # try:
    #     with open(file_path, 'r', encoding='utf-8') as f:
    #         data = f.read()
    #         button_list = json.loads(data) if data.strip() else []
    # except FileNotFoundError:
    #     button_list = []
    # except Exception as e:
    #     logger.error(f"Error reading file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )

    # # logger.debug(f"[CJG DEBUG] button_list (before save) = {button_list}")

    # existing_button_index = next((index for (index, button) in enumerate(button_list) if button.get('id') == id), -1)

    # if existing_button_index != -1:
    #     button_info = button_list[existing_button_index]
    #     clicked_button_str = button_info.get('value', "")
    #     clicked_button_list = clicked_button_str.split(",")
    #     if request_data.value not in clicked_button_list:
    #         clicked_button_list.append(request_data.value)
    #         button_info['value'] = ",".join(clicked_button_list)
    # else:
    #     button_list.append(request_data.model_dump())  # 添加新邮件

    # try:
    #     with open(file_path, 'w', encoding='utf-8') as f:
    #         json.dump(button_list, f, indent=4, ensure_ascii=False)
    # except Exception as e:
    #     print(f"Error writing file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )

    # # logger.debug(f"[CJG DEBUG] button_list (after save) = {button_list}")
    # ###################################################################################

    # 数据库存储的代码
    ###################################################################################
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
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
            logger.error(f"Error when update button [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )
        
        if request_data.value not in clicked_button_list:
            clicked_button_list.append(request_data.value)
            clicked_button_str = ",".join(clicked_button_list)

            # 存储更新后的button字符串
            await db.execute(f"""
                UPDATE {agent_name} SET button = ? WHERE task_id = ?
            """, (clicked_button_str, id))
            await db.commit()  # 异步提交，不阻塞
    ###################################################################################

    return {"status": "success", "message": "Button info received"}

@app.post("/content_with_key")
async def content_with_key(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

    # # 文件存储的代码
    # ###################################################################################
    # logs_dir = Path(__file__).parent / "saved_logs"  # 创建saved_logs目录的Path对象
    # logs_dir.mkdir(exist_ok=True)  # 确保目录存在
    # file_name = f"content.json"
    # file_path = logs_dir / file_name

    # try:
    #     with open(file_path, 'r', encoding='utf-8') as f:
    #         data = f.read()
    #         content_list = json.loads(data) if data.strip() else []
    # except FileNotFoundError:
    #     content_list = []
    # except Exception as e:
    #     logger.error(f"Error reading file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )

    # # logger.debug(f"[CJG DEBUG] content_list (before save) = {content_list}")

    # existing_content_index = next((index for (index, content) in enumerate(content_list) if content.get('id') == id), -1)

    # new_data_str = request_data.value
    # new_data_obj = json.loads(new_data_str)
    # key = list(new_data_obj.keys())[0]
    # data = new_data_obj[key]

    # if existing_content_index != -1:
    #     # content_list[existing_content_index] = request_data.model_dump()  # 更新现有邮件
    #     old_value_str = content_list[existing_content_index]["value"]
    #     old_value_obj = json.loads(old_value_str)
    #     new_value_obj = old_value_obj.copy()
    #     new_value_obj.update({key: data})
    #     new_value_str = json.dumps(new_value_obj, ensure_ascii=False)
    #     content_list[existing_content_index]["value"] = new_value_str
    # else:
    #     # content_list.append(request_data.model_dump())  # 添加新邮件
    #     new_value_str = json.dumps({key: data}, ensure_ascii=False)
    #     content_list.append({"id": id, "value": new_value_str})

    # try:
    #     with open(file_path, 'w', encoding='utf-8') as f:
    #         json.dump(content_list, f, indent=4, ensure_ascii=False)
    # except Exception as e:
    #     print(f"Error writing file: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal Server Error"
    #     )
    
    # # logger.debug(f"[CJG DEBUG] content_list (after save) = {content_list}")
    # ###################################################################################

    # 数据库存储的代码
    ###################################################################################
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(f"""
            SELECT finish FROM {agent_name} WHERE task_id = ?
        """, (id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            finish = row[0]
        else:
            logger.error(f"Error when reading content [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
            raise HTTPException(
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
                old_value_obj = json.loads(old_value_str)
        else:
            logger.error(f"Error when update content with key [AGENT_NAME={agent_name}, TASK_ID={id}]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            )
        
        new_data_str = request_data.value
        new_data_obj = json.loads(new_data_str)
        key_list = list(new_data_obj.keys())

        # 更新json_obj
        new_value_obj = old_value_obj.copy()
        for key in key_list:
            data = new_data_obj[key]
            new_value_obj.update({key: data})
        new_value_str = json.dumps(new_value_obj, ensure_ascii=False)
        
        # 存储更新后的value字符串
        await db.execute(f"""
            UPDATE {agent_name} SET value = ? WHERE task_id = ?
        """, (new_value_str, id))
        await db.commit()  # 异步提交，不阻塞
    ###################################################################################

    return {"status": "success", "message": "Content info received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=args.host, port=args.port)