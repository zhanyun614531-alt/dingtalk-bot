from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import hmac
import hashlib
import base64
import urllib.parse
import json
import requests
import os
import time
import logging
import re
import agent_tools
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import asyncio
from contextlib import asynccontextmanager

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)
app_logger = logging.getLogger("dingtalk-bot")

# 线程池执行器
thread_pool = ThreadPoolExecutor(max_workers=5)

# 存储处理中的任务
processing_tasks = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期事件管理器"""
    # 启动时执行的操作
    app_logger.info("🚀 钉钉机器人服务启动中...")
    yield
    # 关闭时执行的操作
    app_logger.info("🛑 钉钉机器人服务关闭中...")
    thread_pool.shutdown(wait=True)
    app_logger.info("✅ 线程池已关闭")

# 初始化FastAPI应用
app = FastAPI(
    title="钉钉机器人服务",
    description="基于FastAPI的钉钉机器人智能助手",
    version="1.0.0",
    lifespan=lifespan
)

# 从环境变量获取钉钉机器人信息
ROBOT_ACCESS_TOKEN = os.getenv('ROBOT_ACCESS_TOKEN')
ROBOT_SECRET = os.getenv('ROBOT_SECRET')

def sync_llm_processing(conversation_id, user_input, at_user_ids):
    """同步处理LLM任务（在线程中运行）"""
    try:
        app_logger.info(f"开始处理LLM请求: {user_input}")
        
        ark_key = os.environ.get('ARK_API_KEY')
        if not ark_key:
            error_msg = "Test1：ARK_API_KEY未设置"
            asyncio.run(send_official_message(error_msg, at_user_ids=at_user_ids))
            return

        result = agent_tools.smart_assistant(user_input)
        
        if result:
            final_result = f"Test1：{result}"
            asyncio.run(send_official_message(final_result, at_user_ids=at_user_ids))
        else:
            error_msg = "Test1：LLM返回了空内容"
            asyncio.run(send_official_message(error_msg, at_user_ids=at_user_ids))
            
    except Exception as e:
        error_msg = f"Test1：处理出错: {str(e)}"
        app_logger.error(f"LLM处理错误: {error_msg}")
        asyncio.run(send_official_message(error_msg, at_user_ids=at_user_ids))
    finally:
        if conversation_id in processing_tasks:
            del processing_tasks[conversation_id]

async def async_process_llm_message(conversation_id, user_input, at_user_ids):
    """异步包装器，在线程池中运行同步任务"""
    loop = asyncio.get_event_loop()
    
    processing_tasks[conversation_id] = {
        "start_time": time.time(),
        "user_input": user_input
    }
    
    await loop.run_in_executor(
        thread_pool, 
        sync_llm_processing, 
        conversation_id, user_input, at_user_ids
    )

async def send_official_message(msg, at_user_ids=None, at_mobiles=None, is_at_all=False):
    """发送钉钉消息"""
    try:
        timestamp = str(round(time.time() * 1000))
        
        robot_token = os.environ.get('ROBOT_ACCESS_TOKEN')
        robot_secret = os.environ.get('ROBOT_SECRET')
        
        if not robot_token or not robot_secret:
            return False

        string_to_sign = f"{timestamp}\n{robot_secret}"
        hmac_code = hmac.new(
            robot_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

        url = f'https://oapi.dingtalk.com/robot/send?access_token={robot_token}&timestamp={timestamp}&sign={sign}'

        body = {
            "at": {
                "isAtAll": is_at_all,
                "atUserIds": at_user_ids or [],
                "atMobiles": at_mobiles or []
            },
            "text": {
                "content": msg
            },
            "msgtype": "text"
        }

        headers = {'Content-Type': 'application/json'}
        
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, 
            lambda: requests.post(url, json=body, headers=headers, timeout=10)
        )
        
        if resp.status_code == 200:
            result = resp.json()
            return result.get('errcode') == 0
        else:
            app_logger.warning(f"钉钉API响应异常: {resp.status_code} - {resp.text}")
            return False
            
    except Exception as e:
        app_logger.error(f"发送消息异常: {e}")
        return False

def process_command(command):
    """处理用户指令"""
    original_msg = command.strip()
    key = "Test1"
    raw_command = re.sub(re.escape(key), '', original_msg)
    command = re.sub(r'\s', '', raw_command)
    
    if not command:
        return "Test1：请发送具体指令哦~ 支持的指令：\n- LLM"
    elif command == '时间':
        return f"Test1：当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    elif command.startswith("LLM"):
        try:
            pure_command = re.sub(r'^LLM', '', command).strip()
            response = agent_tools.smart_assistant(pure_command)
            
            if response is None:
                return "Test1：LLM处理超时或无响应"
            elif not response.strip():
                return "Test1：LLM返回了空内容"
            else:
                return f"Test1：{response}"
                
        except Exception as e:
            return f"Test1：LLM处理出错: {str(e)}"
    else:
        return f"Test1：暂不支持该指令：{command}"

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def home():
    return "钉钉机器人服务运行中 ✅"

@app.get("/health")
async def health():
    """健康检查端点"""
    health_status = {
        "status": "healthy",
        "service": "dingtalk-bot",
        "timestamp": time.time(),
        "active_tasks": len(processing_tasks),
        "environment": "production",
        "version": "1.0.0"
    }
    return JSONResponse(health_status)

@app.api_route("/dingtalk/webhook", methods=["GET", "POST"])
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """钉钉消息接收接口"""
    if request.method == "GET":
        return JSONResponse({"status": "服务运行中"})
    
    try:
        data = await request.json()
        app_logger.info(f"收到钉钉消息: {data}")

        if 'text' in data and 'content' in data['text']:
            raw_content = data['text']['content'].strip()
            command = re.sub(r'<at id=".*?">@.*?</at>', '', raw_content).strip()
            
            conversation_id = data.get('conversationId', 'unknown')
            at_user_ids = [user['dingtalkId'] for user in data.get('atUsers', [])]

            if not command.startswith("Test1 LLM"):
                result = process_command(command)
                await send_official_message(result, at_user_ids=at_user_ids)
                return JSONResponse({"success": True})
            else:
                immediate_response = "Test1：正在思考中，请稍等片刻... ⏳"
                await send_official_message(immediate_response, at_user_ids=at_user_ids)
                
                pure_command = re.sub(r'^Test1\s*LLM\s*', '', command).strip()
                
                background_tasks.add_task(
                    async_process_llm_message, 
                    conversation_id, 
                    pure_command, 
                    at_user_ids
                )
                
                return JSONResponse({"success": True, "status": "processing"})

        return JSONResponse({"success": True})

    except Exception as e:
        app_logger.error(f"处理webhook请求出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理请求出错: {str(e)}")

@app.get("/debug/tasks")
async def debug_tasks():
    """调试接口：查看当前处理中的任务"""
    now = time.time()
    active_tasks = {}
    
    for task_id, task_info in processing_tasks.items():
        duration = now - task_info['start_time']
        active_tasks[task_id] = {
            "user_input": task_info['user_input'],
            "duration_seconds": round(duration, 1),
            "status": "running" if duration < 300 else "stuck"
        }
    
    return JSONResponse({
        "active_tasks_count": len(active_tasks),
        "server_time": now,
        "active_tasks": active_tasks
    })

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('DINGTALK_PORT', 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        workers=1,
        reload=False
    )
