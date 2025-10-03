from dotenv import load_dotenv
from flask import Flask, request, jsonify
import hmac
import hashlib
import base64
import urllib.parse
import json
import requests
import os
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

        final_msg = re.sub(r'Test$', '', resp.text)
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
    key = "回复"
    raw_command = re.sub(re.escape(key), '', original_msg)
    command = re.sub(r'\s', '', raw_command)
    # print(command)
    if not command:
        return "请发送具体指令哦~ 支持的指令：\n- LLM"
    elif command == '时间':
        return f"当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"

    elif command.startswith("LLM"):
        agent = Test.DeepseekAgent()
        pure_command = re.sub(r'^回复\s*LLM\s*', '', command)
        response = agent.process_input(pure_command)
        return f"回复：{response}"

    # 未知指令
    else:
        return f"暂不支持该指令：{command}\n发送「帮助」查看支持的功能"

# 【新增】根路径路由：用于返回请求方的IP（即你的Python代码出口IP）
@app.route('/')  # 配置根路径
def get_sender_ip():
    # request.remote_addr 就是发送请求的IP（即你的Python代码出口IP）
    return f"你的Python代码实际发送IP：{request.remote_addr}"

@app.route('/dingtalk/webhook', methods=['GET', 'POST'])
def webhook():
    """钉钉消息接收接口，使用官方签名验证逻辑"""
    # 处理GET请求（用于验证连接）
    if request.method == 'GET':
        return "钉钉机器人服务运行中 ✅", 200

    # 处理POST请求（钉钉消息）
    try:
        # 获取官方要求的签名参数
        # timestamp = request.headers.get('timestamp')
        # print(timestamp)
        # print("*"*50)

        # sign = request.headers.get('sign')
        # timestamp = str(round(time.time() * 1000))

        # print(timestamp, sign)

        # 验证签名（使用官方算法）
        # if not verify_official_signature(timestamp, sign):
        #     logging.warning("签名验证失败，可能是secret不匹配或参数错误")
        #     return jsonify({"error": "签名验证失败"}), 403

        # 解析消息内容
        data = request.json
        logging.info(f"收到钉钉消息: {json.dumps(data, ensure_ascii=False)}")

        # 提取指令内容（兼容企业机器人和普通机器人格式）
        if 'text' in data and 'content' in data['text']:
            # 处理可能包含的@标识
            raw_content = data['text']['content'].strip()
            # 移除@机器人的标签（如<at id="xxx">@机器人</at>）
            command = re.sub(r'<at id=".*?">@.*?</at>', '', raw_content).strip()

            # 处理指令并发送回复
            result = process_command(command)

            # 提取需要@的用户（如果有）
            at_user_ids = [user['dingtalkId'] for user in data.get('atUsers', [])]
            send_result = send_official_message(
                result,
                at_user_ids=at_user_ids,
                is_at_all=False
            )

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

if __name__ == '__main__':
    # 从环境变量获取端口，默认5000
    port = int(os.getenv('DINGTALK_PORT', 5000))
    # 监听所有网络接口
    app.run(host='0.0.0.0', port=port, debug=True)
