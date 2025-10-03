import os
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import openai  # ✅ 改为旧版本导入
from dotenv import load_dotenv

# 加载环境变量（从.env文件读取API密钥等配置）
load_dotenv()

# 配置OpenAI（旧版本方式）
openai.api_base = "https://ark.cn-beijing.volces.com/api/v3/bots"
openai.api_key = os.environ.get("ARK_API_KEY")

class AgentMemory:
    """对话记忆管理类，负责存储对话历史和系统提示"""

    def __init__(self, max_history=10):
        # 系统提示：严格约束工具调用格式 + 参考资料输出规则
        self.system_prompt = """你是一个具备工具调用能力的智能助手，必须严格遵循以下规则：

        可用工具及调用格式（必须用```json和```包裹，不可省略）：
        1. 发送邮件
           {"action": "send_qq_email", "parameters": {"to": "收件人邮箱", "subject": "邮件主题", "body": "邮件内容"}}

        操作规范：
        1. 需要调用工具时，仅返回包裹在```json和```中的JSON，无任何额外文字
        2. 不需要工具时，**用最简洁的自然语言直接回答核心问题**，无需额外解释、知识补充或结构化格式（如标题、列表等）
        3. JSON必须包含"action"和"parameters"字段，参数值不能为空
        4. 若参数缺失（如不知道收件人邮箱），需用自然语言询问用户补充信息
        5. **仅当用户明确要求"提供参考资料""带资料来源""参考资料"等类似表述时，回答才包含参考资料编号；否则，只输出核心答案，不需要带资料来源**
        """
        self.history = []  # 存储对话历史
        self.max_history = max_history  # 最大历史记录数量

    def add_message(self, role, content):
        """添加消息到对话历史，自动截断过长记录"""
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]  # 保留最新的记录

    def get_messages(self):
        """获取完整对话列表（包含系统提示）"""
        return [
            {"role": "system", "content": self.system_prompt}] + self.history

class Toolkit:
    """工具包类，包含所有可用工具的实现"""
    def __init__(self):
        # QQ邮箱配置（从环境变量读取）
        self.qq_user = os.environ.get("QQ_EMAIL_USER",
                                      "").strip()  # 格式：xxxxxx@qq.com
        self.qq_auth_code = os.environ.get("QQ_EMAIL_AUTH_CODE",
                                           "").strip()  # QQ邮箱授权码
        self.qq_configured = all([self.qq_user, self.qq_auth_code])  # 检查配置完整性

    def send_qq_email(self, to, subject, body):
        """通过QQ邮箱发送邮件（需提前开启SMTP服务并获取授权码）"""
        if not all([to, subject, body]):
            return "邮件发送失败：收件人、主题或正文不能为空"
        if not self.qq_configured:
            return "邮件发送失败：请在.env文件中配置QQ_EMAIL_USER（邮箱地址）和QQ_EMAIL_AUTH_CODE（授权码）"
        message = MIMEText(body, 'plain', 'utf-8')
        message['From'] = self.qq_user  # 发件人（与登录账号完全一致）
        message['To'] = to # 收件人（单个邮箱直接传字符串，多个需传列表）
        message['Subject'] = Header(subject, 'utf-8')  # 邮件主题（中文需utf-8编码）
        server = None
        try:
            # QQ邮箱SMTP服务器配置（SSL加密，端口465）
            server = smtplib.SMTP_SSL('smtp.qq.com', 465)
            # 登录认证（使用授权码而非QQ密码，确保qq_user与登录账号完全一致）
            server.login(self.qq_user, self.qq_auth_code)
            # 发送邮件：to参数若为多个邮箱，需改为列表格式（如[to1, to2]）
            server.sendmail(self.qq_user, to, message.as_string())
            return f"邮件发送成功！已发送至：{to}（主题：{subject}）"

        except Exception as e:
            print(f"邮件发送过程中出错: {e}")
            return False
        finally:
            # 确保连接被正确关闭
            if server:
                try:
                    server.quit()
                except:
                    # 忽略退出时的任何错误
                    pass

    def call_tool(self, action, parameters):
        """统一工具调用入口"""
        if action == "send_qq_email":
            return self.send_qq_email(
                parameters.get("to", "").strip(),  # 清理收件人地址空格
                parameters.get("subject", "").strip(),  # 清理主题空格
                parameters.get("body", "").strip()  # 清理正文空格
            )
        else:
            return f"工具调用失败：未知工具'{action}'（支持的工具：get_weather、calculator、send_qq_email、file_info_query）"

class DeepseekAgent:
    """Agent主类，协调LLM、记忆和工具调用"""
    def __init__(self):
        # self.model_id = "bot-20250906074401-gbz95"  # Deepseek R1 model ID
        self.model_id = "bot-20250907084333-cbvff"  # Deepseek V3 model ID
        self.memory = AgentMemory()
        self.toolkit = Toolkit()

    def extract_tool_call(self, llm_response):
        """从LLM响应中提取并验证工具调用指令"""
        # ... 保持原有的extract_tool_call方法

    def process_input(self, user_input):
    """处理用户输入，调用Agent并返回结果"""
    try:
        print(f"【Test.py】开始处理: {user_input}")
        
        self.memory.add_message("user", user_input)
        messages = self.memory.get_messages()
        
        print("【Test.py】调用火山方舟API...")
        start_time = time.time()
        
        response = openai.ChatCompletion.create(
            model=self.model_id,
            messages=messages,
            stream=False
        )
        
        processing_time = time.time() - start_time
        llm_raw_response = response.choices[0].message.content.strip()
        
        print(f"【Test.py】API调用成功，耗时: {processing_time:.1f}秒")
        print(f"【Test.py】原始响应: {llm_raw_response[:200]}...")
        
        self.memory.add_message("assistant", llm_raw_response)
        
        # 提取工具调用
        tool_data = self.extract_tool_call(llm_raw_response)
        if tool_data:
            print(f"【Test.py】检测到工具调用: {tool_data['action']}")
            tool_result = self.toolkit.call_tool(tool_data["action"], tool_data["parameters"])
            return tool_result
        else:
            print("【Test.py】直接返回文本响应")
            return llm_raw_response

    except Exception as e:
        error_msg = f"Test.py处理失败：{str(e)}"
        print(f"【Test.py错误】{error_msg}")
        import traceback
        print(f"【Test.py错误详情】{traceback.format_exc()}")
        return error_msg

if __name__ == "__main__":
    agent = DeepseekAgent()
    agent.process_input()
