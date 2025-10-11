from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from qiniu import Auth, put_data, etag
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
import uuid
from datetime import datetime

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

# 临时存储PDF文件（在生产环境中应该使用持久化存储）
pdf_storage = {}


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


def generate_dingtalk_signature(timestamp: str, secret: str) -> str:
    """生成钉钉机器人签名"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code))


# async def upload_file_to_dingtalk(file_data: bytes, file_name: str, file_type: str = "file") -> Dict[str, Any]:
#     """
#     上传文件到钉钉服务器并获取media_id
#
#     参数:
#     - file_data: 文件二进制数据
#     - file_name: 文件名
#     - file_type: 文件类型 (image, voice, file)
#
#     返回:
#     - 包含media_id的字典或错误信息
#     """
#     try:
#         timestamp = str(round(time.time() * 1000))
#         sign = generate_dingtalk_signature(timestamp, ROBOT_SECRET)
#
#         upload_url = f'https://oapi.dingtalk.com/robot/upload?access_token={ROBOT_ACCESS_TOKEN}&timestamp={timestamp}&sign={sign}'
#
#         # 准备文件上传
#         files = {
#             'media': (file_name, file_data, 'application/pdf')
#         }
#
#         data = {
#             'type': file_type
#         }
#
#         loop = asyncio.get_event_loop()
#         response = await loop.run_in_executor(
#             None,
#             lambda: requests.post(upload_url, files=files, data=data, timeout=30)
#         )
#
#         if response.status_code == 200:
#             result = response.json()
#             if result.get('errcode') == 0:
#                 app_logger.info(f"✅ 文件上传成功: {file_name}, media_id: {result.get('media_id')}")
#                 return {
#                     "success": True,
#                     "media_id": result.get('media_id'),
#                     "created_at": result.get('created_at')
#                 }
#             else:
#                 app_logger.error(f"❌ 文件上传失败: {result}")
#                 return {
#                     "success": False,
#                     "error": f"上传失败: {result.get('errmsg', '未知错误')}"
#                 }
#         else:
#             app_logger.error(f"❌ 文件上传HTTP错误: {response.status_code}")
#             return {
#                 "success": False,
#                 "error": f"HTTP错误: {response.status_code}"
#             }
#
#     except Exception as e:
#         app_logger.error(f"❌ 文件上传异常: {str(e)}")
#         return {
#             "success": False,
#             "error": f"上传异常: {str(e)}"
#         }


# async def send_file_message(media_id: str, file_name: str, at_user_ids=None, at_mobiles=None, is_at_all=False):
#     """发送钉钉文件消息"""
#     try:
#         timestamp = str(round(time.time() * 1000))
#         sign = generate_dingtalk_signature(timestamp, ROBOT_SECRET)
#
#         url = f'https://oapi.dingtalk.com/robot/send?access_token={ROBOT_ACCESS_TOKEN}&timestamp={timestamp}&sign={sign}'
#
#         body = {
#             "at": {
#                 "isAtAll": is_at_all,
#                 "atUserIds": at_user_ids or [],
#                 "atMobiles": at_mobiles or []
#             },
#             "file": {
#                 "media_id": media_id
#             },
#             "msgtype": "file"
#         }
#
#         headers = {'Content-Type': 'application/json'}
#
#         loop = asyncio.get_event_loop()
#         resp = await loop.run_in_executor(
#             None,
#             lambda: requests.post(url, json=body, headers=headers, timeout=10)
#         )
#
#         if resp.status_code == 200:
#             result = resp.json()
#             if result.get('errcode') == 0:
#                 app_logger.info(f"✅ 文件消息发送成功: {file_name}")
#                 return True
#             else:
#                 app_logger.warning(f"❌ 文件消息发送失败: {result}")
#                 return False
#         else:
#             app_logger.warning(f"❌ 文件消息API响应异常: {resp.status_code} - {resp.text}")
#             return False
#
#     except Exception as e:
#         app_logger.error(f"❌ 发送文件消息异常: {e}")
#         return False


# async def send_pdf_via_dingtalk(pdf_binary: bytes, stock_name: str, at_user_ids=None):
#     """
#     通过钉钉发送PDF文件
#
#     参数:
#     - pdf_binary: PDF二进制数据
#     - stock_name: 股票名称（用于文件名）
#     - at_user_ids: 需要@的用户ID列表
#     """
#     try:
#         # 生成文件名
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         file_name = f"Stock_Analysis_Report_{stock_name}_{timestamp}.pdf"
#
#         app_logger.info(f"📤 开始上传PDF文件: {file_name}, 大小: {len(pdf_binary)} 字节")
#
#         # 第一步：上传文件到钉钉服务器
#         upload_result = await upload_file_to_dingtalk(pdf_binary, file_name, "file")
#
#         if not upload_result["success"]:
#             error_msg = f"❌ PDF文件上传失败: {upload_result.get('error', '未知错误')}"
#             await send_official_message(error_msg, at_user_ids=at_user_ids)
#             return False
#
#         # 第二步：发送文件消息
#         media_id = upload_result["media_id"]
#         send_success = await send_file_message(media_id, file_name, at_user_ids=at_user_ids)
#
#         if send_success:
#             success_msg = f"✅ 股票分析报告已生成并发送\n📈 股票: {stock_name}\n📄 文件名: {file_name}"
#             await send_official_message(success_msg, at_user_ids=at_user_ids)
#             return True
#         else:
#             error_msg = f"❌ 文件消息发送失败，但文件已上传 (media_id: {media_id})"
#             await send_official_message(error_msg, at_user_ids=at_user_ids)
#             return False
#
#     except Exception as e:
#         error_msg = f"❌ 发送PDF文件时出错: {str(e)}"
#         app_logger.error(error_msg)
#         await send_official_message(error_msg, at_user_ids=at_user_ids)
#         return False

async def upload_file_to_Qiniu(pdf_binary: bytes, stock_name: str, at_user_ids=None):
    """
    上传PDF二进制数据到七牛云
    :param pdf_binary_data: PDF文件的二进制数据
    :param stock_name: 股票名称
    :return: 上传成功返回文件的公开访问URL，失败返回None
    """
    # 初始化七牛云上传器
    access_key = os.environ.get("Qiniu_ACCESS_KEY").strip()
    secret_key = os.environ.get("Qiniu_SECRET_KEY").strip()
    bucket_name = os.environ.get("Qiniu_BUCKET_NAME").strip()
    domain = os.environ.get("Qiniu_DOMAIN").strip()
    q = Auth(access_key, secret_key)
    try:
        # 检查二进制数据是否为空
        if not pdf_binary:
            print("错误：PDF二进制数据为空")
            return None

        timestamp = datetime.now().strftime("%Y%m%d")
        remote_file_name = f"股票分析报告_{stock_name}_{timestamp}.pdf"

        # 简单验证PDF文件头（可选，但推荐）
        pdf_header = b'%PDF-'
        if not pdf_binary.startswith(pdf_header):
            print("警告：提供的二进制数据可能不是有效的PDF文件")

        # 生成上传Token
        token = q.upload_token(bucket_name, remote_file_name,
                                    3600)

        # 执行上传（使用put_data上传二进制数据）
        ret, info = put_data(token, remote_file_name, pdf_binary)

        # 检查上传结果
        if ret is not None and ret['key'] == remote_file_name:
            # 生成公开访问URL
            file_url = f"Test1: 文件上传成功！访问链接：http://{domain}/{remote_file_name}"
            print(f"文件上传成功！访问链接：http://{domain}/{remote_file_name}")
            await send_official_message(file_url, at_user_ids=at_user_ids)
            return True
        else:
            print(f"文件上传失败：{info}")
            return None
    except Exception as e:
        print(f"上传过程中发生错误：{str(e)}")
        return None

async def sync_llm_processing(conversation_id, user_input, at_user_ids):
    """同步处理LLM任务（在线程中运行）"""
    try:
        app_logger.info(f"开始处理LLM请求: {user_input}")

        ark_key = os.environ.get('ARK_API_KEY')
        if not ark_key:
            error_msg = "Test1：ARK_API_KEY未设置"
            await send_official_message(error_msg, at_user_ids=at_user_ids)
            return

        # 正确等待异步函数
        result = await agent_tools.smart_assistant(user_input)

        if result:
            # 处理不同类型的返回结果
            if isinstance(result, dict) and result.get("type") == "stock_pdf" and result.get("success"):
                # 处理股票分析PDF结果
                pdf_binary = result.get("pdf_binary")
                stock_name = result.get("stock_name", "未知股票")
                message = result.get("message", "股票分析报告生成完成")

                if pdf_binary:
                    # 先发送提示消息
                    await send_official_message("Test1: 📈 正在生成股票分析报告PDF，请稍候...", at_user_ids=at_user_ids)
                    # 发送PDF文件
                    # await send_pdf_via_dingtalk(pdf_binary, stock_name, at_user_ids)
                    await upload_file_to_Qiniu(pdf_binary, stock_name, at_user_ids)
                else:
                    error_msg = "Test1：❌ PDF二进制数据为空"
                    await send_official_message(error_msg, at_user_ids=at_user_ids)

            elif isinstance(result, dict) and result.get("type") == "text":
                # 处理普通文本结果
                final_result = f"Test1：{result.get('content', '')}"
                await send_official_message(final_result, at_user_ids=at_user_ids)
            else:
                # 兼容旧版本返回格式
                final_result = f"Test1：{result}"
                await send_official_message(final_result, at_user_ids=at_user_ids)
        else:
            error_msg = "Test1：LLM返回了空内容"
            await send_official_message(error_msg, at_user_ids=at_user_ids)

    except Exception as e:
        error_msg = f"Test1：处理出错: {str(e)}"
        app_logger.error(f"LLM处理错误: {error_msg}")
        await send_official_message(error_msg, at_user_ids=at_user_ids)
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

    # 使用 asyncio.create_task 来运行异步函数
    asyncio.create_task(sync_llm_processing(conversation_id, user_input, at_user_ids))


async def send_official_message(msg, at_user_ids=None, at_mobiles=None, is_at_all=False):
    """发送钉钉消息"""
    try:
        timestamp = str(round(time.time() * 1000))
        sign = generate_dingtalk_signature(timestamp, ROBOT_SECRET)

        robot_token = os.environ.get('ROBOT_ACCESS_TOKEN')
        robot_secret = os.environ.get('ROBOT_SECRET')

        if not robot_token or not robot_secret:
            return False

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


async def process_command(command):
    """处理用户指令（异步版本）"""
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
            # 正确等待异步函数
            response = await agent_tools.smart_assistant(pure_command)

            if response is None:
                return "Test1：LLM处理超时或无响应"
            elif isinstance(response, dict) and response.get("type") == "text":
                content = response.get("content", "")
                if not content.strip():
                    return "Test1：LLM返回了空内容"
                else:
                    return f"Test1：{content}"
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
                # 使用异步版本的 process_command
                result = await process_command(command)
                await send_official_message(result, at_user_ids=at_user_ids)
                return JSONResponse({"success": True})
            else:
                immediate_response = "Test1：正在思考中，请稍等片刻... ⏳"
                await send_official_message(immediate_response, at_user_ids=at_user_ids)

                pure_command = re.sub(r'^Test1\s*LLM\s*', '', command).strip()

                # 使用异步任务
                asyncio.create_task(sync_llm_processing(conversation_id, pure_command, at_user_ids))

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


@app.get("/test-playwright")
async def test_playwright():
    """测试Playwright异步功能"""
    try:
        # 使用异步方式测试Playwright
        result = await agent_tools.test_playwright_async()
        return {"status": "success", "message": f"Playwright测试成功: {result}"}
    except Exception as e:
        return {"status": "error", "message": f"Playwright测试失败: {str(e)}"}


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
