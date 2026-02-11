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
# parser.add_argument('--agent-name', required=True, help='Name of the agent')
# parser.add_argument('--db-path', required=True, help='Path to the database file')
# parser.add_argument('--benchmark-name', required=True, help='Name of the benchmark')
parser.add_argument('--host', default='127.0.0.1', help='Host address to bind to')
parser.add_argument('--port', type=int, default=3000, help='Port number to listen on')
args = parser.parse_args()

# agent_name = args.agent_name
# db_path = args.db_path
# benchmark_name = args.benchmark_name

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

app.mount("/", StaticFiles(directory="../websites"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("frontend_server:app", host=args.host, port=args.port)
