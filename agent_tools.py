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
import pytz

# 加载环境变量
load_dotenv()


class GoogleCalendarManager:
    """Google日历管理器 - 适配Render部署"""

    def __init__(self):
        # 需要添加Tasks API的权限
        self.SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/tasks'  # 新增Tasks API权限
        ]
        self.beijing_tz = pytz.timezone('Asia/Shanghai')  # 北京时区
        self.credentials_info = self._get_credentials_from_env()
        self.service = self._authenticate()
        self.tasks_service = build('tasks', 'v1', credentials=self.service._http.credentials)  # Tasks服务

    def _get_credentials_from_env(self):
        """从环境变量构建credentials字典"""
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

        # 方案1: 从环境变量加载令牌（生产环境推荐）
        token_json = os.environ.get('GOOGLE_TOKEN_JSON')
        if token_json:
            try:
                token_info = json.loads(token_json)
                creds = Credentials.from_authorized_user_info(token_info, self.SCOPES)
                print("✅ 从环境变量加载令牌成功")
            except Exception as e:
                print(f"❌ 从环境变量加载令牌失败: {e}")

        # 方案2: 从本地token.pickle文件加载（开发环境）
        if not creds and os.path.exists('token.pickle'):
            try:
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
                print("✅ 从本地token.pickle加载令牌成功")
            except Exception as e:
                print(f"❌ 从token.pickle加载令牌失败: {e}")

        # 检查令牌有效性
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("✅ 令牌刷新成功")
            except Exception as e:
                print(f"❌ 令牌刷新失败: {e}")
                creds = None

        # 如果没有有效令牌，启动OAuth流程
        if not creds:
            print("🚀 启动OAuth授权流程...")
            try:
                flow = InstalledAppFlow.from_client_config(
                    self.credentials_info, self.SCOPES)
                creds = flow.run_local_server(port=0)

                # 保存令牌供后续使用
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
                print("✅ OAuth授权成功，令牌已保存")

            except Exception as e:
                print(f"❌ OAuth授权失败: {e}")
                return None

        return build('calendar', 'v3', credentials=creds)

    # ========== 任务管理功能 ==========

    def get_task_lists(self):
        """获取任务列表"""
        try:
            task_lists = self.tasks_service.tasklists().list().execute()
            return task_lists.get('items', [])
        except HttpError as error:
            print(f"❌ 获取任务列表失败: {error}")
            return []

    def get_or_create_default_task_list(self):
        """获取或创建默认任务列表"""
        task_lists = self.get_task_lists()
        if task_lists:
            # 返回第一个任务列表
            return task_lists[0]['id']
        else:
            # 创建新的任务列表
            try:
                task_list = self.tasks_service.tasklists().insert(body={
                    'title': '智能助手任务'
                }).execute()
                return task_list['id']
            except HttpError as error:
                print(f"❌ 创建任务列表失败: {error}")
                return None

    def create_task(self, title, notes="", due_date=None, reminder_minutes=60, priority="medium"):
        """
        创建Google任务

        Args:
            title: 任务标题
            notes: 任务描述
            due_date: 截止日期 (datetime对象)
            reminder_minutes: 提前提醒时间（分钟）
            priority: 优先级 (low, medium, high)
        """
        try:
            task_list_id = self.get_or_create_default_task_list()
            if not task_list_id:
                return {
                    "success": False,
                    "error": "❌ 无法获取任务列表"
                }

            # 优先级映射
            priority_map = {"low": "1", "medium": "3", "high": "5"}

            task_body = {
                'title': title,
                'notes': notes,
                'status': 'needsAction'  # 未完成状态
            }

            # 设置截止日期
            if due_date:
                # 确保使用北京时区
                if due_date.tzinfo is None:
                    due_date = self.beijing_tz.localize(due_date)
                # Google Tasks使用RFC 3339格式
                task_body['due'] = due_date.isoformat()

            # 设置优先级
            task_body['priority'] = priority_map.get(priority, "3")

            task = self.tasks_service.tasks().insert(
                tasklist=task_list_id,
                body=task_body
            ).execute()

            return {
                "success": True,
                "task_id": task['id'],
                "message": f"✅ 任务创建成功: {title}"
            }

        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 创建任务失败: {error}"
            }

    def query_tasks(self, show_completed=False, max_results=50):
        """
        查询任务

        Args:
            show_completed: 是否显示已完成的任务
            max_results: 最大返回结果数
        """
        try:
            task_list_id = self.get_or_create_default_task_list()
            if not task_list_id:
                return {
                    "success": False,
                    "error": "❌ 无法获取任务列表"
                }

            # 构建查询参数
            params = {
                'tasklist': task_list_id,
                'maxResults': max_results
            }

            if not show_completed:
                params['showCompleted'] = False
                params['showHidden'] = False

            tasks_result = self.tasks_service.tasks().list(**params).execute()
            tasks = tasks_result.get('items', [])

            if not tasks:
                return {
                    "success": True,
                    "tasks": [],
                    "message": "📭 没有找到任务"
                }

            formatted_tasks = []
            for task in tasks:
                # 处理截止日期
                due_date = task.get('due')
                if due_date:
                    due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    due_beijing = due_dt.astimezone(self.beijing_tz)
                    due_display = due_beijing.strftime('%Y-%m-%d %H:%M')
                else:
                    due_display = "无截止日期"

                # 处理优先级
                priority_map = {"1": "low", "3": "medium", "5": "high"}
                priority = priority_map.get(task.get('priority', '3'), 'medium')

                # 处理状态
                status = "completed" if task.get('status') == 'completed' else "needsAction"

                formatted_tasks.append({
                    'id': task['id'],
                    'title': task['title'],
                    'notes': task.get('notes', ''),
                    'due': due_display,
                    'priority': priority,
                    'status': status,
                    'completed': task.get('completed') if status == "completed" else None
                })

            return {
                "success": True,
                "tasks": formatted_tasks,
                "count": len(formatted_tasks),
                "message": f"📋 找到{len(formatted_tasks)}个任务"
            }

        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 查询任务失败: {error}"
            }

    def update_task_status(self, task_id, status="completed"):
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 状态 (completed, needsAction)
        """
        try:
            task_list_id = self.get_or_create_default_task_list()
            if not task_list_id:
                return {
                    "success": False,
                    "error": "❌ 无法获取任务列表"
                }

            # 先获取任务
            task = self.tasks_service.tasks().get(
                tasklist=task_list_id,
                task=task_id
            ).execute()

            # 更新状态
            if status == "completed":
                task['status'] = 'completed'
                task['completed'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            else:
                task['status'] = 'needsAction'
                task.pop('completed', None)  # 移除完成时间

            updated_task = self.tasks_service.tasks().update(
                tasklist=task_list_id,
                task=task_id,
                body=task
            ).execute()

            status_text = "完成" if status == "completed" else "重新打开"
            return {
                "success": True,
                "message": f"✅ 任务已标记为{status_text}"
            }

        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 更新任务状态失败: {error}"
            }

    def delete_task(self, task_id):
        """删除任务"""
        try:
            task_list_id = self.get_or_create_default_task_list()
            if not task_list_id:
                return {
                    "success": False,
                    "error": "❌ 无法获取任务列表"
                }

            self.tasks_service.tasks().delete(
                tasklist=task_list_id,
                task=task_id
            ).execute()

            return {
                "success": True,
                "message": "🗑️ 任务已成功删除"
            }

        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 删除任务失败: {error}"
            }

    def delete_task_by_title(self, title_keyword, show_completed=True):
        """根据标题关键词删除任务"""
        try:
            result = self.query_tasks(show_completed=show_completed, max_results=100)
            if not result["success"]:
                return result

            matching_tasks = []
            for task in result["tasks"]:
                if title_keyword.lower() in task['title'].lower():
                    matching_tasks.append(task)

            if not matching_tasks:
                return {
                    "success": False,
                    "error": f"❌ 未找到包含 '{title_keyword}' 的任务"
                }

            # 删除匹配的任务
            deleted_count = 0
            for task in matching_tasks:
                delete_result = self.delete_task(task['id'])
                if delete_result["success"]:
                    deleted_count += 1

            return {
                "success": True,
                "message": f"🗑️ 成功删除 {deleted_count} 个匹配任务",
                "deleted_count": deleted_count
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"❌ 删除任务时出错: {str(e)}"
            }

    # ========== 原有日历事件功能保持不变 ==========
    # [保留所有原有的日历事件方法：create_event, query_events, update_event_status, delete_event, delete_event_by_summary]
    # 这里省略原有代码以节省空间，实际使用时请保留

    def create_event(self, summary, description="", start_time=None, end_time=None,
                     reminder_minutes=30, priority="medium", status="confirmed"):
        """创建日历事件 - 修复时区问题"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def query_events(self, days=30, max_results=50):
        """查询日历事件 - 修复时区问题"""
        # [原有代码保持不变]
        # ... 省略具体实现

    # 其他原有方法...
    # ... 省略其他原有方法


class DeepseekAgent:
    """智能助手Agent - 添加任务管理功能"""

    def __init__(self):
        self.client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
            api_key=os.environ.get("ARK_API_KEY")
        )
        self.model_id = "bot-20250907084333-cbvff"

        # 初始化Google日历管理器
        self.calendar_manager = GoogleCalendarManager()

        # 更新系统提示词（添加任务管理功能）
        self.system_prompt = """你是一个智能助手，具备工具调用能力。

可用工具：
【日历事件功能】
1. 创建日历事件：{"action": "create_calendar_event", "parameters": {"summary": "事件标题", "description": "事件描述", "start_time": "开始时间(YYYY-MM-DD HH:MM)", "end_time": "结束时间(YYYY-MM-DD HH:MM)", "reminder_minutes": 30, "priority": "medium"}}
2. 查询日历事件：{"action": "query_calendar_events", "parameters": {"days": 30, "max_results": 20}}
3. 更新事件状态：{"action": "update_event_status", "parameters": {"event_id": "事件ID", "status": "completed"}}
4. 删除日历事件：{"action": "delete_calendar_event", "parameters": {"event_id": "事件ID"}}
5. 按标题删除事件：{"action": "delete_event_by_summary", "parameters": {"summary": "事件标题关键词", "days": 30}}

【任务管理功能】
6. 创建任务：{"action": "create_task", "parameters": {"title": "任务标题", "notes": "任务描述", "due_date": "截止时间(YYYY-MM-DD HH:MM)", "reminder_minutes": 60, "priority": "medium"}}
7. 查询任务：{"action": "query_tasks", "parameters": {"show_completed": false, "max_results": 20}}
8. 更新任务状态：{"action": "update_task_status", "parameters": {"task_id": "任务ID", "status": "completed"}}
9. 删除任务：{"action": "delete_task", "parameters": {"task_id": "任务ID"}}
10. 按标题删除任务：{"action": "delete_task_by_title", "parameters": {"title_keyword": "任务标题关键词"}}

【其他功能】
11. 天气查询：{"action": "get_weather", "parameters": {"city": "城市名称"}}
12. 计算器：{"action": "calculator", "parameters": {"expression": "数学表达式"}}
13. 发送邮件：{"action": "send_email", "parameters": {"to": "收件邮箱", "subject": "邮件主题", "body": "邮件内容"}}

规则：
1. 需要调用工具时，返回```json和```包裹的JSON
2. 不需要工具时，直接回答问题
3. 用简洁明了的方式回答
4. 对于时间安排，使用日历事件；对于待办事项，使用任务
5. 优先级说明：low(低), medium(中), high(高)
6. 状态说明：needsAction(待办), completed(完成)

时间格式示例：
- "2025-10-10 14:30"
- "2025-12-25 09:00"

使用场景：
- 会议、约会 → 使用日历事件
- 待办事项、个人任务 → 使用任务
- 需要具体时间段的 → 日历事件
- 只需要截止日期的 → 任务
"""

    # ========== 任务管理工具方法 ==========

    def create_task(self, title, notes="", due_date=None, reminder_minutes=60, priority="medium"):
        """创建Google任务"""
        try:
            # 解析时间字符串
            due_dt = None
            if due_date:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d %H:%M")

            result = self.calendar_manager.create_task(
                title=title,
                notes=notes,
                due_date=due_dt,
                reminder_minutes=reminder_minutes,
                priority=priority
            )

            return result.get("message", "任务创建完成")

        except Exception as e:
            return f"❌ 创建任务时出错: {str(e)}"

    def query_tasks(self, show_completed=False, max_results=20):
        """查询任务"""
        try:
            result = self.calendar_manager.query_tasks(
                show_completed=show_completed,
                max_results=max_results
            )

            if not result["success"]:
                return result["error"]

            if not result["tasks"]:
                return result["message"]

            # 格式化输出任务列表
            status_text = "所有" if show_completed else "待办"
            tasks_text = f"📋 {status_text}任务列表 ({result['count']}个):\n\n"

            for i, task in enumerate(result["tasks"], 1):
                status_emoji = "✅" if task['status'] == "completed" else "⏳"
                priority_emoji = {"low": "⚪", "medium": "🟡", "high": "🔴"}.get(task['priority'], '🟡')

                tasks_text += f"{i}. {status_emoji}{priority_emoji} {task['title']}\n"
                tasks_text += f"   截止: {task['due']}\n"
                if task['notes']:
                    tasks_text += f"   描述: {task['notes'][:50]}...\n"
                tasks_text += f"   状态: {task['status']} | 优先级: {task['priority']}\n"
                tasks_text += f"   ID: {task['id'][:8]}...\n\n"

            return tasks_text

        except Exception as e:
            return f"❌ 查询任务时出错: {str(e)}"

    def update_task_status(self, task_id, status="completed"):
        """更新任务状态"""
        try:
            result = self.calendar_manager.update_task_status(task_id, status)
            return result.get("message", result.get("error", "状态更新完成"))
        except Exception as e:
            return f"❌ 更新任务状态时出错: {str(e)}"

    def delete_task(self, task_id):
        """删除任务（通过任务ID）"""
        try:
            result = self.calendar_manager.delete_task(task_id)
            return result.get("message", result.get("error", "删除完成"))
        except Exception as e:
            return f"❌ 删除任务时出错: {str(e)}"

    def delete_task_by_title(self, title_keyword):
        """根据标题删除任务"""
        try:
            result = self.calendar_manager.delete_task_by_title(title_keyword)
            return result.get("message", result.get("error", "删除完成"))
        except Exception as e:
            return f"❌ 按标题删除任务时出错: {str(e)}"

    # ========== 原有工具方法保持不变 ==========
    # [保留所有原有的工具方法]

    def get_weather(self, city):
        """获取天气信息"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def calculator(self, expression):
        """执行数学计算"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def send_email(self, to, subject, body):
        """发送邮件"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def create_calendar_event(self, summary, description="", start_time=None, end_time=None,
                              reminder_minutes=30, priority="medium"):
        """创建Google日历事件"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def query_calendar_events(self, days=30, max_results=20):
        """查询日历事件"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def update_event_status(self, event_id, status="completed"):
        """更新事件状态"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def delete_calendar_event(self, event_id):
        """删除日历事件"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def delete_event_by_summary(self, summary, days=30):
        """根据标题删除日历事件"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def extract_tool_call(self, llm_response):
        """从LLM响应中提取工具调用指令"""
        # [原有代码保持不变]
        # ... 省略具体实现

    def call_tool(self, action, parameters):
        """统一工具调用入口 - 添加任务管理功能"""
        if action == "create_task":
            return self.create_task(
                title=parameters.get("title", ""),
                notes=parameters.get("notes", ""),
                due_date=parameters.get("due_date"),
                reminder_minutes=parameters.get("reminder_minutes", 60),
                priority=parameters.get("priority", "medium")
            )
        elif action == "query_tasks":
            return self.query_tasks(
                show_completed=parameters.get("show_completed", False),
                max_results=parameters.get("max_results", 20)
            )
        elif action == "update_task_status":
            return self.update_task_status(
                task_id=parameters.get("task_id", ""),
                status=parameters.get("status", "completed")
            )
        elif action == "delete_task":
            return self.delete_task(
                task_id=parameters.get("task_id", "")
            )
        elif action == "delete_task_by_title":
            return self.delete_task_by_title(
                title_keyword=parameters.get("title_keyword", "")
            )
        # 原有的其他工具调用
        elif action == "get_weather":
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
def test_all_features():
    """测试所有功能"""
    test_cases = [
        # 日历事件测试
        "创建日历事件：明天下午2点团队会议，讨论项目进度，提前15分钟提醒我",
        "查看我未来一周的日程安排",

        # 任务管理测试
        "创建任务：周五前完成产品设计文档，这是一个高优先级的任务",
        "创建任务：下周一提交月度报告，提前一天提醒我",
        "查看我所有的待办任务",
        "标记第一个任务为完成",
        "删除标题包含'报告'的任务",

        # 混合场景测试
        "下周三下午3点有个客户会议，同时记得提醒我提前准备材料"
    ]

    print("🧪 测试所有Google日历和任务功能")
    print("=" * 50)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. 测试: {test_case}")
        result = smart_assistant(test_case)
        print(f"结果: {result}")
        print("-" * 30)


if __name__ == "__main__":
    # 测试所有功能
    test_all_features()
