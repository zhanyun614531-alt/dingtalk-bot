import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

# 加载环境变量
load_dotenv()


class GoogleCalendarManager:
    """Google日历管理器"""

    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        # 从环境变量构建credentials字典
        self.credentials_info = self._get_credentials_from_env()
        self.service = self._authenticate()

    def _get_credentials_from_env(self):
        """从环境变量构建credentials字典"""
        # 注意：这里从环境变量读取，而不是本地文件
        credentials_info = {
            "installed": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "project_id": os.environ.get("GOOGLE_PROJECT_ID", ""),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "redirect_uris": [os.environ.get("GOOGLE_REDIRECT_URIS", "http://localhost")]
            }
        }
        return credentials_info

    def _authenticate(self):
        """Google日历认证 - 适配Render环境"""
        creds = None

        # 在Render上，我们无法永久保存token.pickle，因此主要依赖环境变量中的令牌
        # 检查环境变量中是否已有令牌（适用于长期运行的服务）
        token_json = os.environ.get('GOOGLE_TOKEN_JSON')
        if token_json:
            try:
                token_info = json.loads(token_json)
                creds = Credentials.from_authorized_user_info(token_info, self.SCOPES)
            except Exception as e:
                print(f"从环境变量加载令牌失败: {e}")

        # 如果令牌不存在或已过期，则需要进行OAuth流程
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # 如果需要，可以在这里更新环境中的令牌（如果您的部署支持）
                except Exception as e:
                    print(f"刷新令牌失败: {e}")
                    creds = None
            else:
                # 在Render上，我们需要一个方法来处理首次授权
                # 由于Render是无状态的，这可能需要在本地完成一次，然后捕获令牌并设置为环境变量
                print("⚠️  需要在本地完成首次OAuth授权。")
                print("1. 在本地运行应用完成授权")
                print("2. 授权后，将生成的token.pickle内容（JSON格式）设置为Render的GOOGLE_TOKEN_JSON环境变量")
                # 对于生产环境，可以考虑更成熟的令牌管理方案
                return None

        return build('calendar', 'v3', credentials=creds)

    def create_event(self, summary, description="", start_time=None, end_time=None,
                     reminder_minutes=30, priority="medium", status="confirmed"):
        """
        创建日历事件

        Args:
            summary: 事件标题
            description: 事件描述
            start_time: 开始时间 (datetime对象)
            end_time: 结束时间 (datetime对象)
            reminder_minutes: 提前提醒时间（分钟）
            priority: 优先级 (low, medium, high)
            status: 状态 (confirmed, tentative, cancelled)
        """
        if not start_time:
            start_time = datetime.now() + timedelta(hours=1)
        if not end_time:
            end_time = start_time + timedelta(hours=1)

        # 优先级映射
        priority_map = {"low": "5", "medium": "3", "high": "1"}

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Shanghai',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Shanghai',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': reminder_minutes},
                ],
            },
            'extendedProperties': {
                'private': {
                    'priority': priority,
                    'status': status
                }
            }
        }

        try:
            event = self.service.events().insert(calendarId='primary', body=event).execute()
            return {
                "success": True,
                "event_id": event['id'],
                "html_link": event.get('htmlLink', ''),
                "message": f"✅ 日历事件创建成功: {summary}"
            }
        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 创建日历事件失败: {error}"
            }

    def query_events(self, days=30, max_results=50):
        """
        查询未来一段时间内的日历事件

        Args:
            days: 查询未来多少天
            max_results: 最大返回结果数
        """
        # 修复：使用timezone-aware的datetime对象
        now = datetime.now(timezone.utc).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=future,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            if not events:
                return {
                    "success": True,
                    "events": [],
                    "message": "📭 未来{}天内没有日历事件".format(days)
                }

            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                priority = event.get('extendedProperties', {}).get('private', {}).get('priority', 'medium')
                status = event.get('extendedProperties', {}).get('private', {}).get('status', 'confirmed')

                formatted_events.append({
                    'id': event['id'],
                    'summary': event.get('summary', '无标题'),
                    'description': event.get('description', ''),
                    'start': start,
                    'end': end,
                    'priority': priority,
                    'status': status
                })

            return {
                "success": True,
                "events": formatted_events,
                "count": len(formatted_events),
                "message": f"📅 找到{len(formatted_events)}个未来{days}天内的事件"
            }

        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 查询日历事件失败: {error}"
            }

    def update_event_status(self, event_id, status="completed"):
        """更新事件状态"""
        try:
            # 先获取事件
            event = self.service.events().get(calendarId='primary', eventId=event_id).execute()

            # 更新状态
            if 'extendedProperties' not in event:
                event['extendedProperties'] = {'private': {}}
            elif 'private' not in event['extendedProperties']:
                event['extendedProperties']['private'] = {}

            event['extendedProperties']['private']['status'] = status

            # 如果是完成状态，可以添加完成标记
            if status == "completed":
                event['summary'] = "✅ " + event.get('summary', '')

            updated_event = self.service.events().update(
                calendarId='primary', eventId=event_id, body=event).execute()

            return {
                "success": True,
                "message": f"✅ 事件状态已更新为: {status}"
            }

        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 更新事件状态失败: {error}"
            }

    def delete_event(self, event_id):
        """删除日历事件"""
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            return {
                "success": True,
                "message": "🗑️ 日历事件已成功删除"
            }
        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 删除日历事件失败: {error}"
            }

    def delete_event_by_summary(self, summary, days=30):
        """根据事件标题删除事件（支持模糊匹配）"""
        try:
            # 先查询匹配的事件
            result = self.query_events(days=days, max_results=100)
            if not result["success"]:
                return result

            matching_events = []
            for event in result["events"]:
                if summary.lower() in event['summary'].lower():
                    matching_events.append(event)

            if not matching_events:
                return {
                    "success": False,
                    "error": f"❌ 未找到包含 '{summary}' 的事件"
                }

            # 删除匹配的事件
            deleted_count = 0
            for event in matching_events:
                delete_result = self.delete_event(event['id'])
                if delete_result["success"]:
                    deleted_count += 1

            return {
                "success": True,
                "message": f"🗑️ 成功删除 {deleted_count} 个匹配事件",
                "deleted_count": deleted_count
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"❌ 删除事件时出错: {str(e)}"
            }


class DeepseekAgent:
    """智能助手Agent"""

    def __init__(self):
        self.client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
            api_key=os.environ.get("ARK_API_KEY")
        )
        self.model_id = "bot-20250907084333-cbvff"

        # 初始化Google日历管理器
        self.calendar_manager = GoogleCalendarManager()

        # 更新系统提示词（添加删除功能）
        self.system_prompt = """你是一个智能助手，具备工具调用能力。

可用工具：
1. 天气查询：{"action": "get_weather", "parameters": {"city": "城市名称"}}
2. 计算器：{"action": "calculator", "parameters": {"expression": "数学表达式"}}
3. 发送邮件：{"action": "send_email", "parameters": {"to": "收件邮箱", "subject": "邮件主题", "body": "邮件内容"}}
4. 创建日历事件：{"action": "create_calendar_event", "parameters": {"summary": "事件标题", "description": "事件描述", "start_time": "开始时间(YYYY-MM-DD HH:MM)", "end_time": "结束时间(YYYY-MM-DD HH:MM)", "reminder_minutes": 30, "priority": "medium"}}
5. 查询日历事件：{"action": "query_calendar_events", "parameters": {"days": 30, "max_results": 20}}
6. 更新事件状态：{"action": "update_event_status", "parameters": {"event_id": "事件ID", "status": "completed"}}
7. 删除日历事件：{"action": "delete_calendar_event", "parameters": {"event_id": "事件ID"}}
8. 按标题删除事件：{"action": "delete_event_by_summary", "parameters": {"summary": "事件标题关键词", "days": 30}}

规则：
1. 需要调用工具时，返回```json和```包裹的JSON
2. 不需要工具时，直接回答问题
3. 用简洁明了的方式回答
4. 对于时间相关的请求，优先使用日历工具
5. 优先级说明：low(低), medium(中), high(高)
6. 状态说明：confirmed(待办), completed(完成), cancelled(取消)
7. 删除事件时，如果不知道具体事件ID，可以使用按标题删除功能

时间格式示例：
- "2025-10-10 14:30"
- "2025-12-25 09:00"

删除事件示例：
- 知道事件ID: {"action": "delete_calendar_event", "parameters": {"event_id": "abc123"}}
- 知道标题: {"action": "delete_event_by_summary", "parameters": {"summary": "团队会议"}}
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
        """发送邮件 - 使用 Brevo API"""
        if not all([to, subject, body]):
            return "收件人、主题或正文不能为空"

        brevo_api_key = os.environ.get("BREVO_API_KEY")
        sender_email = os.environ.get("BREVO_SENDER_EMAIL")
        sender_name = os.environ.get("BREVO_SENDER_NAME", "智能助手")

        if not brevo_api_key:
            return "邮件服务未配置"

        try:
            url = "https://api.brevo.com/v3/smtp/email"

            payload = {
                "sender": {
                    "name": sender_name,
                    "email": sender_email
                },
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2>{subject}</h2>
                    <div style="white-space: pre-line; padding: 20px; background: #f9f9f9; border-radius: 5px;">
                        {body}
                    </div>
                    <p style="color: #999; font-size: 12px; margin-top: 20px;">
                        此邮件由智能助手自动发送
                    </p>
                </div>
                """,
                "textContent": body
            }

            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": brevo_api_key
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 201:
                return f"📧 邮件发送成功！已发送至：{to}"
            else:
                error_data = response.json()
                return f"❌ 邮件发送失败：{error_data.get('message', 'Unknown error')}"

        except Exception as e:
            return f"❌ 邮件发送异常：{str(e)}"

    def create_calendar_event(self, summary, description="", start_time=None, end_time=None,
                              reminder_minutes=30, priority="medium"):
        """创建Google日历事件"""
        try:
            # 解析时间字符串
            start_dt = None
            end_dt = None

            if start_time:
                start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            if end_time:
                end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M")

            result = self.calendar_manager.create_event(
                summary=summary,
                description=description,
                start_time=start_dt,
                end_time=end_dt,
                reminder_minutes=reminder_minutes,
                priority=priority
            )

            return result.get("message", "日历事件创建完成")

        except Exception as e:
            return f"❌ 创建日历事件时出错: {str(e)}"

    def query_calendar_events(self, days=30, max_results=20):
        """查询日历事件"""
        try:
            result = self.calendar_manager.query_events(days=days, max_results=max_results)

            if not result["success"]:
                return result["error"]

            if not result["events"]:
                return result["message"]

            # 格式化输出事件列表
            events_text = f"📅 未来{days}天内的日历事件 ({result['count']}个):\n\n"
            for i, event in enumerate(result["events"], 1):
                start_time = event['start'].replace('T', ' ').split('+')[0]
                priority_emoji = {"low": "⚪", "medium": "🟡", "high": "🔴"}.get(event['priority'], '🟡')
                status_emoji = {"confirmed": "⏳", "completed": "✅", "cancelled": "❌"}.get(event['status'], '⏳')

                events_text += f"{i}. {status_emoji}{priority_emoji} {event['summary']}\n"
                events_text += f"   时间: {start_time}\n"
                if event['description']:
                    events_text += f"   描述: {event['description'][:50]}...\n"
                events_text += f"   状态: {event['status']} | 优先级: {event['priority']}\n"
                events_text += f"   ID: {event['id'][:8]}...\n\n"

            return events_text

        except Exception as e:
            return f"❌ 查询日历事件时出错: {str(e)}"

    def update_event_status(self, event_id, status="completed"):
        """更新事件状态"""
        try:
            result = self.calendar_manager.update_event_status(event_id, status)
            return result.get("message", result.get("error", "状态更新完成"))
        except Exception as e:
            return f"❌ 更新事件状态时出错: {str(e)}"

    def delete_calendar_event(self, event_id):
        """删除日历事件（通过事件ID）"""
        try:
            result = self.calendar_manager.delete_event(event_id)
            return result.get("message", result.get("error", "删除完成"))
        except Exception as e:
            return f"❌ 删除日历事件时出错: {str(e)}"

    def delete_event_by_summary(self, summary, days=30):
        """根据标题删除日历事件"""
        try:
            result = self.calendar_manager.delete_event_by_summary(summary, days)
            return result.get("message", result.get("error", "删除完成"))
        except Exception as e:
            return f"❌ 按标题删除事件时出错: {str(e)}"

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
        elif action == "send_email":
            return self.send_email(
                parameters.get("to", ""),
                parameters.get("subject", ""),
                parameters.get("body", "")
            )
        elif action == "create_calendar_event":
            return self.create_calendar_event(
                summary=parameters.get("summary", ""),
                description=parameters.get("description", ""),
                start_time=parameters.get("start_time"),
                end_time=parameters.get("end_time"),
                reminder_minutes=parameters.get("reminder_minutes", 30),
                priority=parameters.get("priority", "medium")
            )
        elif action == "query_calendar_events":
            return self.query_calendar_events(
                days=parameters.get("days", 30),
                max_results=parameters.get("max_results", 20)
            )
        elif action == "update_event_status":
            return self.update_event_status(
                event_id=parameters.get("event_id", ""),
                status=parameters.get("status", "completed")
            )
        elif action == "delete_calendar_event":
            return self.delete_calendar_event(
                event_id=parameters.get("event_id", "")
            )
        elif action == "delete_event_by_summary":
            return self.delete_event_by_summary(
                summary=parameters.get("summary", ""),
                days=parameters.get("days", 30)
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


# 测试函数
def test_calendar_features():
    """测试日历功能"""
    test_cases = [
        "创建日历事件：明天下午2点团队会议，讨论项目进度，提前15分钟提醒我",
        "查看我未来一周的日程安排",
        "下周一上午9点提醒我提交月度报告，这个很重要",
        "查询我未来一个月的所有待办事项",
        "删除标题包含'团队会议'的所有事件",
        "创建一个高优先级的提醒：周五前完成产品设计文档"
    ]

    print("🧪 测试Google日历功能")
    print("=" * 50)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. 测试: {test_case}")
        result = smart_assistant(test_case)
        print(f"结果: {result}")
        print("-" * 30)


if __name__ == "__main__":
    # 测试日历功能
    # test_calendar_features()
    pass
