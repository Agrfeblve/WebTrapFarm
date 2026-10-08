from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import sys
from pathlib import Path
import json
import aiosqlite
import argparse

logger = logging.getLogger('my_server')
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

from logging import FileHandler
file_handler = FileHandler('server.log')
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

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

app = FastAPI(title="My API", description="API for saving emails and tweets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.mount("/webpages", StaticFiles(directory="../data/webpages_filtered"), name="webpages")

class RequestData(BaseModel):
    id: str = ""
    value: str = ""

@app.post("/task")
async def task(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id
    
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
        await db.commit()

    return {"status": "success", "message": "Task id is created"}

@app.post("/finish")
async def finish(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id
    
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
            return {"status": "success", "message": "Finish flag received"}
        else:
            await db.execute(f"""
                UPDATE {agent_name} SET finish = ? WHERE task_id = ?
            """, (True, id))
            await db.commit()

    return {"status": "success", "message": "Finish flag received"}

@app.post("/content")
async def content(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

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

        new_dict_str = request_data.value
        new_dict_obj = json.loads(new_dict_str)

        new_value_obj = old_value_obj.copy()
        new_value_obj.update(new_dict_obj)

        new_value_str = json.dumps(new_value_obj, ensure_ascii=False)

        await db.execute(f"""
            UPDATE {agent_name} SET value = ? WHERE task_id = ?
        """, (new_value_str, id))
        await db.commit()

    return {"status": "success", "message": "Content info received"}

@app.post("/button")
async def button(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

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

            await db.execute(f"""
                UPDATE {agent_name} SET button = ? WHERE task_id = ?
            """, (clicked_button_str, id))
            await db.commit()

    return {"status": "success", "message": "Button info received"}

@app.post("/content_with_key")
async def content_with_key(request_data: RequestData):
    logger.debug(f"request_data: {request_data}")
    id = request_data.id

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

        new_value_obj = old_value_obj.copy()
        for key in key_list:
            data = new_data_obj[key]
            new_value_obj.update({key: data})
        new_value_str = json.dumps(new_value_obj, ensure_ascii=False)
        
        await db.execute(f"""
            UPDATE {agent_name} SET value = ? WHERE task_id = ?
        """, (new_value_str, id))
        await db.commit()

    return {"status": "success", "message": "Content info received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_server:app", host=args.host, port=args.port)
