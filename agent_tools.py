import os
import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.header import Header
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class DeepseekAgent:
    """智能助手Agent"""

    def __init__(self):
        self.client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
            api_key=os.environ.get("ARK_API_KEY")
        )
        self.model_id = "bot-20250907084333-cbvff"

        # 简化的系统提示
        self.system_prompt = """你是一个智能助手，具备工具调用能力。

可用工具：
1. 天气查询：{"action": "get_weather", "parameters": {"city": "城市名称"}}
2. 计算器：{"action": "calculator", "parameters": {"expression": "数学表达式"}}
3. 发送邮件：{"action": "send_qq_email", "parameters": {"to": "收件邮箱", "subject": "邮件主题", "body": "邮件内容"}}

规则：
1. 需要调用工具时，返回```json和```包裹的JSON
2. 不需要工具时，直接回答问题
3. 用简洁明了的方式回答
"""

    def get_weather(self, city):
        """获取天气信息"""
        if not city:
            return "请指定城市名称"

        try:
            response = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
            weather_data = response.json()
            current = weather_data["current_condition"][0]
            return (f"{city}天气：{current['weatherDesc'][0]['value']}，"
                    f"温度{current['temp_C']}°C，湿度{current['humidity']}%")
        except:
            return "天气查询失败"

    def calculator(self, expression):
        """执行数学计算"""
        if not expression:
            return "请提供数学表达式"

        try:
            allowed_chars = {'+', '-', '*', '/', '(', ')', '.', ' ', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
            if not all(c in allowed_chars for c in expression):
                return "表达式包含不支持的字符"
            result = eval(expression)
            return f"{expression} = {result}"
        except:
            return "计算失败"

    def send_qq_email(self, to, subject, body):
        """发送邮件 - 使用 Resend HTTP API"""
        if not all([to, subject, body]):
            return "收件人、主题或正文不能为空"
    
        resend_api_key = os.environ.get("RESEND_API_KEY")
        if not resend_api_key:
            return "邮件服务未配置完成，请联系管理员添加RESEND_API_KEY"
    
        try:
            # 使用Resend的测试域名或验证你自己的域名
            from_email = "onboarding@resend.dev"  # Resend提供的测试发件人
            
            data = {
                "from": from_email,
                "to": [to],
                "subject": subject,
                "html": f"<div style='font-family: Arial, sans-serif; line-height: 1.6; white-space: pre-line;'>{body}</div>",
                "text": body
            }
    
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json"
                },
                json=data,
                timeout=30
            )
    
            print(f"【Resend调试】状态码: {response.status_code}")
            print(f"【Resend调试】响应: {response.text}")
    
            if response.status_code == 200:
                result = response.json()
                return f"邮件发送成功！已发送至：{to}"
            else:
                error_detail = response.json().get('message', response.text)
                return f"邮件发送失败：{error_detail}"
    
        except Exception as e:
            error_msg = f"邮件发送异常：{str(e)}"
            print(f"【Resend错误】{error_msg}")
            return error_msg

    def extract_tool_call(self, llm_response):
        """从LLM响应中提取工具调用指令"""
        if "```json" in llm_response and "```" in llm_response:
            start = llm_response.find("```json") + 7
            end = llm_response.find("```", start)
            json_str = llm_response[start:end].strip()

            try:
                tool_data = json.loads(json_str)
                if isinstance(tool_data, dict) and "action" in tool_data and "parameters" in tool_data:
                    return tool_data
            except:
                pass
        return None

    def call_tool(self, action, parameters):
        """统一工具调用入口"""
        if action == "get_weather":
            return self.get_weather(parameters.get("city", ""))
        elif action == "calculator":
            return self.calculator(parameters.get("expression", ""))
        elif action == "send_qq_email":
            return self.send_qq_email(
                parameters.get("to", ""),
                parameters.get("subject", ""),
                parameters.get("body", "")
            )
        else:
            return f"未知工具：{action}"

    def process_request(self, user_input):
        """处理用户请求"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]

        try:
            # 获取LLM响应
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                stream=False
            )

            llm_response = response.choices[0].message.content.strip()

            # 检查工具调用
            tool_data = self.extract_tool_call(llm_response)
            if tool_data:
                tool_result = self.call_tool(tool_data["action"], tool_data["parameters"])
                return tool_result, True
            else:
                return llm_response, False

        except Exception as e:
            return f"处理请求时出错：{str(e)}", False

def smart_assistant(user_input):
    """智能助手主函数"""
    agent = DeepseekAgent()
    result, tool_used = agent.process_request(user_input)
    return result

if __name__ == "__main__":
    # 测试示例
    test_requests = [
        "查询北京的天气",
        "计算123 + 456",
        "你好，请介绍一下你自己"
    ]
    
    for request in test_requests:
        result = smart_assistant(request)
        print(f"请求: {request}")
        print(f"结果: {result}\n")
