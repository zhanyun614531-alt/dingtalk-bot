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
from playwright.async_api import async_playwright
import re
import asyncio

# 加载环境变量
load_dotenv()


class StockAnalysisPDFAgent:
    """股票分析PDF生成器 - 纯内存操作"""

    def __init__(self):
        # 豆包客户端配置
        self.doubao_client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
            api_key=os.environ.get("ARK_API_KEY")
        )
        self.model_id = "bot-20250907084333-cbvff"

        # 系统提示词 - AI金融分析师角色
        self.system_prompt = """你是一位顶级的金融分析师，你的任务是为客户撰写一份专业、深入、数据驱动且观点明确的股票研究报告。你的分析必须客观、严谨，并结合基本面、技术面和市场情绪进行综合判断。每个部份不超过200字。

请严格遵循以下结构和要求，生成一份完整的HTML格式的股票分析报告：

报告结构与格式要求：

1. 报告摘要 (Report Summary)
   - 关键投资亮点：以要点形式列出3-5个最重要的投资亮点或关注点
   - 投资者画像：指出该股票适合哪类投资者，并说明建议的投资时间周期

2. 深度分析 (In-Depth Analysis)
   2.1 公司与行业分析
     - 商业模式：公司如何创造收入？核心产品、服务和主要客户群体
     - 行业格局与竞争优势：行业驱动因素、市场规模、增长前景、主要竞争对手、护城河分析

   2.2 财务健康状况与业绩
     - 近期业绩：注明最近财报日期，总结业绩超预期/不及预期的关键点
     - 核心财务趋势：过去3-5年收入、净利润和利润率趋势
     - 关键财务比率分析：提供P/S、P/B、PEG、债务权益比等，并与行业比较

   2.3 增长前景与催化剂
     - 增长战略：新产品发布、市场扩张、并购等计划
     - 潜在催化剂：未来6-12个月内可能影响股价的事件

   2.4 技术分析与市场情绪
     - 价格行为与趋势：当前趋势、移动平均线状态
     - 关键价位：支撑位和阻力位分析
     - 成交量分析：近期成交量趋势
     - 市场情绪与持仓：分析师评级分布、机构持仓趋势

   2.5 风险评估
     - 核心业务风险：主要经营风险
     - 宏观与行业风险：经济周期、政策变化等影响
     - 危险信号：需要警惕的负面信号

HTML格式要求：
- 使用专业的金融报告样式
- 包含清晰的章节分隔
- 重要数据使用突出显示
- 风险提示使用醒目标记
- 确保响应式设计，适应PDF输出

重要：直接输出完整的HTML代码，不要包含任何代码块标记（如```html或```）"""

    def clean_html_content(self, html_content):
        """清理HTML内容中的代码块标记和其他不需要的字符"""
        print("🧹 清理HTML内容中的代码块标记...")

        # 移除代码块标记
        cleaned_content = re.sub(r'^```html\s*', '', html_content)
        cleaned_content = re.sub(r'\s*```$', '', cleaned_content)
        cleaned_content = cleaned_content.replace('```html', '').replace('```', '')

        # 确保内容以正确的HTML结构开始
        if not cleaned_content.strip().startswith('<!DOCTYPE html>') and not cleaned_content.strip().startswith(
                '<html'):
            # 包装成完整的专业金融报告HTML结构
            cleaned_content = self.wrap_financial_report_html(cleaned_content)

        print(f"✅ HTML内容清理完成，长度: {len(cleaned_content)} 字符")
        return cleaned_content

    def wrap_financial_report_html(self, content):
        """将内容包装成专业的金融报告HTML结构"""
        current_date = datetime.now().strftime("%Y年%m月%d日")

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票投资分析报告</title>
    <style>
        /* 专业金融报告样式 */
        body {{ 
            font-family: 'Arial', 'Microsoft YaHei', 'PingFang SC', sans-serif; 
            margin: 0;
            padding: 0;
            color: #333;
            line-height: 1.6;
            background: #f8f9fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 30px 40px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 28px;
            font-weight: 700;
        }}
        .header .subtitle {{
            font-size: 16px;
            opacity: 0.9;
            margin-bottom: 15px;
        }}
        .report-meta {{
            display: flex;
            justify-content: center;
            gap: 30px;
            font-size: 14px;
            opacity: 0.8;
        }}
        .content {{
            padding: 40px;
        }}
        .section {{
            margin-bottom: 40px;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            overflow: hidden;
        }}
        .section-header {{
            background: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e9ecef;
            font-weight: 600;
            color: #2c3e50;
            font-size: 18px;
        }}
        .section-content {{
            padding: 20px;
        }}
        .highlight-box {{
            background: #e8f4fd;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .risk-warning {{
            background: #ffeaa7;
            border-left: 4px solid #fdcb6e;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 14px;
        }}
        .data-table th,
        .data-table td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        .data-table th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .key-metric {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            margin: 2px;
            font-weight: 600;
        }}
        .positive {{
            background: #27ae60;
        }}
        .negative {{
            background: #e74c3c;
        }}
        .neutral {{
            background: #95a5a6;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            background: #2c3e50;
            color: white;
            font-size: 12px;
            margin-top: 40px;
        }}
        h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
            margin-top: 30px;
        }}
        h3 {{
            color: #34495e;
            margin-top: 20px;
        }}
        ul, ol {{
            margin: 15px 0;
            padding-left: 25px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        .investment-rating {{
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #27ae60, #2ecc71);
            color: white;
            border-radius: 8px;
            margin: 20px 0;
        }}
        @media print {{
            body {{ background: white; }}
            .container {{ box-shadow: none; }}
            .header {{ background: #2c3e50 !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 股票投资分析报告</h1>
            <div class="subtitle">专业深度分析 · 数据驱动决策</div>
            <div class="report-meta">
                <span>报告日期：{current_date}</span>
                <span>分析师：AI金融研究团队</span>
            </div>
        </div>

        <div class="content">
            {content}
        </div>

        <div class="footer">
            <p>免责声明：本报告基于公开信息分析，仅供参考，不构成投资建议。投资有风险，入市需谨慎。</p>
            <p>报告生成时间：{current_date} • AI金融分析系统</p>
        </div>
    </div>
</body>
</html>"""

    def get_html_from_doubao(self, stock_name_or_code):
        """从豆包获取股票分析HTML报告"""
        print(f"📝 请求豆包生成 {stock_name_or_code} 的股票分析报告...")
    
        user_prompt = f"请为股票 '{stock_name_or_code}' 生成一份完整的专业股票分析报告。"
    
        try:
            response = self.doubao_client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=15000,
                temperature=0.3
            )
            html_content = response.choices[0].message.content.strip()
            print(f"✅ 生成HTML报告（{len(html_content)} 字符）")
    
            # 清理HTML内容
            cleaned_html = self.clean_html_content(html_content)
            return cleaned_html
    
        except Exception as e:
            print(f"❌ 豆包调用失败: {str(e)}")
            # 如果是API错误，可能有更详细的错误信息
            if hasattr(e, 'response'):
                print(f"🔧 API响应详情: {e.response}")
            return None

    async def html_to_pdf(self, html_content):
        """
        使用Playwright将HTML转换为PDF二进制数据（异步版本）

        参数:
        - html_content: HTML内容

        返回:
        - PDF二进制数据，如果失败则返回None
        """
        print("📄 启动浏览器，转换HTML为PDF...")

        try:
            async with async_playwright() as p:
                # 启动浏览器
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']  # 为部署环境添加的参数
                )
                page = await browser.new_page()

                # 设置页面尺寸为A4
                await page.set_viewport_size({"width": 1200, "height": 1697})

                # 加载HTML内容
                await page.set_content(html_content, wait_until='networkidle')

                # 生成PDF二进制数据
                pdf_options = {
                    "format": 'A4',
                    "print_background": True,
                    "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
                    "display_header_footer": False,
                    "prefer_css_page_size": True
                }

                pdf_data = await page.pdf(**pdf_options)
                await browser.close()

                print(f"✅ PDF二进制数据生成成功，大小: {len(pdf_data)} 字节")
                return pdf_data

        except Exception as e:
            print(f"❌ PDF生成失败: {e}")
            return None

    async def generate_stock_report(self, stock_name_or_code):
        """生成股票分析报告的主方法（异步版本）"""
        print(f"🎯 开始生成 {stock_name_or_code} 的分析报告...")

        # 获取HTML内容
        html_content = self.get_html_from_doubao(stock_name_or_code)
        if html_content:
            print(f"✅ 成功获取HTML内容，长度: {len(html_content)} 字符")
            # 转换为PDF二进制数据
            pdf_binary = await self.html_to_pdf(html_content)
            if pdf_binary:
                print(f"✅ {stock_name_or_code} 分析报告生成成功！PDF大小: {len(pdf_binary)} 字节")
                return pdf_binary
            else:
                print(f"❌ {stock_name_or_code} PDF转换失败")
                return None
        else:
            print(f"❌ 无法获取 {stock_name_or_code} 的HTML内容，可能是豆包API调用失败")
            return None


class GoogleCalendarManager:
    """Google日历管理器 - 支持本地credentials.json认证"""

    def __init__(self):
        # 权限范围 - 包含Tasks API
        self.SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/tasks'
        ]
        self.beijing_tz = pytz.timezone('Asia/Shanghai')  # 北京时区
        self.service = self._authenticate()
        if self.service:
            self.tasks_service = build('tasks', 'v1', credentials=self.service._http.credentials)
        else:
            self.tasks_service = None

    def _authenticate(self):
        """Google日历认证 - 优先使用本地credentials.json"""
        creds = None

        # 方案1: 从本地token.pickle文件加载（开发环境优先）
        if os.path.exists('token.pickle'):
            try:
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
                print("✅ 从本地token.pickle加载令牌成功")
            except Exception as e:
                print(f"❌ 从token.pickle加载令牌失败: {e}")

        # 方案2: 从环境变量加载令牌（生产环境）
        if not creds:
            token_json = os.environ.get('GOOGLE_TOKEN_JSON')
            if token_json:
                try:
                    token_info = json.loads(token_json)
                    creds = Credentials.from_authorized_user_info(token_info, self.SCOPES)
                    print("✅ 从环境变量加载令牌成功")
                except Exception as e:
                    print(f"❌ 从环境变量加载令牌失败: {e}")

        # 检查令牌有效性
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("✅ 令牌刷新成功")
            except Exception as e:
                print(f"❌ 令牌刷新失败: {e}")
                creds = None

        # 如果没有有效令牌，启动OAuth流程（使用本地credentials.json）
        if not creds:
            print("🚀 启动本地OAuth授权流程...")
            try:
                # 优先使用本地的credentials.json文件
                if os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    print("✅ 使用credentials.json授权成功")
                else:
                    # 备选方案：从环境变量构建配置
                    credentials_info = self._get_credentials_from_env()
                    flow = InstalledAppFlow.from_client_config(
                        credentials_info, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    print("✅ 使用环境变量配置授权成功")

                # 保存令牌供后续使用
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
                print("✅ OAuth授权成功，令牌已保存到token.pickle")

            except Exception as e:
                print(f"❌ OAuth授权失败: {e}")
                print("💡 请确保：")
                print("   1. 在项目根目录放置credentials.json文件")
                print("   2. 或者在.env文件中配置GOOGLE_CLIENT_ID和GOOGLE_CLIENT_SECRET")
                return None

        return build('calendar', 'v3', credentials=creds)

    def _get_credentials_from_env(self):
        """从环境变量构建credentials字典（备用方案）"""
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

    # ========== 任务管理功能 ==========

    def get_task_lists(self):
        """获取任务列表"""
        if not self.tasks_service:
            return []
        try:
            task_lists = self.tasks_service.tasklists().list().execute()
            return task_lists.get('items', [])
        except HttpError as error:
            print(f"❌ 获取任务列表失败: {error}")
            return []

    def get_or_create_default_task_list(self):
        """获取或创建默认任务列表"""
        if not self.tasks_service:
            return None

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
        """
        if not self.tasks_service:
            return {
                "success": False,
                "error": "❌ 任务服务未初始化"
            }

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
        """
        if not self.tasks_service:
            return {
                "success": False,
                "error": "❌ 任务服务未初始化"
            }

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
        """
        if not self.tasks_service:
            return {
                "success": False,
                "error": "❌ 任务服务未初始化"
            }

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
        if not self.tasks_service:
            return {
                "success": False,
                "error": "❌ 任务服务未初始化"
            }

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

    def delete_tasks_by_time_range(self, start_date=None, end_date=None, show_completed=True):
        """
        根据时间范围批量删除任务

        Args:
            start_date: 开始日期 (datetime对象或字符串 "YYYY-MM-DD")
            end_date: 结束日期 (datetime对象或字符串 "YYYY-MM-DD")
            show_completed: 是否包含已完成的任务
        """
        if not self.tasks_service:
            return {
                "success": False,
                "error": "❌ 任务服务未初始化"
            }

        try:
            # 解析日期参数
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d")

            # 如果没有指定结束日期，默认为开始日期后30天
            if start_date and not end_date:
                end_date = start_date + timedelta(days=30)

            # 如果没有指定开始日期，默认为今天
            if not start_date:
                start_date = datetime.now(self.beijing_tz)

            # 如果没有指定结束日期，默认为开始日期后30天
            if not end_date:
                end_date = start_date + timedelta(days=30)

            # 确保使用北京时区
            if start_date.tzinfo is None:
                start_date = self.beijing_tz.localize(start_date)
            if end_date.tzinfo is None:
                end_date = self.beijing_tz.localize(end_date)

            # 获取所有任务
            result = self.query_tasks(show_completed=show_completed, max_results=500)
            if not result["success"]:
                return result

            matching_tasks = []
            for task in result["tasks"]:
                # 检查任务是否有截止日期
                if task['due'] != "无截止日期":
                    try:
                        # 解析任务的截止日期
                        task_due = datetime.strptime(task['due'], '%Y-%m-%d %H:%M')
                        task_due = self.beijing_tz.localize(task_due)

                        # 检查任务是否在时间范围内
                        if start_date <= task_due <= end_date:
                            matching_tasks.append(task)
                    except ValueError:
                        # 如果日期解析失败，跳过这个任务
                        continue

            if not matching_tasks:
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = end_date.strftime('%Y-%m-%d')
                return {
                    "success": False,
                    "error": f"❌ 在 {start_str} 到 {end_str} 范围内没有找到任务"
                }

            # 删除匹配的任务
            deleted_count = 0
            for task in matching_tasks:
                delete_result = self.delete_task(task['id'])
                if delete_result["success"]:
                    deleted_count += 1

            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            return {
                "success": True,
                "message": f"🗑️ 成功删除 {deleted_count} 个在 {start_str} 到 {end_str} 范围内的任务",
                "deleted_count": deleted_count
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"❌ 按时间范围删除任务时出错: {str(e)}"
            }

    # ========== 日历事件功能 ==========

    def create_event(self, summary, description="", start_time=None, end_time=None,
                     reminder_minutes=30, priority="medium", status="confirmed"):
        """
        创建日历事件 - 修复时区问题
        """
        if not self.service:
            return {
                "success": False,
                "error": "❌ 日历服务未初始化"
            }

        # 确保使用北京时间
        if not start_time:
            start_time = datetime.now(self.beijing_tz) + timedelta(hours=1)
        if not end_time:
            end_time = start_time + timedelta(hours=1)

        # 如果传入的是naive datetime，转换为北京时区
        if start_time.tzinfo is None:
            start_time = self.beijing_tz.localize(start_time)
        if end_time.tzinfo is None:
            end_time = self.beijing_tz.localize(end_time)

        # 优先级映射
        priority_map = {"low": "5", "medium": "3", "high": "1"}

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Shanghai',  # 明确指定时区
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Shanghai',  # 明确指定时区
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
                "message": f"✅ 日历事件创建成功: {summary} (北京时间)"
            }
        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 创建日历事件失败: {error}"
            }

    def query_events(self, days=30, max_results=50):
        """
        查询未来一段时间内的日历事件 - 修复时区问题
        """
        if not self.service:
            return {
                "success": False,
                "error": "❌ 日历服务未初始化"
            }

        # 使用北京时区的时间范围
        now_beijing = datetime.now(self.beijing_tz)
        future_beijing = now_beijing + timedelta(days=days)

        # 转换为RFC3339格式（Google Calendar API要求的格式）
        now_rfc3339 = now_beijing.isoformat()
        future_rfc3339 = future_beijing.isoformat()

        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now_rfc3339,
                timeMax=future_rfc3339,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            if not events:
                return {
                    "success": True,
                    "events": [],
                    "message": f"📭 未来{days}天内没有日历事件"
                }

            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                priority = event.get('extendedProperties', {}).get('private', {}).get('priority', 'medium')
                status = event.get('extendedProperties', {}).get('private', {}).get('status', 'confirmed')

                # 转换时间为北京时间显示
                if 'T' in start:  # 这是日期时间，不是全天事件
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    start_beijing = start_dt.astimezone(self.beijing_tz)
                    start = start_beijing.strftime('%Y-%m-%d %H:%M:%S')

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
                "message": f"📅 找到{len(formatted_events)}个未来{days}天内的事件 (北京时间)"
            }

        except HttpError as error:
            return {
                "success": False,
                "error": f"❌ 查询日历事件失败: {error}"
            }

    def get_current_time_info(self):
        """获取当前时间信息 - 用于调试时区问题"""
        utc_now = datetime.now(timezone.utc)
        beijing_now = datetime.now(self.beijing_tz)
        server_now = datetime.now()

        return {
            "utc_time": utc_now.strftime('%Y-%m-%d %H:%M:%S %Z'),
            "beijing_time": beijing_now.strftime('%Y-%m-%d %H:%M:%S %Z'),
            "server_time": server_now.strftime('%Y-%m-%d %H:%M:%S'),
            "server_timezone": str(server_now.tzinfo) if server_now.tzinfo else "None (naive)"
        }

    def update_event_status(self, event_id, status="completed"):
        """更新事件状态"""
        if not self.service:
            return {
                "success": False,
                "error": "❌ 日历服务未初始化"
            }

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
        if not self.service:
            return {
                "success": False,
                "error": "❌ 日历服务未初始化"
            }

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

    def delete_events_by_time_range(self, start_date=None, end_date=None):
        """
        根据时间范围批量删除日历事件

        Args:
            start_date: 开始日期 (datetime对象或字符串 "YYYY-MM-DD")
            end_date: 结束日期 (datetime对象或字符串 "YYYY-MM-DD")
        """
        if not self.service:
            return {
                "success": False,
                "error": "❌ 日历服务未初始化"
            }

        try:
            # 解析日期参数
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d")

            # 如果没有指定结束日期，默认为开始日期后30天
            if start_date and not end_date:
                end_date = start_date + timedelta(days=30)

            # 如果没有指定开始日期，默认为今天
            if not start_date:
                start_date = datetime.now(self.beijing_tz)

            # 如果没有指定结束日期，默认为开始日期后30天
            if not end_date:
                end_date = start_date + timedelta(days=30)

            # 确保使用北京时区
            if start_date.tzinfo is None:
                start_date = self.beijing_tz.localize(start_date)
            if end_date.tzinfo is None:
                end_date = self.beijing_tz.localize(end_date)

            # 转换为RFC3339格式
            start_rfc3339 = start_date.isoformat()
            end_rfc3339 = end_date.isoformat()

            # 查询时间范围内的事件
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_rfc3339,
                timeMax=end_rfc3339,
                maxResults=500,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            if not events:
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = end_date.strftime('%Y-%m-%d')
                return {
                    "success": False,
                    "error": f"❌ 在 {start_str} 到 {end_str} 范围内没有找到日历事件"
                }

            # 删除匹配的事件
            deleted_count = 0
            for event in events:
                try:
                    self.service.events().delete(
                        calendarId='primary',
                        eventId=event['id']
                    ).execute()
                    deleted_count += 1
                except HttpError as error:
                    print(f"❌ 删除事件 {event['id']} 失败: {error}")
                    continue

            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            return {
                "success": True,
                "message": f"🗑️ 成功删除 {deleted_count} 个在 {start_str} 到 {end_str} 范围内的日历事件",
                "deleted_count": deleted_count
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"❌ 按时间范围删除日历事件时出错: {str(e)}"
            }


class DeepseekAgent:
    """智能助手Agent - 集成股票分析功能"""

    def __init__(self):
        self.client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
            api_key=os.environ.get("ARK_API_KEY")
        )
        self.model_id = "bot-20250907084333-cbvff"

        # 初始化Google日历管理器
        self.calendar_manager = GoogleCalendarManager()

        # 初始化股票分析代理
        self.stock_agent = StockAnalysisPDFAgent()

        # 更新系统提示词 - 添加股票分析功能
        self.system_prompt = """你是一个智能助手，具备工具调用能力。当用户请求涉及日历、任务、天气、计算、邮件或股票分析时，你需要返回JSON格式的工具调用。

可用工具：
【日历事件功能】
1. 创建日历事件：{"action": "create_event", "parameters": {"summary": "事件标题", "description": "事件描述", "start_time": "开始时间(YYYY-MM-DD HH:MM)", "end_time": "结束时间(YYYY-MM-DD HH:MM)", "reminder_minutes": 30, "priority": "medium"}}
2. 查询日历事件：{"action": "query_events", "parameters": {"days": 30, "max_results": 20}}
3. 更新事件状态：{"action": "update_event_status", "parameters": {"event_id": "事件ID", "status": "completed"}}
4. 删除日历事件：{"action": "delete_event", "parameters": {"event_id": "事件ID"}}
5. 按标题删除事件：{"action": "delete_event_by_summary", "parameters": {"summary": "事件标题关键词", "days": 30}}
6. 按时间范围删除事件：{"action": "delete_events_by_time_range", "parameters": {"start_date": "开始日期(YYYY-MM-DD)", "end_date": "结束日期(YYYY-MM-DD)"}}

【任务管理功能】
7. 创建任务：{"action": "create_task", "parameters": {"title": "任务标题", "notes": "任务描述", "due_date": "截止时间(YYYY-MM-DD HH:MM)", "reminder_minutes": 60, "priority": "medium"}}
8. 查询任务：{"action": "query_tasks", "parameters": {"show_completed": false, "max_results": 20}}
9. 更新任务状态：{"action": "update_task_status", "parameters": {"task_id": "任务ID", "status": "completed"}}
10. 删除任务：{"action": "delete_task", "parameters": {"task_id": "任务ID"}}
11. 按标题删除任务：{"action": "delete_task_by_title", "parameters": {"title_keyword": "任务标题关键词"}}
12. 按时间范围删除任务：{"action": "delete_tasks_by_time_range", "parameters": {"start_date": "开始日期(YYYY-MM-DD)", "end_date": "结束日期(YYYY-MM-DD)", "show_completed": true}}

【股票分析功能】
13. 生成股票分析报告：{"action": "generate_stock_report", "parameters": {"stock_name": "股票名称或代码"}}

【其他功能】
14. 天气查询：{"action": "get_weather", "parameters": {"city": "城市名称"}}
15. 计算器：{"action": "calculator", "parameters": {"expression": "数学表达式"}}
16. 发送邮件：{"action": "send_email", "parameters": {"to": "收件邮箱", "subject": "邮件主题", "body": "邮件内容"}}

重要规则：
1. 当需要调用工具时，必须返回 ```json 和 ``` 包裹的JSON格式
2. 不需要工具时，直接用自然语言回答
3. JSON格式必须严格符合上面的示例
4. 时间格式：YYYY-MM-DD HH:MM (24小时制)，日期格式：YYYY-MM-DD
5. 优先级：low(低), medium(中), high(高)
6. 股票分析功能会返回PDF二进制数据，用于后续上传或其他操作

示例：
用户：生成腾讯控股的股票分析报告
AI：```json
{"action": "generate_stock_report", "parameters": {"stock_name": "腾讯控股"}}
```
用户：删除10月份的所有任务
AI：```json
{"action": "delete_tasks_by_time_range", "parameters": {"start_date": "2025-10-01", "end_date": "2025-10-31"}}
```
用户：清理下周的所有日历事件
AI：```json
{"action": "delete_events_by_time_range", "parameters": {"start_date": "2025-10-06", "end_date": "2025-10-12"}}
```
用户：今天天气怎么样
AI：```json
{"action": "get_weather", "parameters": {"city": "北京"}}
```
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
            allowed_chars = {'+', '-', '*', '/', '(', ')', '.', ' ', '0', '1', '2', '3', '4', '5', '6', '7', '8',
                             '9'}
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

    # ========== 股票分析功能 ==========

    async def generate_stock_report(self, stock_name):
        """
        生成股票分析报告（异步版本）

        参数:
        - stock_name: 股票名称或代码

        返回:
        - PDF二进制数据，如果失败则返回None
        """
        print(f"📈 开始生成股票分析报告: {stock_name}")

        try:
            pdf_binary = await self.stock_agent.generate_stock_report(stock_name)
            if pdf_binary:
                print(f"✅ 股票分析报告生成成功，大小: {len(pdf_binary)} 字节")
                # 返回PDF二进制数据，用于后续上传或其他操作
                return pdf_binary
            else:
                print("❌ 股票分析报告生成失败")
                return None

        except Exception as e:
            print(f"❌ 生成股票分析报告时出错: {e}")
            return None

    # ========== Google日历和任务相关方法 ==========

    def create_task(self, title, notes="", due_date=None, reminder_minutes=60, priority="medium"):
        """创建Google任务"""
        try:
            print(f"📝 开始创建任务: {title}")

            # 解析时间字符串
            due_dt = None
            if due_date:
                print(f"⏰ 解析截止时间: {due_date}")
                due_dt = datetime.strptime(due_date, "%Y-%m-%d %H:%M")
                print(f"✅ 时间解析成功: {due_dt}")

            result = self.calendar_manager.create_task(
                title=title,
                notes=notes,
                due_date=due_dt,
                reminder_minutes=reminder_minutes,
                priority=priority
            )

            if result.get("success"):
                print(f"✅ 任务创建成功: {title}")
                return result.get("message", f"✅ 任务 '{title}' 创建成功")
            else:
                error_msg = result.get("error", "创建任务失败")
                print(f"❌ 任务创建失败: {error_msg}")
                return f"❌ {error_msg}"

        except Exception as e:
            error_msg = f"❌ 创建任务时出错: {str(e)}"
            print(error_msg)
            return error_msg

    def query_tasks(self, show_completed=False, max_results=20):
        """查询任务"""
        try:
            print(f"🔍 查询任务: show_completed={show_completed}")

            result = self.calendar_manager.query_tasks(
                show_completed=show_completed,
                max_results=max_results
            )

            if not result["success"]:
                error_msg = result.get("error", "查询任务失败")
                print(f"❌ 查询失败: {error_msg}")
                return f"❌ {error_msg}"

            if not result["tasks"]:
                print("📭 没有找到任务")
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

            print(f"✅ 找到 {len(result['tasks'])} 个任务")
            return tasks_text

        except Exception as e:
            error_msg = f"❌ 查询任务时出错: {str(e)}"
            print(error_msg)
            return error_msg

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

    def delete_tasks_by_time_range(self, start_date=None, end_date=None, show_completed=True):
        """按时间范围批量删除任务"""
        try:
            print(f"🗑️ 按时间范围删除任务: {start_date} 到 {end_date}")

            result = self.calendar_manager.delete_tasks_by_time_range(
                start_date=start_date,
                end_date=end_date,
                show_completed=show_completed
            )

            if result.get("success"):
                print(f"✅ 时间范围删除任务成功")
                return result.get("message", "✅ 时间范围删除任务完成")
            else:
                error_msg = result.get("error", "时间范围删除任务失败")
                print(f"❌ 时间范围删除任务失败: {error_msg}")
                return f"❌ {error_msg}"

        except Exception as e:
            error_msg = f"❌ 按时间范围删除任务时出错: {str(e)}"
            print(error_msg)
            return error_msg

    def create_event(self, summary, description="", start_time=None, end_time=None,
                     reminder_minutes=30, priority="medium"):
        """创建Google日历事件"""
        try:
            print(f"📅 开始创建日历事件: {summary}")

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

            if result.get("success"):
                print(f"✅ 日历事件创建成功: {summary}")
                return result.get("message", f"✅ 日历事件 '{summary}' 创建成功")
            else:
                error_msg = result.get("error", "创建日历事件失败")
                print(f"❌ 日历事件创建失败: {error_msg}")
                return f"❌ {error_msg}"

        except Exception as e:
            error_msg = f"❌ 创建日历事件时出错: {str(e)}"
            print(error_msg)
            return error_msg

    def query_events(self, days=30, max_results=20):
        """查询日历事件"""
        try:
            result = self.calendar_manager.query_events(days=days, max_results=max_results)

            if not result["success"]:
                return result["error"]

            if not result["events"]:
                return result["message"]

            return result["message"]

        except Exception as e:
            return f"❌ 查询日历事件时出错: {str(e)}"

    def update_event_status(self, event_id, status="completed"):
        """更新事件状态"""
        try:
            result = self.calendar_manager.update_event_status(event_id, status)
            return result.get("message", result.get("error", "状态更新完成"))
        except Exception as e:
            return f"❌ 更新事件状态时出错: {str(e)}"

    def delete_event(self, event_id):
        """删除日历事件"""
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

    def delete_events_by_time_range(self, start_date=None, end_date=None):
        """按时间范围批量删除日历事件"""
        try:
            print(f"🗑️ 按时间范围删除日历事件: {start_date} 到 {end_date}")

            result = self.calendar_manager.delete_events_by_time_range(
                start_date=start_date,
                end_date=end_date
            )

            if result.get("success"):
                print(f"✅ 时间范围删除日历事件成功")
                return result.get("message", "✅ 时间范围删除日历事件完成")
            else:
                error_msg = result.get("error", "时间范围删除日历事件失败")
                print(f"❌ 时间范围删除日历事件失败: {error_msg}")
                return f"❌ {error_msg}"

        except Exception as e:
            error_msg = f"❌ 按时间范围删除日历事件时出错: {str(e)}"
            print(error_msg)
            return error_msg

    def extract_tool_call(self, llm_response):
        """从LLM响应中提取工具调用指令"""
        print(f"🔍 解析LLM响应: {llm_response}")

        if "```json" in llm_response and "```" in llm_response:
            try:
                start = llm_response.find("```json") + 7
                end = llm_response.find("```", start)
                json_str = llm_response[start:end].strip()
                print(f"📦 提取到JSON代码块: {json_str}")

                tool_data = json.loads(json_str)
                if isinstance(tool_data, dict) and "action" in tool_data and "parameters" in tool_data:
                    print(f"✅ 成功解析工具调用: {tool_data['action']}")
                    return tool_data
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                return None
            except Exception as e:
                print(f"❌ 提取工具调用失败: {e}")
                return None

        print("❌ 未找到有效的工具调用")
        return None

    async def call_tool(self, action, parameters):
        """统一工具调用入口 - 异步版本"""
        print(f"🛠️ 调用工具: {action}")
        print(f"📋 工具参数: {parameters}")

        try:
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
            elif action == "delete_tasks_by_time_range":
                return self.delete_tasks_by_time_range(
                    start_date=parameters.get("start_date"),
                    end_date=parameters.get("end_date"),
                    show_completed=parameters.get("show_completed", True)
                )
            elif action == "create_event":
                return self.create_event(
                    summary=parameters.get("summary", ""),
                    description=parameters.get("description", ""),
                    start_time=parameters.get("start_time"),
                    end_time=parameters.get("end_time"),
                    reminder_minutes=parameters.get("reminder_minutes", 30),
                    priority=parameters.get("priority", "medium")
                )
            elif action == "query_events":
                return self.query_events(
                    days=parameters.get("days", 30),
                    max_results=parameters.get("max_results", 20)
                )
            elif action == "update_event_status":
                return self.update_event_status(
                    event_id=parameters.get("event_id", ""),
                    status=parameters.get("status", "completed")
                )
            elif action == "delete_event":
                return self.delete_event(
                    event_id=parameters.get("event_id", "")
                )
            elif action == "delete_event_by_summary":
                return self.delete_event_by_summary(
                    summary=parameters.get("summary", ""),
                    days=parameters.get("days", 30)
                )
            elif action == "delete_events_by_time_range":
                return self.delete_events_by_time_range(
                    start_date=parameters.get("start_date"),
                    end_date=parameters.get("end_date")
                )
            elif action == "generate_stock_report":
                # 股票分析工具返回PDF二进制数据
                pdf_binary = await self.generate_stock_report(parameters.get("stock_name", ""))
                if pdf_binary:
                    return {
                        "success": True,
                        "pdf_binary": pdf_binary,
                        "message": f"✅ 股票分析报告生成成功，PDF大小: {len(pdf_binary)} 字节",
                        "stock_name": parameters.get("stock_name", "")
                    }
                else:
                    return {
                        "success": False,
                        "error": "❌ 股票分析报告生成失败"
                    }
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
            else:
                result = f"未知工具：{action}"

            print(f"✅ 工具执行结果: {result}")
            return result

        except Exception as e:
            error_msg = f"❌ 执行工具 {action} 时出错: {str(e)}"
            print(error_msg)
            return error_msg

    async def process_request(self, user_input):
        """处理用户请求（异步版本）"""
        print(f"👤 用户输入: {user_input}")

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
            print(f"🤖 LLM原始响应: {llm_response}")

            # 检查工具调用
            tool_data = self.extract_tool_call(llm_response)
            if tool_data:
                print(f"🔧 检测到工具调用: {tool_data['action']}")
                tool_result = await self.call_tool(tool_data["action"], tool_data["parameters"])

                # 特殊处理股票分析工具，返回PDF二进制数据
                if tool_data["action"] == "generate_stock_report" and isinstance(tool_result,
                                                                                 dict) and tool_result.get(
                    "success"):
                    return {
                        "type": "stock_pdf",
                        "success": True,
                        "pdf_binary": tool_result.get("pdf_binary"),
                        "message": tool_result.get("message"),
                        "stock_name": tool_result.get("stock_name")
                    }
                else:
                    return {
                        "type": "text",
                        "content": str(tool_result),  # 确保返回字符串
                        "success": True
                    }
            else:
                print("💬 无工具调用，直接返回LLM响应")
                return {
                    "type": "text",
                    "content": llm_response,
                    "success": True
                }

        except Exception as e:
            error_msg = f"处理请求时出错：{str(e)}"
            print(f"❌ {error_msg}")
            return {
                "type": "text",
                "content": error_msg,
                "success": False
            }


async def smart_assistant(user_input):
    """智能助手主函数 - 异步版本"""
    agent = DeepseekAgent()
    result = await agent.process_request(user_input)
    return result


async def test_playwright_async():
    """异步测试Playwright功能"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto('https://example.com')
            title = await page.title()
            await browser.close()

            return f"页面标题: {title}"
    except Exception as e:
        return f"Playwright异步测试失败: {str(e)}"


# 测试函数
async def test_all_features():
    """测试所有功能"""
    test_cases = [
        # 日历事件测试
        # "创建日历事件：明天下午2点团队会议，讨论项目进度，提前15分钟提醒我",
        # "查看我未来一周的日程安排",
        #
        # # 任务管理测试
        # "创建任务：周五前完成产品设计文档，这是一个高优先级的任务",
        # "查看我所有的待办任务",

        # 股票分析测试
        "生成腾讯控股的股票分析报告"
        # "分析贵州茅台的股票情况",

        # # 时间范围删除测试
        # "删除10月份的所有任务",
        # "清理下周的所有日历事件",
    ]

    print("🧪 测试所有功能")
    print("=" * 50)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. 测试: {test_case}")
        try:
            result = await smart_assistant(test_case)
            if result["type"] == "stock_pdf":
                print(f"✅ 股票分析报告生成成功")
                print(f"   股票名称: {result.get('stock_name')}")
                print(f"   PDF大小: {len(result.get('pdf_binary', b''))} 字节")
                print(f"   消息: {result.get('message')}")
                # 这里可以添加上传PDF到其他服务的代码
            else:
                print(f"结果: {result.get('content', '')}")
        except Exception as e:
            print(f"❌ 测试失败: {e}")
        print("-" * 30)


if __name__ == '__main__':
    # 测试所有功能
    asyncio.run(test_all_features())
