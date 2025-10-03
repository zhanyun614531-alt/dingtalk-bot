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
    """简化的Agent类，专注于自动工具调用"""

    def __init__(self):
        self.client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
            api_key=os.environ.get("ARK_API_KEY")
        )
        self.model_id = "bot-20250907084333-cbvff"

        # 系统提示词，重点强调工具调用
        self.system_prompt = """你是一个智能助手，具备工具调用能力。当用户请求涉及以下功能时，你必须返回对应的JSON格式指令：

可用工具：
1. 天气查询：{"action": "get_weather", "parameters": {"city": "城市名称"}}
2. 计算器：{"action": "calculator", "parameters": {"expression": "数学表达式"}}
3. 发送邮件：{"action": "send_qq_email", "parameters": {"to": "收件邮箱", "subject": "邮件主题", "body": "邮件内容"}}

规则：
1. 需要调用工具时，只返回```json和```包裹的JSON，不要有任何其他文字
2. 如果用户要求发送邮件但未提供具体内容，你需要生成合适的内容
3. 如果参数缺失，用自然语言询问用户补充信息
4. 不需要工具时，直接回答用户问题
"""

    def get_weather(self, city):
        """获取天气信息"""
        if not city:
            return "天气查询失败：未指定城市名称"

        try:
            response = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
            response.raise_for_status()
            weather_data = response.json()
            current = weather_data["current_condition"][0]
            return (f"{city}当前天气：{current['weatherDesc'][0]['value']}，"
                    f"温度{current['temp_C']}°C，湿度{current['humidity']}%")
        except Exception as e:
            return f"天气查询失败：{str(e)}"

    def calculator(self, expression):
        """执行数学计算"""
        if not expression:
            return "计算失败：未提供数学表达式"

        try:
            allowed_chars = {'+', '-', '*', '/', '(', ')', '.', ' ', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
            if not all(c in allowed_chars for c in expression):
                return "计算失败：表达式包含不支持的字符"
            result = eval(expression)
            return f"计算结果：{expression} = {result}"
        except Exception as e:
            return f"计算失败：{str(e)}"

    def send_qq_email(self, to, subject, body):
        """发送QQ邮件"""
        if not all([to, subject, body]):
            return "邮件发送失败：收件人、主题或正文不能为空"

        qq_user = os.environ.get("QQ_EMAIL_USER", "").strip()
        qq_auth_code = os.environ.get("QQ_EMAIL_AUTH_CODE", "").strip()

        if not all([qq_user, qq_auth_code]):
            return "邮件发送失败：请配置QQ邮箱信息"

        message = MIMEText(body, 'plain', 'utf-8')
        message['From'] = qq_user
        message['To'] = to
        message['Subject'] = Header(subject, 'utf-8')

        try:
            server = smtplib.SMTP_SSL('smtp.qq.com', 465)
            server.login(qq_user, qq_auth_code)
            server.sendmail(qq_user, to, message.as_string())
            server.quit()
            return f"邮件发送成功！已发送至：{to}"
        except Exception as e:
            return f"邮件发送失败：{str(e)}"

    def extract_tool_call(self, llm_response):
        """从LLM响应中提取工具调用指令"""
        if "```json" in llm_response and "```" in llm_response:
            # 提取JSON部分
            start = llm_response.find("```json") + 7
            end = llm_response.find("```", start)
            json_str = llm_response[start:end].strip()

            try:
                tool_data = json.loads(json_str)
                if isinstance(tool_data, dict) and "action" in tool_data and "parameters" in tool_data:
                    return tool_data
            except json.JSONDecodeError:
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
        """
        处理用户请求的核心函数
        返回：(最终结果, 是否调用了工具)
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]

        try:
            # 第一步：获取LLM的初始响应
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                stream=False
            )

            llm_response = response.choices[0].message.content.strip()

            # 第二步：检查是否需要工具调用
            tool_data = self.extract_tool_call(llm_response)

            if tool_data:
                # 调用工具并返回结果
                tool_result = self.call_tool(tool_data["action"], tool_data["parameters"])
                return tool_result, True
            else:
                # 直接返回LLM的回答
                return llm_response, False

        except Exception as e:
            return f"处理请求时出错：{str(e)}", False


# 使用函数
def smart_assistant(user_input):
    """
    智能助手主函数
    输入用户请求，自动识别并执行相应功能
    """
    agent = DeepseekAgent()
    result, tool_used = agent.process_request(user_input)
    return result

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

# 示例使用
if __name__ == "__main__":
    # 示例1：发送邮件（如您要求的场景）
    request1 = "379609511@qq.com发送一封邮件，主题是国庆安排，内容是深圳一日游。深圳一日游的内容需要你自己LLM提供"
    result1 = smart_assistant(request1)
    print("结果1:", result1)

    # 示例2：天气查询
    request2 = "查询北京的天气情况"
    result2 = smart_assistant(request2)
    print("结果2:", result2)

    # 示例3：数学计算
    request3 = "请计算123 + 456 * 2的结果"
    result3 = smart_assistant(request3)
    print("结果3:", result3)

    # 示例4：普通对话
    request4 = "你好，请介绍一下你自己"
    result4 = smart_assistant(request4)
    print("结果4:", result4)
