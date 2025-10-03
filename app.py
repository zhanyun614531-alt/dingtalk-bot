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
import datetime
import logging
import re
# from llm_output import DeepseekAgent
import Test

# 加载环境变量（从.env文件读取API密钥等配置）
load_dotenv()

# 初始化Flask应用
app = Flask(__name__)

# 配置日志
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 从环境变量或配置获取钉钉机器人信息
ROBOT_ACCESS_TOKEN = os.getenv('ROBOT_ACCESS_TOKEN', '你的access_token')  # 机器人access_token
ROBOT_SECRET = os.getenv('ROBOT_SECRET', '你的加签secret')  # 机器人安全设置中的加签secret

# 存储处理中的任务
processing_tasks = {}

def async_process_llm_message(conversation_id, user_input, at_user_ids):
    """异步处理LLM消息"""
    try:
        print(f"【异步任务】开始处理: {user_input}")
        
        # 创建Agent并处理
        agent = Test.DeepseekAgent()
        response = agent.process_input(user_input)
        
        print(f"【异步任务】处理完成: {response}")
        
        # 发送结果到钉钉
        if response:
            result = f"Test1：{response}"
            send_official_message(result, at_user_ids=at_user_ids)
            
        # 从处理中任务移除
        if conversation_id in processing_tasks:
            del processing_tasks[conversation_id]
            
    except Exception as e:
        error_msg = f"Test1：异步处理出错: {str(e)}"
        print(f"【异步任务错误】{error_msg}")
        send_official_message(error_msg, at_user_ids=at_user_ids)

def verify_official_signature(timestamp, sign):
    """
    基于钉钉官方Demo的签名验证方法
    与官方算法完全一致，解决签名验证失败问题
    """
    try:
        # 按照官方文档拼接字符串
        string_to_sign = f"{timestamp}\n{ROBOT_SECRET}"
        # 计算HMAC-SHA256签名
        hmac_code = hmac.new(
            ROBOT_SECRET.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        # 进行Base64编码并URL转义
        computed_sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        # 比对签名
        return computed_sign == sign
    except Exception as e:
        logging.error(f"签名验证出错: {str(e)}")
        return False

def remove_trailing_string(str, target):
    # 使用正则匹配末尾的目标字符串（包含可能的空格）
    # 正则含义：匹配字符串末尾的(空格+目标字符串)组合
    pattern = r'\s*' + re.escape(target) + r'$'
    # 替换为空字符串（即删除）
    result = re.sub(pattern, '', str)
    return result

def send_official_message(msg, at_user_ids=None, at_mobiles=None, is_at_all=False):
    """
    基于官方Demo的消息发送方法
    支持@用户功能，完全符合官方接口规范
    """
    try:
        # def send_custom_robot_group_message(access_token, secret, msg, at_user_ids=None, at_mobiles=None,
        #                                     is_at_all=False):
        """
        发送钉钉自定义机器人群消息
        :param access_token: 机器人webhook的access_token
        :param secret: 机器人安全设置的加签secret
        :param msg: 消息内容
        :param at_user_ids: @的用户ID列表
        :param at_mobiles: @的手机号列表
        :param is_at_all: 是否@所有人
        :return: 钉钉API响应
        """
        # timestamp = str(round(time.time() * 1000))
        # string_to_sign = f'{timestamp}\n{secret}'
        # hmac_code = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'),
        #                      digestmod=hashlib.sha256).digest()
        # sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        #
        # url = f'https://oapi.dingtalk.com/robot/send?access_token={access_token}&timestamp={timestamp}&sign={sign}'
        #
        # body = {
        #     "at": {
        #         "isAtAll": str(is_at_all).lower(),
        #         "atUserIds": at_user_ids or [],
        #         "atMobiles": at_mobiles or []
        #     },
        #     "text": {
        #         "content": msg
        #     },
        #     "msgtype": "text"
        # }
        # headers = {'Content-Type': 'application/json'}
        # resp = requests.post(url, json=body, headers=headers)
        # logging.info("钉钉自定义机器人群消息响应：%s", resp.text)
        # return resp.json()

        timestamp = str(round(time.time() * 1000))
        # 计算签名（与官方Demo一致）
        string_to_sign = f"{timestamp}\n{ROBOT_SECRET}"
        hmac_code = hmac.new(
            ROBOT_SECRET.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

        # 构建官方要求的URL
        url = f'https://oapi.dingtalk.com/robot/send?access_token={ROBOT_ACCESS_TOKEN}&timestamp={timestamp}&sign={sign}'

        # 构建消息体（支持@功能）
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
        resp = requests.post(url, json=body, headers=headers)
        print(resp.text)

        final_msg = re.sub(r'Test1$', '', resp.text)
        # logging.info(f"钉钉消息发送响应: {resp.text}")
        logging.info(f"钉钉消息发送响应: {final_msg}")

        return resp.json()
    except Exception as e:
        error_msg = f"发送消息失败: {str(e)}"
        logging.error(error_msg)
        return {"error": error_msg}

def process_command(command):
    """处理用户指令，支持多种功能"""
    original_msg = command.strip()
    key = "Test1"
    raw_command = re.sub(re.escape(key), '', original_msg)
    command = re.sub(r'\s', '', raw_command)
    
    print(f"【调试】原始命令: '{original_msg}'")
    print(f"【调试】处理后命令: '{command}'")
    
    if not command:
        return "Test1：请发送具体指令哦~ 支持的指令：\n- LLM"
    elif command == '时间':
        return f"Test1：当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    elif command.startswith("LLM"):
        try:
            print(f"【调试】开始调用LLM，命令: '{command}'")
            agent = Test.DeepseekAgent()
            pure_command = re.sub(r'^LLM', '', command).strip()
            print(f"【调试】LLM纯命令: '{pure_command}'")
            
            response = agent.process_input(pure_command)
            print(f"【调试】LLM返回: '{response}'")
            
            if response is None:
                return "Test1：LLM处理超时或无响应"
            elif not response.strip():
                return "Test1：LLM返回了空内容"
            else:
                return f"Test1：{response}"
                
        except Exception as e:
            error_msg = f"Test1：LLM处理出错: {str(e)}"
            print(f"【错误】{error_msg}")
            return error_msg
    else:
        return f"Test1：暂不支持该指令：{command}\n发送「帮助」查看支持的功能"

# 【新增】根路径路由：用于返回请求方的IP（即你的Python代码出口IP）
@app.route('/')  # 配置根路径
def get_sender_ip():
    # request.remote_addr 就是发送请求的IP（即你的Python代码出口IP）
    return f"你的Python代码实际发送IP：{request.remote_addr}"

@app.route('/dingtalk/webhook', methods=['GET', 'POST'])
def webhook():
    """钉钉消息接收接口，使用异步处理LLM请求"""
    # 处理GET请求（用于验证连接）
    if request.method == 'GET':
        return "钉钉机器人服务运行中 ✅", 200

    # 处理POST请求（钉钉消息）
    try:
        data = request.json
        logging.info(f"收到钉钉消息: {json.dumps(data, ensure_ascii=False)}")

        # 提取消息内容
        if 'text' in data and 'content' in data['text']:
            raw_content = data['text']['content'].strip()
            command = re.sub(r'<at id=".*?">@.*?</at>', '', raw_content).strip()
            
            # 提取会话ID用于跟踪
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
        error_msg = f"处理请求出错: {str(e)}"
        logging.error(error_msg)
        return jsonify({"error": error_msg}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "dingtalk-bot"})

@app.route('/ip')
def get_ip():
    """获取Render服务器的公网IP"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    return jsonify({
        "client_ip": client_ip,
        "headers": dict(request.headers)
    })

@app.route('/server-ip')
def get_server_ip():
    """获取Render服务器的真实公网IP"""
    try:
        # 方法1: 通过外部API获取服务器出口IP
        response = requests.get('https://httpbin.org/ip', timeout=10)
        if response.status_code == 200:
            server_ip = response.json()['origin']
            return jsonify({
                "render_server_public_ip": server_ip,
                "note": "将此IP添加到钉钉白名单"
            })
    except Exception as e:
        pass
    
    try:
        # 方法2: 通过其他服务获取
        response = requests.get('https://api.ipify.org?format=json', timeout=10)
        if response.status_code == 200:
            server_ip = response.json()['ip']
            return jsonify({
                "render_server_public_ip": server_ip,
                "note": "将此IP添加到钉钉白名单"
            })
    except Exception as e:
        return jsonify({"error": f"无法获取服务器IP: {str(e)}"})

if __name__ == '__main__':
    # 从环境变量获取端口，默认5000
    port = int(os.getenv('DINGTALK_PORT', 5000))
    # 监听所有网络接口
    app.run(host='0.0.0.0', port=port, debug=True)
