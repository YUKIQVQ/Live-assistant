import customtkinter as ctk
import threading
import asyncio
import blivedm
import time
import json
import os

# --- 新增：根据模型导入相应的 SDK ---
try:
    import dashscope  # Qwen
    from dashscope import Generation as QwenGeneration
except ImportError:
    dashscope = None

try:
    import openai  # GPT
except ImportError:
    openai = None

try:
    import openai as deepseek_client  # DeepSeek 通常兼容 OpenAI 接口
    deepseek = None
except ImportError:
    deepseek_client = None


# ================== 配置区 ==================
class LiveDashboard(ctk.CTkToplevel):
    def __init__(self, config_data, master=None):
        super().__init__(master)
        self.config_data = config_data
        self.loop = None
        self.client = None
        # --- 初始化配置 ---
        self.setup_credentials()
        # --- UI 界面构建 ---
        self.setup_ui()

    def setup_credentials(self):
        """从传入的 config_data 中提取凭证"""
        # 1. 读取用户选择的模型
        self.selected_model = self.config_data.get('selected_model', 'qwen')
        # 2. 读取各个模型的 Key (隔离存储)
        self.qwen_api_key = self.config_data.get('qwen_api_key', '')
        self.deepseek_api_key = self.config_data.get('deepseek_api_key', '')
        self.openai_api_key = self.config_data.get('openai_api_key', '')
        # 3. 读取 Bilibili 直播间配置
        self.ACCESS_KEY_ID = self.config_data.get('access_key_id', '')
        self.ACCESS_KEY_SECRET = self.config_data.get('access_key_secret', '')
        self.APP_ID = self.config_data.get('app_id', '')
        self.ROOM_OWNER_AUTH_CODE = self.config_data.get('room_owner_auth_code', '')

    def setup_ui(self):
        """构建直播间 UI"""
        self.title("AI 实时互动直播间")
        self.geometry("1920x1080")

        # --- 左侧：直播画面/弹幕区 ---
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(self.left_frame, text="📺 直播区域", font=("Microsoft YaHei", 16, "bold")).pack(pady=5)
        # 弹幕显示框
        self.danmu_textbox = ctk.CTkTextbox(self.left_frame, state="disabled", font=("Microsoft YaHei", 12))
        self.danmu_textbox.pack(fill="both", expand=True, padx=10, pady=10)

        # --- 右侧：AI 控制台 ---
        self.right_frame = ctk.CTkFrame(self, width=300)
        self.right_frame.pack(side="right", fill="y", padx=(0, 10), pady=10)
        self.right_frame.pack_propagate(False)
        ctk.CTkLabel(self.right_frame, text="🤖 状态", font=("Microsoft YaHei", 16, "bold")).pack(pady=10)
        # 状态指示灯
        self.status_label = ctk.CTkLabel(self.right_frame, text="🔴 未连接", text_color="red")
        self.status_label.pack(pady=5)
        # 日志显示
        self.log_textbox = ctk.CTkTextbox(self.right_frame, state="disabled", height=200)
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        # 控制按钮
        self.btn_start = ctk.CTkButton(self.right_frame, text="▶️ 开始监听", command=self.start_listening)
        self.btn_start.pack(pady=10, padx=20, fill="x")
        self.btn_stop = ctk.CTkButton(self.right_frame, text="⏹️ 停止监听", command=self.stop_listening, state="disabled")
        self.btn_stop.pack(pady=5, padx=20, fill="x")

    def add_danmu(self, text):
        """线程安全地添加弹幕"""
        self.danmu_textbox.configure(state="normal")
        self.danmu_textbox.insert("end", text + "\n")
        self.danmu_textbox.see("end")
        self.danmu_textbox.configure(state="disabled")

    def add_log(self, text):
        """线程安全地添加日志"""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def start_listening(self):
        """点击开始按钮"""
        if not self.ACCESS_KEY_ID or not self.APP_ID:
            self.add_log("错误：Access Key 或 App ID 为空！")
            return

        # 检查模型 Key
        if self.selected_model == "qwen" and not self.qwen_api_key:
            self.add_log("错误：选择了 Qwen 模型，但 API Key 为空！")
            return
        elif self.selected_model == "deepseek" and not self.deepseek_api_key:
            self.add_log("错误：选择了 DeepSeek 模型，但 API Key 为空！")
            return
        elif self.selected_model == "gpt" and not self.openai_api_key:
            self.add_log("错误：选择了 GPT 模型，但 API Key 为空！")
            return

        self.add_log(f"🚀 正在启动弹幕客户端... (使用模型: {self.selected_model})")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_label.configure(text="🔄 连接中...", text_color="yellow")

        # 在新线程中启动 asyncio 事件循环
        thread = threading.Thread(target=self.run_asyncio_loop, daemon=True)
        thread.start()

    def stop_listening(self):
        """点击停止按钮"""
        self.add_log("⏹️ 用户手动停止监听")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_label.configure(text="🛑 已停止", text_color="orange")
        # 尝试关闭客户端连接
        if self.client and not self.client.is_closed():
            # 注意：blivedm 的关闭逻辑可能需要根据实际情况调整
            pass

    def run_asyncio_loop(self):
        """在子线程中运行的 asyncio 事件循环"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            # 创建客户端
            self.client = blivedm.OpenLiveClient(
                access_key_id=self.ACCESS_KEY_ID,
                access_key_secret=self.ACCESS_KEY_SECRET,
                app_id=self.APP_ID,
                room_owner_auth_code=self.ROOM_OWNER_AUTH_CODE
            )
            handler = DanmuHandler(self)
            self.client.set_handler(handler)
            # 运行客户端
            self.loop.run_until_complete(self.start_client())
        except Exception as e:
            self.add_log(f"❌ 启动失败: {e}")
        finally:
            self.loop.close()

    async def start_client(self):
        """异步启动客户端"""
        self.client.start()
        self.add_log("✅ 弹幕监听已启动")
        self.status_label.configure(text="✅ 监听中", text_color="green")
        try:
            while self.winfo_exists() and self.btn_stop.cget("state") == "normal":
                await asyncio.sleep(1)
        finally:
            await self.client.stop_and_close()
            self.add_log("👋 弹幕客户端已关闭")


# --- 弹幕处理器 ---
class DanmuHandler(blivedm.BaseHandler):
    def __init__(self, ui_instance):
        self.ui = ui_instance

    def _on_open_live_danmaku(self, client, message):
        # 1. 更新 UI 日志
        self.ui.add_log(f"👤 [{message.uname}]: {message.msg}")
        # 2. 调用 AI 回复
        # 注入时间地点信息
        location_time_info = f"当前时间：{time.strftime('%Y-%m-%d %H:%M:%S')}，地点：上海市"
        reply = self.call_ai_sync(message.msg, message.uname, location_time_info)
        if reply:
            self.ui.add_log(f"🤖 [{self.ui.selected_model}]: {reply}")

    def call_ai_sync(self, user_input, username, location_time_info):
        """同步调用 AI 接口 (支持多模型)"""
        model = self.ui.selected_model
        # --- 组合 Prompt ---
        system_prompt = f"""你是一个直播间的 AI 助手。 
        【当前环境】{location_time_info} 
        【观众 {username} 提问】{user_input} 
        【请回复】"""

        try:
            if model == "qwen":
                # --- 调用 Qwen ---
                if not dashscope:
                    return "错误：缺少 dashscope 库"
                dashscope.api_key = self.ui.qwen_api_key
                response = QwenGeneration.call(
                    model='qwen-turbo',
                    prompt=system_prompt,
                    max_tokens=150
                )
                if response.status_code == 200:
                    return response.output.text.strip()
                else:
                    return f"Qwen错误: {response.message}"

            elif model == "deepseek":
                # --- 调用 DeepSeek (兼容 OpenAI 接口) ---
                if not deepseek_client:
                    return "错误：缺少 openai 库"
                client = deepseek_client.OpenAI(
                    api_key=self.ui.deepseek_api_key,
                    base_url="https://api.deepseek.com/v1" # 请确认这是正确的地址
                )
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": system_prompt}],
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()

            elif model == "gpt":
                # --- 调用 GPT ---
                if not openai:
                    return "错误：缺少 openai 库"
                client = openai.OpenAI(api_key=self.ui.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": system_prompt}],
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()

            else:
                return "未知模型"

        except Exception as e:
            self.ui.add_log(f"❌ AI调用错误 ({model}): {e}")
            return f"AI 回复失败: {str(e)}"


# --- 如果直接运行 main.py (用于测试) ---
if __name__ == "__main__":
    if not os.path.exists("config.json"):
        print("请先运行 settings_ui.py 进行配置")
    else:
        # 测试用配置
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                test_config = json.load(f)
        except Exception as e:
            print(f"读取配置失败: {e}")
            test_config = {}

        root = ctk.CTk()
        root.withdraw()  # 隐藏主窗口
        app = LiveDashboard(test_config, master=root)
        app.protocol("WM_DELETE_WINDOW", root.destroy)
        root.mainloop()