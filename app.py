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
    """异步处理LLM消息 - 带完整调试"""
    try:
        print(f"【异步任务】开始处理: {user_input}")
        print(f"【异步任务】会话ID: {conversation_id}")
        print(f"【异步任务】@用户: {at_user_ids}")
        
        # 测试环境变量在异步线程中是否可用
        robot_token = os.environ.get('ROBOT_ACCESS_TOKEN')
        robot_secret = os.environ.get('ROBOT_SECRET')
        ark_key = os.environ.get('ARK_API_KEY')
        
        print(f"【环境变量检查】ROBOT_ACCESS_TOKEN: {'已设置' if robot_token else '未设置'}")
        print(f"【环境变量检查】ROBOT_SECRET: {'已设置' if robot_secret else '未设置'}")
        print(f"【环境变量检查】ARK_API_KEY: {'已设置' if ark_key else '未设置'}")
        
        if not ark_key:
            error_msg = "Test1：ARK_API_KEY未设置，无法调用LLM"
            print(f"【错误】{error_msg}")
            send_official_message(error_msg, at_user_ids=at_user_ids)
            return

        print("【异步任务】开始LLM处理...")
        start_time = time.time()
        
        # 添加更详细的调试
        print("【异步任务】准备调用 Test.smart_assistant...")
        result = agent_tools.smart_assistant(user_input)
        
        processing_time = time.time() - start_time
        print(f"【异步任务】LLM处理完成，耗时: {processing_time:.1f}秒")
        print(f"【异步任务】LLM返回类型: {type(result)}")
        print(f"【异步任务】LLM返回内容: {result}")
        
        if result:
            final_result = f"Test1：{result}"
            print(f"【异步任务】准备发送结果: {final_result[:100]}...")
            
            send_success = send_official_message(final_result, at_user_ids=at_user_ids)
            if send_success:
                print("【异步任务】消息发送成功")
            else:
                print("【异步任务】消息发送失败")
        else:
            error_msg = "Test1：LLM返回了空内容"
            print(f"【异步任务】{error_msg}")
            send_official_message(error_msg, at_user_ids=at_user_ids)
            
    except Exception as e:
        # 更详细的错误信息
        error_msg = f"Test1：异步处理出错: {str(e)}"
        print(f"【异步任务错误】{error_msg}")
        print(f"【异步任务错误类型】{type(e).__name__}")
        
        import traceback
        full_traceback = traceback.format_exc()
        print(f"【完整错误堆栈】\n{full_traceback}")
        
        # 检查错误信息中是否包含 'response'
        if 'response' in str(e):
            print("【关键发现】错误确实与 'response' 变量相关")
        
        # 尝试发送错误信息
        try:
            send_official_message(error_msg, at_user_ids=at_user_ids)
        except Exception as send_error:
            print(f"【严重错误】连错误消息都无法发送: {send_error}")
    finally:
        if conversation_id in processing_tasks:
            del processing_tasks[conversation_id]
        print(f"【异步任务】清理完成，会话ID: {conversation_id}")

def remove_trailing_string(str, target):
    # 使用正则匹配末尾的目标字符串（包含可能的空格）
    # 正则含义：匹配字符串末尾的(空格+目标字符串)组合
    pattern = r'\s*' + re.escape(target) + r'$'
    # 替换为空字符串（即删除）
    result = re.sub(pattern, '', str)
    return result

def send_official_message(msg, at_user_ids=None, at_mobiles=None, is_at_all=False):
    """
    基于官方Demo的消息发送方法，返回发送状态
    """
    try:
        timestamp = str(round(time.time() * 1000))
        
        # 获取环境变量（确保在函数内部获取）
        robot_token = os.environ.get('ROBOT_ACCESS_TOKEN')
        robot_secret = os.environ.get('ROBOT_SECRET')
        
        if not robot_token or not robot_secret:
            print("【发送错误】钉钉机器人配置缺失")
            return False

        # 计算签名
        string_to_sign = f"{timestamp}\n{robot_secret}"
        hmac_code = hmac.new(
            robot_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

        # 构建URL
        url = f'https://oapi.dingtalk.com/robot/send?access_token={robot_token}&timestamp={timestamp}&sign={sign}'

        # 构建消息体
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
        print(f"【发送消息】准备发送到钉钉: {msg[:50]}...")
        
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        print(f"【发送消息】钉钉响应: {resp.status_code} - {resp.text}")
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get('errcode') == 0:
                print("【发送消息】发送成功")
                return True
            else:
                print(f"【发送消息】钉钉API错误: {result}")
                return False
        else:
            print(f"【发送消息】HTTP错误: {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"【发送消息】异常: {str(e)}")
        return False

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
            pure_command = re.sub(r'^LLM', '', command).strip()
            print(f"【调试】LLM纯命令: '{pure_command}'")
            response = Test.smart_assistant(pure_command)
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

@app.route('/async-debug')
def async_debug():
    """异步任务调试信息"""
    now = time.time()
    active_tasks = {}
    
    for task_id, task_info in processing_tasks.items():
        duration = now - task_info['start_time']
        active_tasks[task_id] = {
            "user_input": task_info['user_input'],
            "duration_seconds": round(duration, 1),
            "status": "running" if duration < 300 else "stuck"
        }
    
    return jsonify({
        "active_tasks_count": len(active_tasks),
        "server_time": now,
        "active_tasks": active_tasks
    })

@app.route('/test-llm-direct')
def test_llm_direct():
    """直接测试LLM，绕过所有复杂逻辑"""
    try:
        from openai import OpenAI  # ✅ 新版本导入
        
        # 创建客户端
        client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
            api_key=os.environ.get("ARK_API_KEY")
        )
        
        # 简单直接的测试
        test_prompt = "2025年国庆假期法定节假日是什么时候？简要回答！"
        print(f"【直接测试】开始测试，提示: {test_prompt}")
        
        response = client.chat.completions.create(
            model="bot-20250907084333-cbvff",
            messages=[
                {"role": "user", "content": test_prompt}
            ],
            stream=False
        )
        
        print(f"【直接测试】响应: {response}")
        
        result = response.choices[0].message.content
        return jsonify({
            "status": "success",
            "response": result,
            "response_type": type(response).__name__,
            "choices_count": len(response.choices)
        })
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        })

@app.route('/test-module')
def test_module():
    """直接测试Test.py模块"""
    try:
        print("【模块测试】开始测试Test.py模块...")
        
        # 测试1: 导入是否成功
        print("【模块测试】检查导入...")
        from Test import smart_assistant
        print("【模块测试】导入成功")
        
        # 测试2: 简单调用
        print("【模块测试】开始简单调用...")
        test_input = "你好，请简单回复'测试成功'"
        result = smart_assistant(test_input)
        
        print(f"【模块测试】调用结果: {result}")
        
        return jsonify({
            "status": "success",
            "module_test": "通过",
            "result": result
        })
        
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        print(f"【模块测试错误】\n{full_traceback}")
        
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": full_traceback
        })
        
if __name__ == '__main__':
    # 从环境变量获取端口，默认5000
    port = int(os.getenv('DINGTALK_PORT', 5000))
    # 监听所有网络接口
    app.run(host='0.0.0.0', port=port, debug=True)
