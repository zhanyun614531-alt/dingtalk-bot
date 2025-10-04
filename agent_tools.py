import os
import json
import requests
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
3. 发送邮件：{"action": "send_email", "parameters": {"to": "收件邮箱", "subject": "邮件主题", "body": "邮件内容"}}

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

    def send_email(self, to, subject, body):
        """发送邮件 - 使用 Brevo API（带详细调试）"""

        if not all([to, subject, body]):
            return "收件人、主题或正文不能为空"
    
        brevo_api_key = os.environ.get("BREVO_API_KEY")
        sender_email = os.environ.get("BREVO_SENDER_EMAIL", "noreply@brevo.com")
        sender_name = os.environ.get("BREVO_SENDER_NAME", "智能助手")
    
        print(f"【Brevo调试】环境变量检查:")
        print(f"  - BREVO_API_KEY 存在: {bool(brevo_api_key)}")
        print(f"  - BREVO_API_KEY 长度: {len(brevo_api_key) if brevo_api_key else 0}")
        print(f"  - BREVO_SENDER_EMAIL: {sender_email}")
        print(f"  - BREVO_SENDER_NAME: {sender_name}")
    
        if not brevo_api_key:
            return "❌ 邮件服务未配置：BREVO_API_KEY 未找到"
    
        # 检查API Key格式
        if not brevo_api_key.startswith('xkeysib-'):
            print(f"【Brevo警告】API Key 格式可能不正确，应以 'xkeysib-' 开头")
    
        try:
            # Brevo API v3
            url = "https://api.brevo.com/v3/smtp/email"
    
            payload = {
                "sender": {
                    "name": sender_name,
                    "email": sender_email
                },
                "to": [
                    {
                        "email": to,
                        "name": to.split('@')[0]
                    }
                ],
                "subject": subject,
                "htmlContent": f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2>{subject}</h2>
                    <div style="white-space: pre-line;">{body}</div>
                </div>
                """,
                "textContent": body
            }
    
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": brevo_api_key
            }
    
            print(f"【Brevo调试】请求头: {headers}")
            print(f"【Brevo调试】请求负载: {payload}")
    
            response = requests.post(url, json=payload, headers=headers, timeout=30)
    
            print(f"【Brevo调试】响应状态码: {response.status_code}")
            print(f"【Brevo调试】完整响应: {response.text}")
    
            if response.status_code == 201:
                result = response.json()
                message_id = result.get('messageId', '')
                return f"📧 邮件发送成功！已发送至：{to}"
            else:
                # 更详细的错误处理
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', 'Unknown error')
                    error_code = error_data.get('code', 'No error code')
                    return f"❌ 邮件发送失败 [{response.status_code}]: {error_message} (代码: {error_code})"
                except:
                    return f"❌ 邮件发送失败 [{response.status_code}]: {response.text}"
    
        except Exception as e:
            error_msg = f"❌ 邮件发送异常：{str(e)}"
            print(f"【Brevo错误】{error_msg}")
            import traceback
            print(f"【Brevo错误堆栈】{traceback.format_exc()}")
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
        elif action == "send_email":  # 注意：这里改为 send_email
            return self.send_email(
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
        "向379609511@qq.com发送测试邮件，主题为'Brevo测试'，内容为'这是一封通过Brevo发送的测试邮件'"
    ]

    for request in test_requests:
        print(f"请求: {request}")
        result = smart_assistant(request)
        print(f"结果: {result}\n")
