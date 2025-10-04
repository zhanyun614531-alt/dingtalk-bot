from dotenv import load_dotenv
from flask import Flask, request, jsonify
import hmac
import hashlib
import base64
import urllib.parse
import json
import requests
import os
import threading
import time
import logging
import re
import agent_tools

# 加载环境变量
load_dotenv()

# 初始化Flask应用
app = Flask(__name__)

# 配置日志
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 从环境变量获取钉钉机器人信息
ROBOT_ACCESS_TOKEN = os.getenv('ROBOT_ACCESS_TOKEN')
ROBOT_SECRET = os.getenv('ROBOT_SECRET')

# 存储处理中的任务
processing_tasks = {}

def async_process_llm_message(conversation_id, user_input, at_user_ids):
    """异步处理LLM消息"""
    try:
        print(f"【异步任务】开始处理: {user_input}")
        
        # 检查API密钥
        ark_key = os.environ.get('ARK_API_KEY')
        if not ark_key:
            error_msg = "Test1：ARK_API_KEY未设置"
            send_official_message(error_msg, at_user_ids=at_user_ids)
            return

        # 调用智能助手
        result = agent_tools.smart_assistant(user_input)
        
        if result:
            final_result = f"Test1：{result}"
            send_official_message(final_result, at_user_ids=at_user_ids)
        else:
            error_msg = "Test1：LLM返回了空内容"
            send_official_message(error_msg, at_user_ids=at_user_ids)
            
    except Exception as e:
        error_msg = f"Test1：处理出错: {str(e)}"
        print(f"【异步任务错误】{error_msg}")
        send_official_message(error_msg, at_user_ids=at_user_ids)
    finally:
        if conversation_id in processing_tasks:
            del processing_tasks[conversation_id]

def send_official_message(msg, at_user_ids=None, at_mobiles=None, is_at_all=False):
    """发送钉钉消息"""
    try:
        timestamp = str(round(time.time() * 1000))
        
        robot_token = os.environ.get('ROBOT_ACCESS_TOKEN')
        robot_secret = os.environ.get('ROBOT_SECRET')
        
        if not robot_token or not robot_secret:
            return False

        # 计算签名
        string_to_sign = f"{timestamp}\n{robot_secret}"
        hmac_code = hmac.new(
            robot_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

        # 构建URL和请求体
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
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            result = resp.json()
            return result.get('errcode') == 0
        else:
            return False
            
    except Exception as e:
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

@app.route('/')
def home():
    return "钉钉机器人服务运行中 ✅"

@app.route('/dingtalk/webhook', methods=['GET', 'POST'])
def webhook():
    """钉钉消息接收接口"""
    if request.method == 'GET':
        return "钉钉机器人服务运行中 ✅", 200

    try:
        data = request.json

        # 提取消息内容
        if 'text' in data and 'content' in data['text']:
            raw_content = data['text']['content'].strip()
            command = re.sub(r'<at id=".*?">@.*?</at>', '', raw_content).strip()
            
            # 提取会话信息
            conversation_id = data.get('conversationId', 'unknown')
            at_user_ids = [user['dingtalkId'] for user in data.get('atUsers', [])]

            # 处理非LLM指令（立即响应）
            if not command.startswith("Test1 LLM"):
                result = process_command(command)
                send_official_message(result, at_user_ids=at_user_ids)
                return jsonify({"success": True})

            # 处理LLM指令（异步）
            else:
                # 立即响应"处理中"消息
                immediate_response = "Test1：正在思考中，请稍等片刻... ⏳"
                send_official_message(immediate_response, at_user_ids=at_user_ids)
                
                # 启动异步处理线程
                pure_command = re.sub(r'^Test1\s*LLM\s*', '', command).strip()
                thread = threading.Thread(
                    target=async_process_llm_message,
                    args=(conversation_id, pure_command, at_user_ids)
                )
                thread.daemon = True
                thread.start()
                
                # 记录处理中的任务
                processing_tasks[conversation_id] = {
                    "start_time": time.time(),
                    "user_input": pure_command
                }
                
                return jsonify({"success": True, "status": "processing"})

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "dingtalk-bot"})

if __name__ == '__main__':
    port = int(os.getenv('DINGTALK_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
