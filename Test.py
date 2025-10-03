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
    # ... 保持原有的AgentMemory类代码不变

class Toolkit:
    """工具包类，包含所有可用工具的实现"""
    # ... 保持原有的Toolkit类代码不变

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
        """处理用户输入，调用Agent并渲染多色内容"""
        self.memory.add_message("user", user_input)
        messages = self.memory.get_messages()

        try:
            print("思考中...\n", "thinking")
            # ✅ 改为旧版本API调用
            response = openai.ChatCompletion.create(
                model=self.model_id,
                messages=messages,
                stream=False
            )
            llm_raw_response = response.choices[0].message.content.strip()
            self.memory.add_message("assistant", llm_raw_response)
            print(f"【调试】LLM原始响应：{llm_raw_response[:200]}...\n\n", "debug")
            
            tool_data = self.extract_tool_call(llm_raw_response)
            if tool_data:
                print(f"调用工具：{tool_data['action']}\n", "tool")
                print(f"【调试】准备调用工具：{tool_data['action']}，参数：{tool_data['parameters']}")
                tool_result = self.toolkit.call_tool(tool_data["action"], tool_data["parameters"])
                print(f"工具返回结果：\n{tool_result}\n\n", "tool_result")
                print(f"【调试】工具返回结果：{tool_result}")

        except Exception as e:
            error_msg = f"处理失败：{str(e)}\n"
            print(error_msg, "error")
            self.memory.add_message("system", error_msg)

if __name__ == "__main__":
    agent = DeepseekAgent()
    agent.process_input()
