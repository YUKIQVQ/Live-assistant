import customtkinter as ctk
import json
import os
from tkinter import messagebox

# --- 尝试导入主程序模块，如果不存在则定义一个空类用于测试 ---
try:
    from main import LiveDashboard
except ImportError:
    class LiveDashboard(ctk.CTkToplevel):
        def __init__(self, config_data):
            super().__init__()
            self.title("直播间主界面 (测试)")
            self.geometry("800x600")
            ctk.CTkLabel(self, text="AI 直播间已启动！", font=("Microsoft YaHei", 24)).pack(pady=20)
            ctk.CTkLabel(self, text=f"欢迎, {config_data.get('app_id', '用户')}").pack()

# --- 配置外观 ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ConfigApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("直播间 AI 助手 - 凭证配置")
        self.geometry("500x600")  # 增加高度以容纳新控件
        self.resizable(False, False)

        # 布局
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)

        ctk.CTkLabel(self, text="API 密钥配置中心", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0,
                                                                                                   columnspan=2,
                                                                                                   pady=20)

        # --- 新增：模型选择下拉框 ---
        ctk.CTkLabel(self, text="选择模型:").grid(row=1, column=0, padx=20, pady=5, sticky="w")
        self.model_var = ctk.StringVar(value="qwen")
        self.model_dropdown = ctk.CTkComboBox(self, values=["qwen", "deepseek", "gpt"], variable=self.model_var)
        self.model_dropdown.grid(row=1, column=1, padx=20, pady=5, sticky="ew")

        # --- 字段定义 ---
        self.entries = {}
        # 注意：这里跳过了第1行，因为第1行给了下拉框
        fields = [
            ("Qwen API Key:", "qwen_api_key"),
            ("DeepSeek API Key:", "deepseek_api_key"),
            ("OpenAI API Key:", "openai_api_key"),
            ("Access Key ID:", "access_key_id"),
            ("Access Key Secret:", "access_key_secret"),
            ("APP ID:", "app_id"),
            ("主播身份码:", "room_owner_auth_code")
        ]

        for i, (label_text, key) in enumerate(fields):
            row = i + 2  # 索引偏移2，避开标题和下拉框
            ctk.CTkLabel(self, text=label_text).grid(row=row, column=0, padx=20, pady=5, sticky="w")

            # 如果包含 Key 或 码，则隐藏内容
            show_char = "*" if "Key" in label_text or "code" in label_text or "码" in label_text else None
            entry = ctk.CTkEntry(self, placeholder_text=f"请输入 {label_text}", show=show_char)
            entry.grid(row=row, column=1, padx=20, pady=5, sticky="ew")
            self.entries[key] = entry

        # --- 按钮区域 ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=len(fields) + 2, column=0, columnspan=2, pady=30)

        ctk.CTkButton(btn_frame, text="📂 读取配置", command=self.load_config).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="🚀 运行程序", command=self.run_program, fg_color="#8C48C4",
                      hover_color="#6B3A96").pack(side="right", padx=10)
        ctk.CTkButton(btn_frame, text="💾 保存", command=self.save_config).pack(side="right", padx=10)

        self.load_config()

    def save_config(self):
        config_data = {}

        # 1. 获取模型选择
        config_data["selected_model"] = self.model_var.get()

        # 2. 获取所有输入框的数据
        for key, entry in self.entries.items():
            config_data[key] = entry.get().strip()

        # 3. 校验 (根据选择的模型校验对应的 Key)
        model = config_data["selected_model"]
        key_map = {
            "qwen": "qwen_api_key",
            "deepseek": "deepseek_api_key",
            "gpt": "openai_api_key"
        }

        required_key = key_map.get(model)
        if not config_data.get(required_key):
            messagebox.showwarning("警告", f"当前选择了 {model}，请填写对应的 API Key！")
            return False

        # 4. 保存逻辑
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            messagebox.showinfo("成功", "配置已保存！")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"保存失败:\n{e}")
            return False

    def load_config(self):
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 加载模型选择
                if "selected_model" in data:
                    self.model_var.set(data["selected_model"])

                # 加载其他字段
                for key, entry in self.entries.items():
                    if key in data:
                        entry.insert(0, data[key])
            except Exception as e:
                print(f"读取配置失败: {e}")

    def run_program(self):
        if self.save_config():
            self.withdraw()
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                self.main_window = LiveDashboard(config_data)
                self.main_window.protocol("WM_DELETE_WINDOW", self.on_main_close)
                self.mainloop()
            except Exception as e:
                messagebox.showerror("错误", f"启动主程序失败:\n{e}")
                self.deiconify()

    def on_main_close(self):
        self.main_window.destroy()
        self.quit()


if __name__ == "__main__":
    app = ConfigApp()
    app.mainloop()