import http.server
import json
import threading
import urllib.parse
import tkinter as tk       
from tkinter import ttk, scrolledtext, filedialog, simpledialog
import threading, time, os, re, random, webbrowser, json, subprocess, ctypes
import pyautogui, pyperclip 
import sys
import win32gui, win32con, win32api, win32clipboard, win32ui
import cv2
import numpy as np
from mobile_console import MobileConsole
import queue
from PIL import Image
from nexus_bridge import NexusBridge

class NexusTool:
    def __init__(self):       
        import subprocess, os; [os.system(f"taskkill /f /pid {p.split()[-1]}") for p in os.popen("netstat -ano | findstr :5000 | findstr LISTENING").readlines()]
        self.root = tk.Tk()
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        pyautogui.MINIMUM_DURATION = 0
        self.root.title("Nexus 桌面助手 - AI协作与自动化工具")
        self.root.geometry("950x750")
        self.stop_event = threading.Event()
        self.window_status = {}
        self.speech_pool = []
        # 扫描话题中的机器人指令
        #if hasattr(self, 'bridge'):
            #self.root.after(0, lambda: self.bridge.process_ai_response(topic))
        self.speech_authors = []

        self.window_configs = {}
        # 补回缺失的初始化逻辑：为每个窗口配置设置默认值
        for name, cfg in self.window_configs.items():
            if cfg.get("type") != "file_bridge":
                cfg.setdefault("rx", cfg.get("x", 0))
                cfg.setdefault("ry", cfg.get("y", 0))
                cfg.setdefault("rw", 800)
                cfg.setdefault("rh", 500)
                cfg.setdefault("copy_rx", 0)
                cfg.setdefault("copy_ry", 0)

        for name in self.window_configs:
            self.window_status[name] = "idle"
      
        self.END_MARKER = "本轮回复结束"
        self.SEND_TO_PATTERN = re.compile(r"\[@send_to:([^\]]+)\]")
        self.WINDOW_NAMES = ["DeepSeek", "千问", "扣子", "Qoder CN", "智谱", "deepseek", "qianwen", "qianwen2", "zhipu", "coze"]
        self.ROUTE_NAMES = ["DeepSeek", "千问", "扣子", "Qoder CN", "智谱", "deepseek", "qianwen", "qianwen2", "zhipu", "coze"]
        self.search_engines = {"Bing": "https://www.bing.com/search?q=", "Google": "https://www.google.com/search?q=", "百度": "https://www.baidu.com/s?wd="}

        self.CONFIG_FILE = r"D:\智联枢纽\nexus_config.json"
        self._load_config()
        # 初始化机器人桥接器
        self.bridge = NexusBridge(result_callback=self._worker_result_handler) 
        # 初始化移动控制台
        try:
            self._mobile_console = MobileConsole(
                state_provider=self._get_system_state,
                command_executor=self._execute_remote_command,
                log_stream=self._mc_log_queue,
                port=self._get_config("mobile_port", 5000),
            )
            if getattr(self._mobile_console, '_available', True):
                threading.Thread(target=self._mobile_console.start, daemon=True).start()
            else:
                self.log("移动端依赖缺失，服务未启动")
        except Exception as e:
            self.log(f"移动端初始化失败: {e}")
        try:
            threading.Thread(target=self._mobile_console.start, daemon=True).start()
        except Exception as e:
            self.log(f"移动端启动失败: {e}，主程序继续运行")
        self._build_ui()
        # 启动独立的机器人对话窗口（rw.py）
        def launch_robot():
            import sys, os, subprocess
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
                robot_exe = os.path.join(exe_dir, "NexusRobot.exe")
            else:
                base = os.path.dirname(os.path.abspath(__file__))
                robot_exe = os.path.join(base, "NexusRobot.exe")
            if os.path.exists(robot_exe):
                subprocess.Popen([robot_exe], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        
        threading.Thread(target=launch_robot, daemon=True).start()
        # 轻量桌面自动化 API（端口 5000）
        class DesktopHandler(http.server.BaseHTTPRequestHandler):
            _app = None

            def do_POST(self):
                try:
                    if self.path == '/api/desktop':
                        length = int(self.headers.get('Content-Length', 0))
                        raw = self.rfile.read(length).decode('utf-8')
                        data = json.loads(raw)

                        command = data.get("command", "")
                        if command:
                            app = DesktopHandler._app
                            import nexus_worker; result = nexus_worker.execute(command, extra_globals={"app": app})
                            
                            
                                
                            
                                
                            
                                
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps(result).encode('utf-8'))
                        else:
                            self.send_response(400)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({"success": False, "error": "缺少command字段"}).encode('utf-8'))
                    else:
                        self.send_response(404)
                        self.end_headers()
                except Exception as e:
                    import traceback
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    err_msg = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
                    self.wfile.write(json.dumps(err_msg).encode('utf-8'))

            def log_message(self, format, *args):
                pass  # 禁用 HTTP 日志

        DesktopHandler._app = self
        self._desktop_server = http.server.HTTPServer(('127.0.0.1', 5000), DesktopHandler)
        threading.Thread(target=self._desktop_server.serve_forever, daemon=True).start()
        self.log("桌面助手远程指令通道已就绪（端口5000）")
    def log(self, msg):
        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        else:
            print(msg)
        # 推送到移动控制台
        if hasattr(self, '_mc_log_queue'):
            self._mc_log_queue.put(msg)
    def clear_log(self):
        """清空日志文本框"""
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "日志已清空\n")
        self.log_text.see(tk.END) 
    def clear_chat(self):
        """清空对话文本框"""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)
        self.chat_text.config(state=tk.DISABLED)   

    def _load_config(self):
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                json_windows = config.get("windows", {})
                for name in list(self.window_configs.keys()):
                    if name not in json_windows and name not in ["deepseek","qianwen","zhipu","coze"]:
                        del self.window_configs[name]
                        if name in self.window_status:
                            del self.window_status[name]
                for name, wcfg in json_windows.items():
                    if name not in self.window_configs:
                        self.window_configs[name] = wcfg
                        self.window_status[name] = "idle"
                for name, coord in config.get("coords", {}).items():
                    if name in self.window_configs:
                        self.window_configs[name]["x"] = coord.get("x", self.window_configs[name].get("x", 0))
                        self.window_configs[name]["y"] = coord.get("y", self.window_configs[name].get("y", 0))
                        self.window_configs[name]["rx"] = coord.get("rx", self.window_configs[name]["x"])
                        self.window_configs[name]["ry"] = coord.get("ry", self.window_configs[name]["y"])
                        self.window_configs[name]["rw"] = coord.get("rw", self.window_configs[name].get("rw", 800))
                        self.window_configs[name]["rh"] = coord.get("rh", self.window_configs[name].get("rh", 500))
                        self.window_configs[name]["copy_rx"] = coord.get("copy_rx", self.window_configs[name]["rx"])
                        self.window_configs[name]["copy_ry"] = coord.get("copy_ry", self.window_configs[name]["ry"])
                settings = config.setdefault("settings", {})
                settings.setdefault("zhipu_threshold", 0.48)
                settings.setdefault("qianwen_threshold", 0.55)
                settings.setdefault("coze_threshold", 0.50)
                settings.setdefault("scroll_count", 10)
                settings.setdefault("scroll_amount", 500)
                settings.setdefault("click_max", 2)
                settings.setdefault("screenshot_wait", 2)
                settings.setdefault("fullselect_stable_count", 2)
                settings.setdefault("screenshot_stable_count", 2)
                settings.setdefault("fullselect_interval", 3)
                settings.setdefault("screenshot_interval", 3)
                settings.setdefault("stable_wait", 3)
                settings.setdefault("idle_timeout", 10)
                self.log("已加载持久化配置")
            try:
                import yaml
                with open("D:/智联枢纽/workflow.yaml", "r", encoding="utf-8") as wf:
                    self._workflow_config = yaml.safe_load(wf) or {}
            except:
                self._workflow_config = {}
        except Exception as e:
            self.log(f"[配置加载失败] {repr(e)}，使用默认空配置继续运行")
            if not self.window_configs:
                self.window_configs = {
                    "千问": {"keyword": "千问", "x": 0, "y": 0, "grab_type": "ocr"},
                    "DeepSeek": {"keyword": "DeepSeek", "x": 0, "y": 0, "grab_type": "select"},
                }
                for n in self.window_configs:
                    self.window_status[n] = "idle"
    def _save_config(self):
        coords = {}
        windows = {}
        for name, cfg in self.window_configs.items():
            coords[name] = {"x": cfg.get("x", 0), "y": cfg.get("y", 0),
                            "rx": cfg.get("rx", cfg.get("x", 0)), "ry": cfg.get("ry", cfg.get("y", 0)),
                            "copy_rx": cfg.get("copy_rx", cfg.get("rx", 0)), "copy_ry": cfg.get("copy_ry", cfg.get("ry", 0)),
                            "rw": cfg.get("rw", 800), "rh": cfg.get("rh", 500)}
            windows[name] = {"keyword": cfg.get("keyword", ""), "type": cfg.get("type", ""),
                            "x": cfg.get("x", 0), "y": cfg.get("y", 0)}
        try:
            # 读取原有配置，保留 settings 中其他值
            old_config = {}
            if os.path.exists(self.CONFIG_FILE):
                try:
                    with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                        old_config = json.load(f)
                except:
                    pass
            old_settings = old_config.get("settings", {})
            # 更新勾选状态
            if hasattr(self, 'schedule_vars'):
                old_settings["schedule_checks"] = {name: var.get() for name, var in self.schedule_vars.items()}
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"coords": coords, "windows": windows, "settings": old_settings}, f, indent=2)
        except Exception as e:
            print(f"[配置错误] 加载失败: {repr(e)}")
            import traceback
            print(traceback.format_exc())

    # ==================== UI构建 ====================
    def _build_ui(self):
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=tk.BOTH, expand=True)
        log_frame = ttk.LabelFrame(main, text="运行日志", padding="5")
        log_frame.pack(fill=tk.X, pady=(0,5))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True)

        chat_tab = ttk.Frame(notebook)
        notebook.add(chat_tab, text="💬 对话")
        self._build_chat_tab(chat_tab)

        calib_tab = ttk.Frame(notebook)
        notebook.add(calib_tab, text="🎯 定位校准")
        self._build_calibration_tab(calib_tab)

        schedule_tab = ttk.Frame(notebook)
        notebook.add(schedule_tab, text="🔄 智能调度")
        self._build_schedule_tab(schedule_tab)

        task_tab = ttk.Frame(notebook)
        notebook.add(task_tab, text="⚡ 自动任务")
        self._build_task_tab(task_tab)

        app_tab = ttk.Frame(notebook)
        notebook.add(app_tab, text="📱 应用启动")
        self._build_app_tab(app_tab)

        search_tab = ttk.Frame(notebook)
        notebook.add(search_tab, text="🔍 搜索抓取")
        self._build_search_tab(search_tab)

        help_tab = ttk.Frame(notebook)
        notebook.add(help_tab, text="❓ 帮助与反馈")
        self._build_help_tab(help_tab)

    def _build_chat_tab(self, parent):
        frame = ttk.Frame(parent, padding="5")
        frame.pack(fill=tk.BOTH, expand=True)
        sel_frame = ttk.Frame(frame)
        sel_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sel_frame, text="选择对话对象:").pack(side=tk.LEFT)
        self.target_var = tk.StringVar(value="deepseek")
        for name in self.window_configs:
            ttk.Radiobutton(sel_frame, text=name, variable=self.target_var, value=name).pack(side=tk.LEFT, padx=5)
        chat_frame = ttk.Frame(frame)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.chat_text = scrolledtext.ScrolledText(chat_frame, height=18, state=tk.NORMAL)
        self.chat_text.pack(fill=tk.BOTH, expand=True)
        self.chat_text.bind('<Button-3>', self._right_click)
        input_frame = ttk.Frame(frame)
        input_frame.pack(fill=tk.X, pady=5)
        self.msg_var = tk.StringVar()
        self.entry = tk.Text(input_frame, height=4, width=60)
        self.entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.entry.bind("<Return>", lambda e: self._send_message())
        self.entry.bind('<Button-3>', self._right_click)
        self.entry.bind("<Control-v>", lambda e: self._paste_from_clipboard(e.widget))
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        self.send_btn = ttk.Button(btn_frame, text="📤 发送", command=self._send_message)
        self.send_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="⏹️ 停止", command=self._stop_task)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.clear_btn = ttk.Button(btn_frame, text="🗑️ 清空日志", command=self.clear_log)
        self.clear_chat_btn = ttk.Button(btn_frame, text="🧹 清空对话", command=self.clear_chat)
        self.clear_chat_btn.pack(side=tk.LEFT, padx=5)
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        self.copy_btn = ttk.Button(btn_frame, text="📋 复制最新回复", command=self._copy_latest_reply)
        self.copy_btn.pack(side=tk.LEFT, padx=5)
        self.restart_btn = ttk.Button(btn_frame, text="🔄 重启应用", command=self._restart_app)
        self.restart_btn.pack(side=tk.LEFT, padx=5)

    def _build_calibration_tab(self, parent):
        self.calib_frame = ttk.Frame(parent, padding="10")
        self.calib_frame.pack(fill=tk.BOTH, expand=True)
        self._build_calib_rows()

    def _build_calib_rows(self):
        for widget in self.calib_frame.winfo_children():
            widget.destroy()
        ttk.Label(self.calib_frame, text="点击[校准]后，将鼠标放在对应AI输入框上等待5秒。").pack(anchor=tk.W)
        self.coord_vars = {}
        self.read_coord_vars = {}
        self.copy_coord_vars = {}
        for name, cfg in self.window_configs.items():
            row = ttk.Frame(self.calib_frame)
            row.pack(fill=tk.X, pady=5)
            if cfg.get("type") == "file_bridge":
                label = "Qoder CN（我）" if name == "qianwen2" else name
                ttk.Label(row, text=f"{label}:", width=12).pack(side=tk.LEFT)
                var = tk.StringVar(value=f"{cfg.get('x', 0)}, {cfg.get('y', 0)}")
                var.trace("w", lambda *args, n=name, v=var: self._update_coords(n, v))
                self.coord_vars[name] = var
                ttk.Entry(row, textvariable=var, width=13).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="🎯 校准", command=lambda n=name: self._calibrate(n)).pack(side=tk.LEFT, padx=2)
                ttk.Label(row, text=f"任务: {cfg.get('task_file','')}", foreground="gray").pack(side=tk.LEFT, padx=5)
                ttk.Label(row, text=f"回复: {cfg.get('reply_file','')}", foreground="gray").pack(side=tk.LEFT, padx=5)
                ttk.Button(row, text="🧪 测试桥接", command=lambda n=name: self._test_file_bridge(n)).pack(side=tk.LEFT, padx=5)
            else:
                ttk.Label(row, text=f"{name}:", width=12).pack(side=tk.LEFT)
                var = tk.StringVar(value=f"{cfg['x']}, {cfg['y']}")
                var.trace("w", lambda *args, n=name, v=var: self._update_coords(n, v))
                self.coord_vars[name] = var
                ttk.Entry(row, textvariable=var, width=13).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="🎯 校准", command=lambda n=name: self._calibrate(n)).pack(side=tk.LEFT, padx=2)
                rvar = tk.StringVar(value=f"{cfg.get('rx', cfg['x'])}, {cfg.get('ry', cfg['y'])}")
                self.read_coord_vars[name] = rvar
                ttk.Entry(row, textvariable=rvar, width=13).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="📖 校准读取区", command=lambda n=name: self._calibrate_read(n)).pack(side=tk.LEFT, padx=2)
                cvar = tk.StringVar(value=f"{cfg.get('copy_rx', cfg.get('rx', cfg['x']))}, {cfg.get('copy_ry', cfg.get('ry', cfg['y']))}")
                self.copy_coord_vars[name] = cvar
                ttk.Entry(row, textvariable=cvar, width=13).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="📋 校准复制键", command=lambda n=name: self._calibrate_copy_btn(n)).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="🔍 测试捕获", command=lambda n=name: self._test_capture(n)).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="🔎 找复制键", command=lambda n=name: self._test_copy_btn(n, click=False)).pack(side=tk.LEFT, padx=2)
                ttk.Button(row, text="🖱️ 点复制键", command=lambda n=name: self._test_copy_btn(n, click=True)).pack(side=tk.LEFT, padx=2)
                monitor_row = ttk.Frame(row)
                monitor_row.pack(side=tk.LEFT, padx=(10,0))
                ttk.Label(monitor_row, text="监控方式:").pack(side=tk.LEFT)
                grab_var = tk.StringVar(value=cfg.get("grab_type", "ocr"))
                grab_combo = ttk.Combobox(monitor_row, textvariable=grab_var, values=["select", "ocr"], state="readonly", width=8)
                grab_combo.pack(side=tk.LEFT, padx=2)
                grab_var.trace("w", lambda *a, n=name, v=grab_var: self._change_grab_type(n, v))
        settings_frame = ttk.LabelFrame(self.calib_frame, text="监控参数设置", padding="5")
        settings_frame.pack(fill=tk.X, pady=10)
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="稳定等待(秒):").pack(side=tk.LEFT)
        self.stable_wait_var = tk.IntVar(value=self._get_config("stable_wait", 3))
        sw_label = ttk.Label(row1, text="?", foreground="blue", cursor="hand2")
        sw_label.pack(side=tk.LEFT)
        self._add_tooltip(sw_label, "截图监控稳定后等待秒数。\n调小加快速度，调大更稳定。\n建议范围：2-5秒")
        ttk.Spinbox(row1, from_=1, to=10, textvariable=self.stable_wait_var, width=3, command=lambda: self._save_setting("stable_wait", self.stable_wait_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="超时轮数:").pack(side=tk.LEFT, padx=(20,0))
        self.idle_timeout_var = tk.IntVar(value=self._get_config("idle_timeout", 10))
        io_label = ttk.Label(row1, text="?", foreground="blue", cursor="hand2")
        io_label.pack(side=tk.LEFT)
        self._add_tooltip(io_label, "说明1：超时跳过轮数。每轮约3秒，10轮约30秒。建议范围：5-20轮")
        ttk.Spinbox(row1, from_=5, to=30, textvariable=self.idle_timeout_var, width=3, command=lambda: self._save_setting("idle_timeout", self.idle_timeout_var.get())).pack(side=tk.LEFT, padx=5)
        row2 = ttk.Frame(settings_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="千问阈值:").pack(side=tk.LEFT)
        self.qianwen_th_var = tk.DoubleVar(value=self._get_config("qianwen_threshold", 0.55))
        ql_th1 = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql_th1.pack(side=tk.LEFT)
        self._add_tooltip(ql_th1, "窗口1复制键匹配阈值。数值越低越容易匹配。建议范围：0.45-0.60")
        ttk.Spinbox(row2, from_=0.3, to=0.8, increment=0.01, textvariable=self.qianwen_th_var, width=4, command=lambda: self._save_setting("qianwen_threshold", self.qianwen_th_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="智谱阈值:").pack(side=tk.LEFT, padx=(20,0))
        self.zhipu_th_var = tk.DoubleVar(value=self._get_config("zhipu_threshold", 0.48))
        ql_th2 = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql_th2.pack(side=tk.LEFT)
        self._add_tooltip(ql_th2, "窗口2复制键匹配阈值。数值越低越容易匹配。建议范围：0.40-0.55")
        ttk.Spinbox(row2, from_=0.3, to=0.8, increment=0.01, textvariable=self.zhipu_th_var, width=4, command=lambda: self._save_setting("zhipu_threshold", self.zhipu_th_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="扣子阈值:").pack(side=tk.LEFT, padx=(20,0))
        self.coze_th_var = tk.DoubleVar(value=self._get_config("coze_threshold", 0.50))
        ttk.Spinbox(row2, from_=0.3, to=0.8, increment=0.01, textvariable=self.coze_th_var, width=4, command=lambda: self._save_setting("coze_threshold", self.coze_th_var.get())).pack(side=tk.LEFT, padx=5)
        row3 = ttk.Frame(settings_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="滚动次数:").pack(side=tk.LEFT)
        ql2 = ttk.Label(row3, text="?", foreground="blue", cursor="hand2")
        ql2.pack(side=tk.LEFT)
        self._add_tooltip(ql2, "每次截图后滚轮滚动次数。建议范围：5-15次")
        ql = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql.pack(side=tk.LEFT)
        self.scroll_count_var = tk.IntVar(value=self._get_config("scroll_count", 10))
        ttk.Spinbox(row3, from_=3, to=20, textvariable=self.scroll_count_var, width=3, command=lambda: self._save_setting("scroll_count", self.scroll_count_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, text="滚动量:").pack(side=tk.LEFT, padx=(20,0))
        ql3 = ttk.Label(row3, text="?", foreground="blue", cursor="hand2")
        ql3.pack(side=tk.LEFT)
        self._add_tooltip(ql3, "每次滚轮滚动的像素量。建议范围：300-800")
        ql = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql.pack(side=tk.LEFT)
        self.scroll_amount_var = tk.IntVar(value=self._get_config("scroll_amount", 500))
        ttk.Spinbox(row3, from_=100, to=1000, increment=100, textvariable=self.scroll_amount_var, width=4, command=lambda: self._save_setting("scroll_amount", self.scroll_amount_var.get())).pack(side=tk.LEFT, padx=5)
        row_switches = ttk.Frame(settings_frame)
        row_switches.pack(fill=tk.X, pady=2)
        self.ss_enabled_var = tk.BooleanVar(value=self._get_config("screenshot_enabled", True))
        ttk.Checkbutton(row_switches, text="截图监控", variable=self.ss_enabled_var, command=lambda: self._save_setting("screenshot_enabled", self.ss_enabled_var.get())).pack(side=tk.LEFT, padx=5)
        self.fs_enabled_var = tk.BooleanVar(value=self._get_config("fullselect_enabled", True))
        ttk.Checkbutton(row_switches, text="全选监控", variable=self.fs_enabled_var, command=lambda: self._save_setting("fullselect_enabled", self.fs_enabled_var.get())).pack(side=tk.LEFT, padx=5)
        self.robot_enabled_var = tk.BooleanVar(value=self._get_config("robot_enabled", True))
        ttk.Checkbutton(row_switches, text="机器人拦截", variable=self.robot_enabled_var, command=lambda: self._save_setting("robot_enabled", self.robot_enabled_var.get())).pack(side=tk.LEFT, padx=5)

        row5 = ttk.Frame(settings_frame)
        row5.pack(fill=tk.X, pady=2)
        ttk.Label(row5, text="模板窗口:").pack(side=tk.LEFT)
        ql8 = ttk.Label(row5, text="?", foreground="blue", cursor="hand2")
        ql8.pack(side=tk.LEFT)
        self._add_tooltip(ql8, "说明8：窗口模板选择。选择要配置模板的窗口")
        self.template_win_var = tk.StringVar(value="qianwen")
        ttk.Combobox(row5, textvariable=self.template_win_var, values=["qianwen","zhipu","coze","deepseek"], width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row5, text="路径:").pack(side=tk.LEFT, padx=(10,0))
        ql9 = ttk.Label(row5, text="?", foreground="blue", cursor="hand2")
        ql9.pack(side=tk.LEFT)
        self._add_tooltip(ql9, "说明9：模板路径。复制键模板图片的路径")
        self.template_path_var = tk.StringVar(value=self._get_config("template_qianwen", ""))
        ttk.Entry(row5, textvariable=self.template_path_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(row5, text="选择", command=lambda: self._browse_template()).pack(side=tk.LEFT)

        row4 = ttk.Frame(settings_frame)
        row4.pack(fill=tk.X, pady=2)
        ttk.Label(row4, text="全选间隔(秒):").pack(side=tk.LEFT)
        ql4 = ttk.Label(row4, text="?", foreground="blue", cursor="hand2")
        ql4.pack(side=tk.LEFT)
        self._add_tooltip(ql4, "全选监控每次检测的间隔秒数。建议范围：1-5秒")
        ql = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql.pack(side=tk.LEFT)
        self._add_tooltip(ql, "说明4：全选间隔秒数。全选监控每次检测的间隔。建议范围：1-5秒")
        self.fs_interval_var = tk.IntVar(value=self._get_config("fullselect_interval", 3))
        ttk.Spinbox(row4, from_=1, to=5, textvariable=self.fs_interval_var, width=3, command=lambda: self._save_setting("fullselect_interval", self.fs_interval_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Label(row4, text="截图间隔(秒):").pack(side=tk.LEFT, padx=(20,0))
        ql5 = ttk.Label(row4, text="?", foreground="blue", cursor="hand2")
        ql5.pack(side=tk.LEFT)
        self._add_tooltip(ql5, "截图监控每次检测的间隔秒数。建议范围：1-5秒")
        ql = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql.pack(side=tk.LEFT)
        self._add_tooltip(ql, "说明5：截图间隔秒数。截图监控每次检测的间隔。建议范围：1-5秒")
        self.ss_interval_var = tk.IntVar(value=self._get_config("screenshot_interval", 3))
        ttk.Spinbox(row4, from_=1, to=5, textvariable=self.ss_interval_var, width=3, command=lambda: self._save_setting("screenshot_interval", self.ss_interval_var.get())).pack(side=tk.LEFT, padx=5)

        row_stable = ttk.Frame(settings_frame)
        row_stable.pack(fill=tk.X, pady=2)
        ttk.Label(row_stable, text="全选稳定次数:").pack(side=tk.LEFT)
        self.fs_stable_var = tk.IntVar(value=self._get_config("fullselect_stable_count", 2))
        ttk.Spinbox(row_stable, from_=1, to=5, textvariable=self.fs_stable_var, width=3, command=lambda: self._save_setting("fullselect_stable_count", self.fs_stable_var.get())).pack(side=tk.LEFT, padx=5)
        ql_s1 = ttk.Label(row_stable, text="?", foreground="blue", cursor="hand2")
        ql_s1.pack(side=tk.LEFT)
        self._add_tooltip(ql_s1, "全选监控内容不变次数。建议范围：2-3次")
        ttk.Label(row_stable, text="截图稳定次数:").pack(side=tk.LEFT, padx=(20,0))
        self.ss_stable_var = tk.IntVar(value=self._get_config("screenshot_stable_count", 2))
        ttk.Spinbox(row_stable, from_=1, to=5, textvariable=self.ss_stable_var, width=3, command=lambda: self._save_setting("screenshot_stable_count", self.ss_stable_var.get())).pack(side=tk.LEFT, padx=5)
        ql_s2 = ttk.Label(row_stable, text="?", foreground="blue", cursor="hand2")
        ql_s2.pack(side=tk.LEFT)
        self._add_tooltip(ql_s2, "截图监控无变化次数。建议范围：2-3次")

        row4b = ttk.Frame(settings_frame)
        row4b.pack(fill=tk.X, pady=2)
        ttk.Label(row4b, text="点击次数上限:").pack(side=tk.LEFT)
        ql6 = ttk.Label(row4b, text="?", foreground="blue", cursor="hand2")
        ql6.pack(side=tk.LEFT)
        self._add_tooltip(ql6, "复制键最多点击次数。建议范围：1-3次")
        ql = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql.pack(side=tk.LEFT)
        self._add_tooltip(ql, "说明6：点击次数上限。复制键最多点击次数。建议范围：1-3次")
        self.click_max_var = tk.IntVar(value=self._get_config("click_max", 2))
        ttk.Spinbox(row4b, from_=1, to=5, textvariable=self.click_max_var, width=3, command=lambda: self._save_setting("click_max", self.click_max_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Label(row4b, text="截图后等待(秒):").pack(side=tk.LEFT, padx=(20,0))
        ql7 = ttk.Label(row4b, text="?", foreground="blue", cursor="hand2")
        ql7.pack(side=tk.LEFT)
        self._add_tooltip(ql7, "稳定截图后等待时间。建议范围：1-5秒")
        ql = ttk.Label(row2, text="?", foreground="blue", cursor="hand2")
        ql.pack(side=tk.LEFT)
        self._add_tooltip(ql, "说明7：截图后等待秒数。稳定截图后等待时间。建议范围：1-5秒")
        self.screenshot_wait_var = tk.IntVar(value=self._get_config("screenshot_wait", 2))
        ttk.Spinbox(row4b, from_=1, to=5, textvariable=self.screenshot_wait_var, width=3, command=lambda: self._save_setting("screenshot_wait", self.screenshot_wait_var.get())).pack(side=tk.LEFT, padx=5)
        add_frame = ttk.Frame(self.calib_frame)
        add_frame.pack(fill=tk.X, pady=10)
        ttk.Button(add_frame, text="➕ 添加窗口", command=self._add_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(add_frame, text="🗑️ 删除窗口", command=self._remove_window).pack(side=tk.LEFT, padx=5)

    def _build_schedule_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="智能调度：谁空闲谁接活。", foreground="blue").pack(anchor=tk.W, pady=5)
        select_frame = ttk.LabelFrame(frame, text="参与窗口（勾选才会被调度）", padding="5")
        select_frame.pack(fill=tk.X, pady=5)
        self.select_frame = select_frame
        self.schedule_vars = {}
        for name in self.window_configs:
            var = tk.BooleanVar(value=self._get_config("schedule_checks", {}).get(name, True))
            self.schedule_vars[name] = var           
            label = "Qoder CN（我）" if name == "qianwen2" else name
            ttk.Checkbutton(select_frame, text=label, variable=var).pack(side=tk.LEFT, padx=5)
        topic_frame = ttk.Frame(frame)
        topic_frame.pack(fill=tk.X, pady=5)
        ttk.Label(topic_frame, text="初始话题:" ).pack(anchor=tk.W)
        self.schedule_topic_var = tk.StringVar(value= "请讨论：AI的发展会加剧还是缩小数字鸿沟？")
        self.schedule_topic_entry = tk.Text(topic_frame, height=4, width=60)
        self.schedule_topic_entry.pack(fill=tk.X, pady=3)
        self.schedule_topic_entry.bind("<Button-3>", self._right_click)
        self.schedule_topic_entry.bind("<Return>", lambda e: self._start_schedule())
        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill=tk.X, pady=5)
        self.schedule_run_btn = ttk.Button(ctrl_frame, text="🚀 启动智能调度", command=self._start_schedule)
        self.schedule_run_btn.pack(side=tk.LEFT, padx=5)
        self.schedule_switch_var = tk.BooleanVar(value=self._get_config("schedule_enabled", True))
        ttk.Checkbutton(ctrl_frame, text="启用调度", variable=self.schedule_switch_var, command=lambda: self._save_setting("schedule_enabled", self.schedule_switch_var.get())).pack(side=tk.LEFT, padx=5)
        self.schedule_stop_btn = ttk.Button(ctrl_frame, text="⏹️ 停止", command=self._stop_task)
        self.schedule_stop_btn.pack(side=tk.LEFT, padx=5)
        self.schedule_status_text = scrolledtext.ScrolledText(frame, height=12)
        self.schedule_status_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.schedule_status_text.bind("<Button-3>", lambda e: tk.Menu(self.root, tearoff=0).post(e.x_root, e.y_root))
        self.schedule_copy_btn = ttk.Button(frame, text="📋 复制", command=self._copy_schedule_latest)
        self.schedule_copy_btn.pack(anchor=tk.E, pady=2)

    def _build_task_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="预设任务，一键启动桌面自动化。", foreground="blue").pack(anchor=tk.W, pady=5)
        target_frame = ttk.Frame(frame)
        target_frame.pack(fill=tk.X, pady=5)
        ttk.Label(target_frame, text="目标窗口:").pack(side=tk.LEFT)
        self.task_target_var = tk.StringVar(value="千问")
        for t in self.window_configs:
            ttk.Radiobutton(target_frame, text=t, variable=self.task_target_var, value=t).pack(side=tk.LEFT, padx=5)
        desc_frame = ttk.Frame(frame)
        desc_frame.pack(fill=tk.X, pady=5)
        ttk.Label(desc_frame, text="任务描述:").pack(anchor=tk.W)
        self.task_desc_var = tk.StringVar(value="请用200字介绍人工智能的发展历史。")
        ttk.Entry(desc_frame, textvariable=self.task_desc_var, width=70).pack(fill=tk.X, pady=3)
        rounds_frame = ttk.Frame(frame)
        rounds_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rounds_frame, text="运行轮次:").pack(side=tk.LEFT)
        self.task_rounds_var = tk.IntVar(value=1)
        ttk.Spinbox(rounds_frame, from_=1, to=10, textvariable=self.task_rounds_var, width=5).pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        self.task_run_btn = ttk.Button(btn_frame, text="🚀 启动自动化任务", command=self._start_auto_task)
        self.task_run_btn.pack(side=tk.LEFT, padx=5)
        self.task_stop_btn = ttk.Button(btn_frame, text="⏹️ 停止", command=self._stop_task)
        self.task_stop_btn.pack(side=tk.LEFT, padx=5)
        self.task_log_text = scrolledtext.ScrolledText(frame, height=8)
        self.task_log_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def _build_app_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="扫描桌面图标并一键启动应用。", foreground="blue").pack(anchor=tk.W, pady=5)
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.app_listbox = tk.Listbox(list_frame, height=10)
        self.app_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.app_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.app_listbox.config(yscrollcommand=scrollbar.set)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="🔍 扫描桌面图标", command=self._scan_desktop).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🚀 启动选中应用", command=self._launch_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📂 手动添加", command=self._add_shortcut).pack(side=tk.LEFT, padx=5)
        self.app_paths = {}

    def _build_search_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="自动搜索：打开浏览器 → 全选复制 → 发送给AI整理。", foreground="blue").pack(anchor=tk.W, pady=5)
        engine_frame = ttk.Frame(frame)
        engine_frame.pack(fill=tk.X, pady=5)
        ttk.Label(engine_frame, text="搜索引擎:").pack(side=tk.LEFT)
        self.search_engine_var = tk.StringVar(value="Bing")
        engines = list(self.search_engines.keys())
        self.search_engine_combo = ttk.Combobox(engine_frame, textvariable=self.search_engine_var, values=engines, width=15)
        self.search_engine_combo.pack(side=tk.LEFT, padx=5)
        keyword_frame = ttk.Frame(frame)
        keyword_frame.pack(fill=tk.X, pady=5)
        ttk.Label(keyword_frame, text="搜索关键词:").pack(anchor=tk.W)
        self.search_keyword_var = tk.StringVar()
        ttk.Entry(keyword_frame, textvariable=self.search_keyword_var, width=70).pack(fill=tk.X, pady=3)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="🔍 自动搜索并整理", command=self._execute_search).pack(side=tk.LEFT, padx=5)
        content_frame = ttk.LabelFrame(frame, text="搜索结果", padding="5")
        content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.search_content_text = scrolledtext.ScrolledText(content_frame, height=10)
        self.search_content_text.pack(fill=tk.BOTH, expand=True)

    def _right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='复制', command=lambda: self.root.clipboard_append(event.widget.selection_get()))
        menu.add_command(label='粘贴', command=lambda: event.widget.insert(tk.INSERT, self.root.clipboard_get()))
        menu.post(event.x_root, event.y_root)


    def _update_coords(self, name, var):
        try:
            x, y = map(int, var.get().replace(" ", "").split(","))
            self.window_configs[name]["x"] = x
            self.window_configs[name]["y"] = y
        except: pass

    def _calibrate(self, name):
        self.log(f"请把鼠标放在 {name} 的输入框上，5秒后自动捕获...")
        self.root.update()
        time.sleep(5)
        x, y = pyautogui.position()
        self.coord_vars[name].set(f"{x}, {y}")
        self.window_configs[name]["x"] = x
        self.window_configs[name]["y"] = y
        self._save_config()
        self.log(f"✅ {name} 新坐标已保存: ({x}, {y})")

    def _calibrate_read(self, name):
        self.log(f"请把鼠标放在 {name} 的【输出区 / 聊天区】上，5秒后自动捕获...")
        self.root.update()
        time.sleep(5)
        rx, ry = pyautogui.position()
        self.read_coord_vars[name].set(f"{rx}, {ry}")
        self.window_configs[name]["rx"] = rx
        self.window_configs[name]["ry"] = ry
        self._save_config()
        self.log(f"✅ {name} 读取区新坐标已保存: ({rx}, {ry})")

    def _change_grab_type(self, name, grab_type):
        if name in self.window_configs:
            self.window_configs[name]["grab_type"] = grab_type
            self._save_config()
            self.log(f"✅ {name} 监控方式已切换为: {grab_type}")

    def _calibrate_copy_btn(self, name):
        self.log(f"请把鼠标放在 {name} 的【复制键图标（小图标）】上，5秒后自动捕获...")
        self.root.update()
        time.sleep(5)
        x, y = pyautogui.position()
        self.window_configs[name]["copy_rx"] = x
        self.window_configs[name]["copy_ry"] = y
        if hasattr(self, 'copy_coord_vars') and name in self.copy_coord_vars:
            self.copy_coord_vars[name].set(f"{x}, {y}")
        self._save_config()
        self.log(f"✅ {name} 复制键新坐标已保存: ({x}, {y})")

    def _test_capture(self, name, silent=False):
        cfg = self.window_configs.get(name, {})
        rx, ry = cfg.get("rx", cfg.get("x", 0)), cfg.get("ry", cfg.get("y", 0))
        if not silent:
            self.log(f"  🔍 {name} 测试捕获: 点击 ({rx}, {ry}) → Ctrl+A + Ctrl+C ...")
        self.root.update()
        if rx > 0 and ry > 0:
            pyautogui.click(rx, ry)
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.3)
        captured = pyperclip.paste() or ""
        if not silent:
            preview = captured[:80].replace("\n", "↵") if captured else "(空)"
            if captured:
                self.log(f"  ✅ 抓到 {len(captured)} 字符 | 预览: {preview}...")
            else:
                self.log(f"  ⚠ 抓到 0 字符。可能需要重新校准读取区。")
        return captured

    def _test_copy_btn(self, name, click=False):
        cfg = self.window_configs.get(name, {})
        kw = cfg.get("keyword", name)
        hwnd = None
        def _find(h, _):
            nonlocal hwnd
            try:
                if kw and kw in win32gui.GetWindowText(h):
                    hwnd = h
            except:
                pass
        win32gui.EnumWindows(_find, None)
        if not hwnd:
            self.log(f"  [{name}] 窗口未找到 (kw={kw})")
            return ""
        self.log(f"  [{name}] 测试{'点击' if click else '查找'}复制键: hwnd={hwnd}")

        self._scroll_to_bottom(hwnd, cfg, name)
        self.root.update()
        if name == "coze" and click:
            rx = cfg.get("rx", 0)
            ry = cfg.get("ry", 0)
            if rx > 0 and ry > 0:
                pyautogui.click(rx, ry)
                time.sleep(0.3)
            self._scroll_to_bottom(hwnd, cfg, name)
            time.sleep(2.0)

        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.3)
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width, height = right - left, bottom - top
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            img_pil = Image.frombuffer("RGB", (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, "raw", "BGRX", 0, 1)
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            img_full = np.array(img_pil)
            img_gray = cv2.cvtColor(img_full, cv2.COLOR_RGB2GRAY)
        except Exception as e:
            self.log(f"  [{name}] 截图失败: {e}")
            return ""

        template_map = {
            "qianwen": self._get_config("template_qianwen", self._get_config("template_qianwen", r"D:\智联枢纽\copy_btn_qianwen_precise.png")),
            "qianwen2": self._get_config("template_qianwen", self._get_config("template_qianwen", r"D:\智联枢纽\copy_btn_qianwen_precise.png")),
            "coze": r"D:\智联枢纽\copy_btn_coze_color.png",
            "zhipu": r"D:\智联枢纽\copy_btn_zhipu.png",
            "deepseek": r"D:\智联枢纽\copy_btn_template.png",
        }
        template_path = template_map.get(name, r"D:\智联枢纽\copy_btn_template.png")
        if not os.path.exists(template_path):
            self.log(f"  [{name}] 模板不存在: {template_path}")
            return ""
        img_pil_tpl = Image.open(template_path)
        template = np.array(img_pil_tpl.convert("L"))
        if template is None or template.size == 0:
            self.log(f"  [{name}] 模板读取失败")
            return ""
        th, tw = template.shape

        matches = []
        for scale in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
            sw, sh = int(tw * scale), int(th * scale)
            if sw > img_gray.shape[1] or sh > img_gray.shape[0]: continue
            scaled = cv2.resize(template, (sw, sh))
            res = cv2.matchTemplate(img_gray, scaled, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= threshold)
            for pt in zip(*loc[::-1]):
                cx, cy = int(pt[0] + sw // 2), int(pt[1] + sh // 2)
                matches.append((cx, cy, float(res[pt[1], pt[0]]), scale))

        if not matches:
            self.log(f"  [{name}] ❌ 未找到任何匹配 (整窗 {width}x{height})")
            os.makedirs(r"D:\智联枢纽\screenshots", exist_ok=True)
            try:
                Image.fromarray(img_full).save(rf"D:\智联枢纽\screenshots\test_no_match_{name}.png")
                self.log(f"  [{name}] 截图已保存供检查: D:\\智联枢纽\\screenshots\\test_no_match_{name}.png")
            except Exception as e:
                self.log(f"  [{name}] 警告: 截图保存失败: {e}")
            return ""

        self.log(f"  [{name}] ✅ 找到 {len(matches)} 个候选")
        if not matches:
            return ""           

        copy_rx_abs = cfg.get("copy_rx", 0)
        cfg_x = cfg.get("x", 0)
        if name == "coze":
            matches = [m for m in matches if m[0] < left + width * 0.85]
        if name in ("qianwen", "coze", "zhipu") and name != "robot":
            y_min = int(height * 2 / 3)
            y_max = height
            if copy_rx_abs > 0 and cfg_x > 0:
                rel_cx_hint = copy_rx_abs - cfg_x
                abs_x_hint = left + rel_cx_hint
                x_min = max(0, abs_x_hint - 200)
                x_max = min(width, abs_x_hint + 200)
            else:
                x_min, x_max = 0, width
            valid = [m for m in matches if x_min <= m[0] <= x_max and y_min <= m[1] <= y_max]

            if name == "coze":
                copy_rx = cfg.get("copy_rx", 0)
                copy_ry = cfg.get("copy_ry", 0)
                if copy_rx > 0 and copy_ry > 0:
                    abs_x = copy_rx
                    abs_y = copy_ry
                    pyautogui.moveTo(abs_x, abs_y, duration=0.2)
                    time.sleep(1.0)
                    pyautogui.click()
                    time.sleep(0.5)
                    data = self._read_clipboard_with_retry()
                    if data:
                        return data
                    pyautogui.click()
                    time.sleep(0.5)
                    return self._read_clipboard_with_retry() or ""
                return ""

        img_marked = img_full.copy()
        for cx, cy, conf, _ in matches:
            cv2.rectangle(img_marked, (cx-10, cy-10), (cx+10, cy+10), (0, 255, 0), 1) 
            if not matches:
                self.log(f"  [{name}] 未找到任何匹配")
                return ""
        if 'best' not in locals():
             best = matches[0]           
        bx, by = best[0], best[1]
        cv2.rectangle(img_marked, (bx-15, by-15), (bx+15, by+15), (0, 0, 255), 2)
        cv2.putText(img_marked, f"BEST {best[2]:.2f}", (bx+20, by-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        os.makedirs(r"D:\智联枢纽\screenshots", exist_ok=True)
        mark_path = rf"D:\智联枢纽\screenshots\test_copy_btn_{name}.png"
        try:
            Image.fromarray(cv2.cvtColor(img_marked, cv2.COLOR_BGR2RGB)).save(mark_path)
            self.log(f"  [{name}] 📸 标记截图(绿=候选/红=最佳)已保存: {mark_path}")
        except Exception as e:
            self.log(f"  [{name}] 警告: 标记截图保存失败: {e}")

        abs_x = int(left + best[0])
        abs_y = int(top + best[1])
        pyperclip.copy("")
        time.sleep(0.1)
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.3)
        except Exception as e:
            self.log(f"  [{name}] 测试:激活窗口失败: {e}")
        pyautogui.moveTo(abs_x, abs_y)
        pyautogui.click()
        time.sleep(0.5)
        data = self._read_clipboard_with_retry()
        if data:
            self.log(f"  [{name}] 测试:第一次点击成功 → 复制成功: {len(data)} 字符")
            return data
        self.log(f"  [{name}] 测试:第一次未生效，再点一次...")
        pyautogui.click()
        time.sleep(0.8)
        data = self._read_clipboard_with_retry()
        if data:
            self.log(f"  [{name}] 测试:第二次点击成功 → 复制成功: {len(data)} 字符")
            return data
        self.log(f"  [{name}] 测试:2 次点击均失败")
        return ""

    def _add_to_chat(self, role, content):
        self.chat_text.config(state=tk.NORMAL)
        prefix = "🧑 我" if role == "user" else f"🤖 {role}"
        self.chat_text.insert(tk.END, f"{prefix}: {content}\n\n")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)
    def _copy_latest_reply(self):
        content = self.chat_text.get("1.0", tk.END)
        lines = content.split("\n")
        start = -1
        for i in range(len(lines)-1, -1, -1):
            if lines[i].startswith("🤖"):
                start = i
                break
        if start >= 0:
            result = []
            for i in range(start, len(lines)):
                if lines[i].startswith("🧑") or (lines[i].startswith("🤖") and i > start):
                    break
                result.append(lines[i])
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(result))
    def _copy_schedule_latest(self):
        content = self.schedule_status_text.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content.strip())
    def _add_window(self):
        win = tk.Toplevel(self.root)
        win.title("添加窗口")
        win.geometry("420x340")
        win.transient(self.root)
        win.grab_set()
        result = {"name": None, "cfg": None}
        ttk.Label(win, text="窗口名称:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=30).grid(row=0, column=1, padx=10, pady=5)
        type_var = tk.StringVar(value="select")
        ttk.Label(win, text="监控方式:").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        type_frame = ttk.Frame(win)
        type_frame.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        ttk.Radiobutton(type_frame, text="全选监控（Ctrl+A+C，适合DeepSeek等）", variable=type_var, value="select").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="截图监控（模板匹配复制键，适合千问/智谱等）", variable=type_var, value="ocr").pack(anchor='w')
        ttk.Label(win, text="窗口关键词\n(标题包含的字):").grid(row=2, column=0, sticky='w', padx=10, pady=5)
        kw_var = tk.StringVar()
        ttk.Entry(win, textvariable=kw_var, width=30).grid(row=2, column=1, padx=10, pady=5)
        ttk.Label(win, text="任务文件:").grid(row=3, column=0, sticky='w', padx=10, pady=5)
        task_var = tk.StringVar()
        ttk.Entry(win, textvariable=task_var, width=30).grid(row=3, column=1, padx=10, pady=5)
        ttk.Label(win, text="回复文件:").grid(row=4, column=0, sticky='w', padx=10, pady=5)
        reply_var = tk.StringVar()
        ttk.Entry(win, textvariable=reply_var, width=30).grid(row=4, column=1, padx=10, pady=5)
        def toggle_fields():
            is_bridge = type_var.get() == "file_bridge"
            task_var.set(task_var.get() if is_bridge else "")
            reply_var.set(reply_var.get() if is_bridge else "")
        type_var.trace("w", lambda *a: toggle_fields())
        def on_ok():
            name = name_var.get().strip()
            kw = kw_var.get().strip()
            if not name:
                self.log("添加失败：未填名称")
                return
            if name in self.window_configs:
                self.log(f"添加失败：{name} 已存在")
                return
            if type_var.get() == "file_bridge":
                tf = task_var.get().strip() or rf"D:\智联枢纽\{name}_in.txt"
                rf = reply_var.get().strip() or rf"D:\智联枢纽\{name}_out.txt"
                self.window_configs[name] = {
                    "type": "file_bridge",
                    "display_name": name,
                    "window_keyword": kw or name,
                    "input_x": 0, "input_y": 0,
                    "task_file": tf,
                    "reply_file": rf,
                }
            else:
                self.window_configs[name] = {"keyword": kw or name, "x": 0, "y": 0, "placeholder": "", "grab_type": type_var.get()}
            self.window_status[name] = "idle"
            self._save_config()
            self.log(f"✅ 已添加窗口: {name} ({type_var.get()})")
            self._build_calib_rows()
            self._rebuild_schedule_checkbuttons()
            win.destroy()
        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=win.destroy).pack(side=tk.LEFT, padx=5)

    def _remove_window(self):
        name = simpledialog.askstring("删除窗口", "输入要删除的窗口名称:")
        if not name:
            return
        if name not in self.window_configs:
            self.log(f"删除失败：{name} 不存在")
            return
        del self.window_configs[name]
        del self.window_status[name]
        if hasattr(self, 'schedule_vars') and name in self.schedule_vars:
            del self.schedule_vars[name]
        self.log(f"🗑️ 已删除窗口: {name}")
        self._save_config()
        self._build_calib_rows()
        self._rebuild_schedule_checkbuttons()

    def _rebuild_schedule_checkbuttons(self):
        if not hasattr(self, 'select_frame'):
            return
        for w in self.select_frame.winfo_children():
            w.destroy()
        if not hasattr(self, 'schedule_vars'):
            self.schedule_vars = {}
        prev = {n: v.get() for n, v in self.schedule_vars.items()}
        self.schedule_vars = {}
        for name in self.window_configs:
            var = tk.BooleanVar(value=prev.get(name, True))
            self.schedule_vars[name] = var
            label = "Qoder CN（我）" if name == "qianwen2" else name
            ttk.Checkbutton(self.select_frame, text=label, variable=var).pack(side=tk.LEFT, padx=5)

    def _test_file_bridge(self, name):
        cfg = self.window_configs.get(name, {})
        tf = cfg.get("task_file", "")
        rf = cfg.get("reply_file", "")
        if not tf or not rf:
            self.log(f"  [{name}] 文件路径未配置")
            return
    def _send_message(self):
        msg = self.entry.get("1.0", tk.END).rstrip('\n')
        if not msg: return
        self.entry.delete("1.0", tk.END)
        self._add_to_chat("user", msg)
        self.stop_event.clear()

        # 处理 [@send_to:窗口名] 格式
        if msg.startswith("[@send_to:"):
            fixed_msg = msg.replace('\\n', '\n')
            self._worker_to_schedule = False
            self.bridge.process_ai_response(fixed_msg)
            return

        target = self.target_var.get()
        at_pos = msg.find("@")
        if at_pos >= 0:
            after_at = msg[at_pos+1:].strip()
            # 提取 @ 后的第一个词作为候选窗口名
            first_word = after_at.split()[0] if after_at else ""
            if first_word in self.window_configs:
                # @后面是窗口名 → 切换目标窗口，并移除 @窗口名 部分
                target = first_word
                before_at = msg[:at_pos].strip()
                after_win = after_at[len(first_word):].strip()
                msg = (before_at + " " + after_win).strip()
                if not msg:
                    return
            else:
                # @后面不是窗口名 → 机器人指令
                code = after_at
                if code:
                    result = nexus_worker.execute(code, extra_globals={"app": self})
                    self._add_to_chat("机器人", str(result))
                    return

        threading.Thread(target=lambda: self._do_send_and_capture(target, msg, True), daemon=True).start()            
    def _stop_task(self):
        self.stop_event.set()
        for name in self.window_status:
            self.window_status[name] = "idle"
        self.log("用户手动停止任务。调度已重置。")

    def _copy_to_clipboard(self, text):
        for _retry in range(5):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return True
            except Exception:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
                time.sleep(0.2)
        self.log(f"  剪贴板写入失败（重试 5 次仍被占用）")
        return False

    def _do_send_and_capture(self, name, msg, show_in_chat=False):
        # name_map = {"DeepSeek": "deepseek", "千问": "qianwen", "扣子": "coze", "Qoder CN": "qianwen2", "智谱": "zhipu"}
        # name = name_map.get(name, name)
        cfg = self.window_configs.get(name, {})
        kw = cfg.get("keyword", name)

        # ============ 1. 文件桥接窗口 (qianwen2) ============
        if cfg.get("type") == "file_bridge":
            hwnd = None
            def _enum(h, _):
                nonlocal hwnd
                if cfg.get("window_keyword", "") in win32gui.GetWindowText(h):
                    hwnd = h
            win32gui.EnumWindows(_enum, None)
            msg_with_hint = msg + "\n\n（请完成回复后，将回复内容写入 " + cfg.get("reply_file", r"D:\智联枢纽\qianwen2_out.txt") + "，覆盖写入，不要追加）"
            if hwnd:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                ix, iy = cfg.get("x", 0), cfg.get("y", 0)
                if ix > 0 and iy > 0:
                    pyautogui.click(ix, iy)
                else:
                    rect = win32gui.GetWindowRect(hwnd)
                    pyautogui.click(rect[0] + (rect[2]-rect[0])//2, rect[1] + (rect[3]-rect[1])//2)
                time.sleep(0.2)
                if self._copy_to_clipboard(msg_with_hint):
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.2)
                    pyautogui.press('enter')
                    self.log(f"  [qianwen2] 已粘贴消息到 Qoder CN 窗口（带写文件指令）")
            else:
                self.log(f"  [qianwen2] Qoder CN 窗口未找到，改为纯文件写入")
            try:
                with open(cfg.get("task_file", r"D:\智联枢纽\qianwen2_in.txt"), "w", encoding="utf-8") as f:
                    f.write(msg_with_hint)
            except Exception as e:
                self.log(f"  [qianwen2] 写入任务文件失败: {e}")
            return self._file_bridge(name, msg, skip_write=True)

        # ============ 2. 普通截屏窗口 (DeepSeek, 千问, 扣子, 智谱) ============
        task_msg = msg
        if name == "qianwen":
            task_msg = task_msg + "\n\n（请直接在左侧对话框回复，不要使用文件发送功能，不要切换到右侧输出框，所有内容直接显示在聊天区）"

        self.log(f"  发送到 {name}: {msg[:50]}...")

        hwnd = None
        def f(h, _):
            nonlocal hwnd
            title = win32gui.GetWindowText(h)
            if kw in title or name in title:
                hwnd = h
        win32gui.EnumWindows(f, None)
        if not hwnd:
            def f2(h, _):
                nonlocal hwnd
                if name in win32gui.GetWindowText(h):
                    hwnd = h
            win32gui.EnumWindows(f2, None)
        if not hwnd: 
            self.log(f"  [{name}] 未找到窗口")
            return ""
        if win32gui.IsIconic(hwnd): 
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)      
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)

        if not self._copy_to_clipboard(task_msg):
            return ""

        # ==================== 【核心修复】补回点击输入框、粘贴、回车发送 ====================
        try:
            ix, iy = cfg.get("x", 0), cfg.get("y", 0)
            if ix > 0 and iy > 0:
                pyautogui.click(ix, iy)
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.1)
                pyautogui.press('delete')
                time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            self.log(f"  [{name}] 消息已粘贴并回车发送")
        except Exception as e:
            self.log(f"  [{name}] 粘贴发送动作异常: {e}")
            return ""

        time.sleep(1.5)
        # ======================================================================================
        grab_type = "select" if name == "robot" else self.window_configs.get(name, {}).get("grab_type", "ocr")
        if grab_type == "ocr":
            return self._screenshot_monitor_and_grab(hwnd, name, cfg, show_in_chat)
        elif grab_type == "select":
            return self._select_monitor_and_marker_extract(hwnd, name, cfg, show_in_chat)
        else:
            return self._screenshot_monitor_and_grab(hwnd, name, cfg, show_in_chat)
        return ""

    def _simple_select(self, hwnd, cfg):
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
            x, y = cfg.get("rx", cfg.get("x", 0)), cfg.get("ry", cfg.get("y", 0))
            if x > 0 and y > 0:
                cx, cy = x, y
            else:
                rect = win32gui.GetWindowRect(hwnd)
                cx = rect[0] + (rect[2] - rect[0]) // 2
                cy = rect[1] + (rect[3] - rect[1]) // 2
            pyautogui.click(cx, cy)
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'end')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            text = pyperclip.paste() or ""
            # 【关键修复】抓取完毕后，按一下 Esc 键取消全选高亮，防止画面一直卡在蓝底状态
            pyautogui.press('esc')
            time.sleep(0.3)
            rx = cfg.get("rx", 0)
            ry = cfg.get("ry", 0)
            if rx > 0 and ry > 0:
                pyautogui.click(rx, ry)
                time.sleep(0.3)
                btn_text = pyperclip.paste() or ""
                if btn_text and len(btn_text) > 10:
                    return btn_text
            return text
        except Exception as e:
            self.log(f"  [simple_select] 异常: {e}")
            return ""
    def _select_monitor_and_marker_extract(self, hwnd, name, cfg, show_in_chat):
        idle_count = 0
        last_content = ""
        stable_count = 0

        while not self.stop_event.is_set():
            interval = self._get_config("fullselect_interval", 3)
            for _ in range(int(interval * 5)):
                if self.stop_event.is_set():
                    break
                time.sleep(0.2)
            if self.stop_event.is_set():
                break
            if not win32gui.IsWindow(hwnd):
                self.log(f"  [{name}] 窗口已关闭")
                return ""

            cur_content = self._simple_select(hwnd, cfg)

            if not cur_content.strip():
                idle_count += 1
                if idle_count >= 10:
                    self.log(f"  [{name}] 30秒无响应（用户设置），跳过")
                    return ""
                continue

            if not stable_count and cur_content != last_content:
                self.log(f"  [{name}] AI开始回复，长度: {len(cur_content)}")
                last_content = cur_content
                continue

            if cur_content == last_content and cur_content.strip():
                stable_count += 1
                self.log(f"  [{name}] 内容稳定（{stable_count}/2）")
                sc = self._get_config("fullselect_stable_count", 2)
                if stable_count >= sc:
                    self.log(f"  [{name}] 连续{sc}次稳定，尝试抓取...")

                    # 不再进行最后一次全选，直接点击复制键
                    rx = cfg.get("rx", 0)
                    ry = cfg.get("ry", 0)
                    if rx > 0 and ry > 0:
                        pyautogui.press("esc")
                        time.sleep(0.3)
                        pyperclip.copy("")
                        time.sleep(0.1)
                        pyautogui.click(rx, ry)
                        time.sleep(0.3)
                        btn_content = pyperclip.paste() or ""
                        if btn_content and len(btn_content) > 10:
                            self.log(f"  [{name}] 复制键抓取成功: {len(btn_content)} 字符")
                            if show_in_chat:
                                self.root.after(0, lambda c=btn_content: self._add_to_chat(name, c))
                            return btn_content

                    # 兜底：如果复制键抓取失败，重新全选一次
                    final_content = self._simple_select(hwnd, cfg)
                    if final_content and len(final_content.strip()) > 0:
                        self.log(f"  [{name}] 全选兜底成功: {len(final_content)} 字符")
                        if show_in_chat:
                            self.root.after(0, lambda c=final_content: self._add_to_chat(name, c))
                        return final_content
                    else:
                        self.log(f"  [{name}] 抓取失败，将在下一轮重试")
                        time.sleep(2)
                        return ""
                last_content = cur_content
                self.log(f"  [{name}] 内容有变化，长度: {len(cur_content)}")

        return cur_content if cur_content and cur_content.strip() else last_content

    def _simple_select(self, hwnd, cfg):
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
            x, y = cfg.get("rx", cfg.get("x", 0)), cfg.get("ry", cfg.get("y", 0))
            if x > 0 and y > 0:
                cx, cy = x, y
            else:
                rect = win32gui.GetWindowRect(hwnd)
                cx = rect[0] + (rect[2] - rect[0]) // 2
                cy = rect[1] + (rect[3] - rect[1]) // 2
            pyautogui.click(cx, cy)
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'end')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            text = pyperclip.paste() or ""
            # 抓取完毕后，按 Esc 键取消全选高亮，防止画面卡在蓝底状态
            pyautogui.press('esc')
            time.sleep(0.1)
            return text
        except Exception as e:
            self.log(f"  [simple_select] 异常: {e}")
            return ""
    def _extract_reply(self, content, name=""):
        if not content:
            return None
        end_idx = content.rfind(self.END_MARKER)
        if end_idx >= 0:
            content = content[:end_idx + len(self.END_MARKER)]
        start_idx = content.rfind(self.START_MARKER)
        if start_idx >= 0:
            return content[start_idx + len(self.START_MARKER):].strip()
        return None

    def _scroll_to_bottom(self, hwnd, cfg, name=""):
        try:
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)
            if name == 'zhipu':
                pyautogui.hotkey('ctrl', 'end')
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'end')
                time.sleep(0.3)
                for _ in range(10):
                    pyautogui.scroll(-500)
                    time.sleep(0.08)
            else:
                rx, ry = cfg.get("rx", 0), cfg.get("ry", 0)
                if rx > 0 and ry > 0:
                    pyautogui.click(rx, ry)
                    time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'end')
                time.sleep(0.2)
                for _ in range(10):
                    pyautogui.scroll(-500)
                    time.sleep(0.08)
            time.sleep(0.1)
            self.log(f"  [scroll] Ctrl+End + 滚轮兜底 已执行")
        except Exception as e:
            self.log(f"  [scroll] 异常: {e}")

    def _find_copy_btn_near(self, hwnd, name, cfg, anchor_x, anchor_y, search_radius=80):
        template_map = {
            "qianwen": r"D:\智联枢纽\copy_btn_qianwen.png",
            "qianwen2": r"D:\智联枢纽\copy_btn_qianwen.png",
            "coze": r"D:\智联枢纽\copy_btn_coze_color.png",
            "zhipu": r"D:\智联枢纽\copy_btn_zhipu.png",
            "deepseek": r"D:\智联枢纽\copy_btn_template.png",
        }
        template_path = template_map.get(name, r"D:\智联枢纽\copy_btn_template.png")
        if not os.path.exists(template_path):
            return None
        try:
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width, height = right - left, bottom - top
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            img_pil = Image.frombuffer("RGB", (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, "raw", "BGRX", 0, 1)
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            img_gray = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2GRAY)
            offset_x, offset_y = 0, 0
            if name == "coze":
                h, w = img_gray.shape[:2]
                y_start = int(h * 0.6)
                img_gray = img_gray[y_start:, :]
                x_start = int(w * 0.4)
                img_gray = img_gray[:, x_start:]
                offset_y = y_start
                offset_x = x_start
            else:
                offset_x, offset_y = 0, 0
            img_pil_tpl = Image.open(template_path)
            template = np.array(img_pil_tpl.convert("L"))
            th, tw = template.shape
            rel_ax = anchor_x - left
            rel_ay = anchor_y - top
            matches = []
            for scale in [0.75, 1.0, 1.25, 1.5]:
                sw, sh = int(tw * scale), int(th * scale)
                if sw > img_gray.shape[1] or sh > img_gray.shape[0]: continue
                scaled = cv2.resize(template, (sw, sh))
                res = cv2.matchTemplate(img_gray, scaled, cv2.TM_CCOEFF_NORMED)
                qth = self._get_config("qianwen_threshold", 0.55)
                zth = self._get_config("zhipu_threshold", 0.48)
                cth = self._get_config("coze_threshold", 0.50)
                threshold = qth if name == "qianwen" else (zth if name == "zhipu" else cth)
                loc = np.where(res >= threshold)
                for pt in zip(*loc[::-1]):
                    cx, cy = int(pt[0] + sw // 2) + offset_x, int(pt[1] + sh // 2) + offset_y
                    matches.append((cx, cy, float(res[pt[1], pt[0]]), scale))
            if not matches:
                return None
            valid = [m for m in matches if abs(m[0] - rel_ax) <= search_radius and abs(m[1] - rel_ay) <= search_radius]
            if not valid:
                return None
            best = min(valid, key=lambda m: (m[0] - rel_ax) ** 2 + (m[1] - rel_ay) ** 2)
            return (int(left + best[0]), int(top + best[1]))
        except Exception as e:
            self.log(f"  [find_copy_btn_near] 异常: {e}")
            return None

    def _screenshot_monitor_and_grab(self, hwnd, name, cfg, show_in_chat):
        idle_count = 0
        last_screenshot = None
        stable_count = 0
        click_fail_count = 0

        while not self.stop_event.is_set():
            interval = self._get_config("screenshot_interval", 3)
            for _ in range(int(interval * 3)):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.33)
            idle_count += 1
            timeout = self._get_config("idle_timeout", 10)
            if idle_count > timeout:
                self.log(f"  [{name}] 超时30秒无稳定回复，先跳过")
                return ""
            if self.stop_event.is_set():
                break
            if not win32gui.IsWindow(hwnd):
                self.log(f"  [{name}] 窗口已关闭")
                return ""

            try:
                rect = win32gui.GetWindowRect(hwnd)
                left, top, right, bottom = rect
                width, height = right - left, bottom - top
                if width < 100 or height < 100:
                    self.log(f"  [{name}] 窗口尺寸异常: {width}x{height}")
                    idle_count += 1
                    if idle_count >= 10:
                        self.log(f"  [{name}] 30秒窗口异常，放弃")
                        return ""
                    continue
                screenshot = pyautogui.screenshot(region=(left, top, width, height))
                cur_screenshot = np.array(screenshot)
            except Exception as e:
                self.log(f"  [{name}] 截图异常: {e}")
                idle_count += 1
                if idle_count >= 10:
                    self.log(f"  [{name}] 30秒连续截图异常，放弃")
                    return ""
                continue

            if last_screenshot is None:
                last_screenshot = cur_screenshot
                self.log(f"  [{name}] 建立截图基线（窗口: {width}x{height}）")
                stable_count = 0
                idle_count = 0
                continue

            if cur_screenshot.shape != last_screenshot.shape:
                self.log(f"  [{name}] 截图尺寸变化: {last_screenshot.shape} -> {cur_screenshot.shape}，重置基线")
                last_screenshot = cur_screenshot
                stable_count = 0
                idle_count = 0
                continue
            
            diff = int(np.sum(np.abs(cur_screenshot.astype(int) - last_screenshot.astype(int))))
            if diff > 2000:
                idle_count = 0
                if 2000 < diff < 5000000:
                    stable_count += 1
                    self.log(f"  [{name}] 中幅残留（{diff}像素），稳定计数 {stable_count}/2")
                else:
                    stable_count = 0
                    last_screenshot = cur_screenshot
                    self.log(f"  [{name}] 截图有变化（{diff}像素），继续等待...")
            else:
                idle_count += 1
                stable_count += 1
                self.log(f"  [{name}] 截图无变化（稳定{stable_count}/2）")

            sc = self._get_config("screenshot_stable_count", 2)
            if stable_count >= sc:
                self.log(f"  [{name}] 连续{sc}次稳定，回复结束，准备滚动到底并独立抓取...")
                if name == 'zhipu':
                    pyautogui.click(width - 100, height//2)
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'end')
                    time.sleep(0.5)
                    for _ in range(15):
                        pyautogui.scroll(-500)
                        time.sleep(0.05)
                    time.sleep(2)
                else:
                    self._scroll_to_bottom(hwnd, cfg, name)
                    if name in ("qianwen",):
                        time.sleep(3)
                    else:
                        time.sleep(2)

                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    left, top, right, bottom = rect
                    width, height = right - left, bottom - top
                    screenshot = pyautogui.screenshot(region=(left, top, width, height))
                    img_full = np.array(screenshot)
                    img_gray = cv2.cvtColor(img_full, cv2.COLOR_RGB2GRAY)
                    self.log(f"  [{name}] 抓取截图成功: ({width}x{height})，已保存到文件")
                    try:
                        save_dir = r"D:\智联枢纽\screenshots"
                        os.makedirs(save_dir, exist_ok=True)
                        save_path = os.path.join(save_dir, f"grab_{name}.png")
                        screenshot.save(save_path)
                        self.log(f"  [{name}] 诊断截图已保存: {save_path}")
                    except Exception as e:
                        self.log(f"  [{name}] 截图保存失败: {e}")
                except Exception as e:
                    self.log(f"  [{name}] 屏幕截图失败: {e}")
                    stable_count = 0
                    last_screenshot = cur_screenshot
                    continue

                template_map = {
                    "qianwen": self._get_config("template_qianwen", self._get_config("template_qianwen", r"D:\智联枢纽\copy_btn_qianwen_precise.png")),
                    "qianwen2": self._get_config("template_qianwen", self._get_config("template_qianwen", r"D:\智联枢纽\copy_btn_qianwen_precise.png")),
                    "coze": r"D:\智联枢纽\copy_btn_coze_color.png",
                    "zhipu": r"D:\智联枢纽\copy_btn_zhipu.png",
                }
                template_path = template_map.get(name, r"D:\智联枢纽\copy_btn_template.png")
                if not os.path.exists(template_path):
                    self.log(f"  [{name}] 模板文件缺失")
                    return ""
                tpl_pil = Image.open(template_path).convert("L")
                template = np.array(tpl_pil)
                th, tw = template.shape
                matches = []
                for scale in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
                    sw, sh = int(tw*scale), int(th*scale)
                    if sw > img_gray.shape[1] or sh > img_gray.shape[0]: continue
                    scaled = cv2.resize(template, (sw, sh))
                    res = cv2.matchTemplate(img_gray, scaled, cv2.TM_CCOEFF_NORMED)
                    qth = self._get_config("qianwen_threshold", 0.55)                                      
                    zth = self._get_config("zhipu_threshold", 0.48)                   
                    cth = self._get_config("coze_threshold", 0.50)                   
                    threshold = qth if name == "qianwen" else (zth if name == "zhipu" else cth)
                    loc = np.where(res >= threshold)
                    for pt in zip(*loc[::-1]):
                        cx, cy = int(pt[0] + sw//2), int(pt[1] + sh//2)
                        matches.append((cx, cy, float(res[pt[1], pt[0]]), scale))
                if not matches:
                    self.log(f"  [{name}] 未找到复制键候选")
                    stable_count = 0
                    last_screenshot = cur_screenshot
                    continue
                self.log(f"  [{name}] ✅ 找到 {len(matches)} 个候选")

                search_zone = cfg.get("search_zone", None)
                if search_zone:
                    x_min = int(width * search_zone.get("x_start", 0.87))
                    x_max = int(width * search_zone.get("x_end", 0.95))
                    y_min = int(height * search_zone.get("y_start", 0.85))
                    y_max = int(height * search_zone.get("y_end", 0.92))
                    candidates = [m for m in matches if x_min <= m[0] <= x_max and y_min <= m[1] <= y_max]
                    self.log(f"  [{name}] 小区域搜索: x({x_min}-{x_max}), y({y_min}-{y_max}), 候选 {len(candidates)} 个")
                else:
                    y_min = int(height * 0.45)
                    y_max = height
                    x_min = int(width * 0.25)
                    x_max = width
                    candidates = [m for m in matches if x_min <= m[0] <= x_max and y_min <= m[1] <= y_max]

                if not candidates:
                    self.log(f"  [{name}] 模板匹配失败，自动降级为全选抓取...")
                    return self._simple_select(hwnd, cfg)
                    self.log(f"  [{name}] 底部1/3无候选，扩大到底部1/2降阈值重试...")
                    matches_low = []
                    for scale in [0.5, 0.75, 1.0, 1.25, 1.5]:
                        sw, sh = int(tw*scale), int(th*scale)
                        if sw > img_gray.shape[1] or sh > img_gray.shape[0]: continue
                        scaled = cv2.resize(template, (sw, sh))
                        res = cv2.matchTemplate(img_gray, scaled, cv2.TM_CCOEFF_NORMED)
                        loc = np.where(res >= 0.4)
                        for pt in zip(*loc[::-1]):
                            cx, cy = int(pt[0] + sw//2), int(pt[1] + sh//2)
                            matches_low.append((cx, cy, float(res[pt[1], pt[0]]), scale))
                    if name == "zhipu":
                        x_min_low = int(width * 0.5)
                        y_min_low = int(height * 0.5)
                        candidates = [m for m in matches_low if m[0] > x_min_low and m[1] > y_min_low]
                        if candidates:
                            best = min(candidates, key=lambda m: m[0])
                    else:
                        if matches_low:
                            candidates = [m for m in matches_low if m[1] > int(height*0.5)]
                    if not candidates:
                        abs_x = left + int(width * 0.35)
                        abs_y = top + int(height * 0.92)
                        self.log(f"  [{name}] 匹配失败，使用固定坐标: ({abs_x},{abs_y})")
                        candidates = [(abs_x, abs_y, 0, 1)]
                    else:
                        self.log(f"  [{name}] 低阈值底部找到 {len(candidates)} 候选")
                else:
                    self.log(f"  [{name}] 底部1/3区域 {len(candidates)} 候选")

                if name == "coze":
                    best = min(candidates, key=lambda m: m[0])
                else:
                    best = max(candidates, key=lambda m: m[2])
                self.log(f"  [{name}] 最佳匹配置信度: {best[2]:.3f}, 位置: ({best[0]}, {best[1]})")
                abs_x = int(left + best[0])
                abs_y = int(top + best[1])
                self.log(f"  [{name}] 独立抓取: 选中({abs_x},{abs_y}) 置信度{best[2]:.2f}")

                if name == "coze" and name != "zhipu":
                    copy_rx = cfg.get("copy_rx", 0)
                    copy_ry = cfg.get("copy_ry", 0)
                    if copy_rx > 0 and copy_ry > 0:
                        rect = win32gui.GetWindowRect(hwnd)
                        abs_x = rect[0] + (copy_rx - cfg.get("x", 0))
                        abs_y = rect[1] + (copy_ry - cfg.get("y", 0))
                        pyautogui.moveTo(abs_x, abs_y, duration=0.1)
                        time.sleep(0.2)
                        pyautogui.click()
                        data = ""
                        for _ in range(6):
                            time.sleep(0.2)
                            data = self._read_clipboard_with_retry()
                            if data and len(data) > 1:
                                break
                        if data and len(data) > 1:
                            self.log(f"  [coze] 一次点击成功: {len(data)} 字符")
                            if show_in_chat:
                                self.root.after(0, lambda c=data: self._add_to_chat(name, c))
                            return data
                        else:
                            self.log(f"  [coze] 一次点击后剪贴板仍为空")
                    else:
                        self.log(f"  [coze] 复制键未校准")
                    stable_count = 0
                    last_screenshot = cur_screenshot
                    return ""

                try:
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.2)
                except: pass
                pyperclip.copy("")
                time.sleep(0.1)
                rx=cfg.get("rx",0);ry=cfg.get("ry",0)
                if rx>0 and ry>0:
                    pyautogui.click(rx,ry)
                    time.sleep(0.2)
                rx=cfg.get("rx",0);ry=cfg.get("ry",0)
                if rx>0 and ry>0:
                    pyautogui.click(rx,ry)
                    time.sleep(0.3)
                pyautogui.moveTo(abs_x, abs_y, duration=0.1)
                time.sleep(0.2)
                click_max = 1
                data = ""
                for click_i in range(click_max):
                    if click_i > 0:
                        pyautogui.moveTo(abs_x, abs_y, duration=0.1)
                        time.sleep(0.2)
                    pyautogui.click()
                    for _ in range(5):
                        time.sleep(0.2)
                        data = self._read_clipboard_with_retry()
                        if data and len(data) > 1:
                            break
                    if data:
                        break
                if data:
                    self.log(f"  [{name}] 独立抓取成功: {len(data)} 字符")
                    if show_in_chat:
                        self.root.after(0, lambda c=data: self._add_to_chat(name, c))
                    return data
                click_fail_count += 1
                if click_fail_count >= 2:
                    self.log(f"  [{name}] 点击失败{click_fail_count}次，放弃抓取")
                    return ""
                stable_count = 0
                last_screenshot = cur_screenshot
                continue
        return ""

    def _click_copy_grab(self, hwnd, name="qianwen", cfg=None):
        if name in ("qianwen", "coze", "zhipu") and name != "robot":
            return self._test_copy_btn(name, click=True)
        return ""

    def _read_clipboard_with_retry(self):
        for _ in range(2):
            time.sleep(0.3)
            try:
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                    if data and len(data) >= 0:
                        return data
                win32clipboard.CloseClipboard()
            except:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
        try:
            data = pyperclip.paste()
            if data:
                return data
        except:
            pass
        return ""

    def _start_schedule(self):
        self._schedule_running = False
        if not self._get_config("schedule_enabled", True):
            self.schedule_status_text.insert(tk.END, "调度功能已禁用\n")
            return
        self.stop_event = threading.Event()
        self.stop_event.clear()             
        for name in self.window_status:
            self.window_status[name] = "idle"
        self.schedule_status_text.delete(1.0, tk.END)
        threading.Thread(target=self._unified_schedule_loop, daemon=True).start()

    def _unified_schedule_loop(self):
        active = [n for n, v in self.schedule_vars.items() if v.get()]
        if not active:
            self.schedule_status_text.insert(tk.END, "没有选择任何窗口。\n")
            return
        topic = self.schedule_topic_entry.get("1.0", tk.END).strip()
        if hasattr(self, 'bridge'):
            self._worker_to_schedule = True
        self.bridge.process_ai_response(topic)
        self._worker_to_schedule = False
        if topic.strip().startswith("@"):
            code = topic.strip()[1:].strip()
            result = self.bridge.process_ai_response(chr(64)+code)
            self.schedule_status_text.insert(tk.END, f"🤖 执行结果: {result}\n\n")
            self.schedule_topic_entry.delete("1.0", tk.END)
            return
        self.schedule_topic_entry.delete("1.0", tk.END)
        self.speech_pool = [topic]
        self.speech_authors = ["system"]
        self.last_assigned_idx = {name: -1 for name in active}

        self.schedule_status_text.insert(tk.END, f"调度启动: {active}\n话题: {topic[:80]}...\n\n")

        while not self.stop_event.is_set():
            idle_windows = [n for n in active if self.window_status.get(n, "idle") == "idle"]
            self.log(f"  [调度心跳] 新一轮循环开始，时间戳: {time.time()}, idle: {idle_windows}")
            pending_windows = [n for n in active if self.window_status.get(n) == "pending"]

            if not idle_windows and pending_windows:
                for name in pending_windows:
                    self.log(f"  [调度派发] 即将派发给 {name}，时间戳: {time.time()}")
                    self.schedule_status_text.insert(tk.END, f"🔄 回来检查 pending: {name}\n")
                    self.schedule_status_text.see(tk.END)
                    content = self._recheck_pending(name)
                    if content and len(content.strip()) > 0:
                        self.speech_pool.append(content)
                        self.speech_authors.append(name)
                        self.window_status[name] = "idle"
                        self.schedule_status_text.insert(tk.END, f"✅ {name} 延后抓取成功, 长度: {len(content)}\n\n")
                    else:
                        self.schedule_status_text.insert(tk.END, f"⏳ {name} 仍未完成，继续 pending\n\n")
                for _ in range(10):
                    if self.stop_event.is_set(): break
                    time.sleep(0.2)
                continue

            if not idle_windows:
                for _ in range(10):
                    if self.stop_event.is_set(): break
                    time.sleep(0.2)
                continue

            last_active = {name: -1 for name in idle_windows}
            for name in idle_windows:
                for i in range(len(self.speech_authors) - 1, -1, -1):
                    if self.speech_authors[i] == name:
                        last_active[name] = i
                        break
            idle_windows.sort(key=lambda n: last_active[n])
            self.log(f"  [调度诊断] 候选排序: {[(n, last_active[n]) for n in idle_windows]}, pool_size={len(self.speech_pool)}")

            has_route = False
            route_target_internal = None
            if self.speech_pool:
                _probe_speech = self.speech_pool[-1]
                _match = self.SEND_TO_PATTERN.search(_probe_speech)
                if _match:
                    has_route = True
                    route_target_internal = self._resolve_route_name(_match.group(1).strip())
                else:
                    for _win_name in self.ROUTE_NAMES:
                        if f"@{_win_name}" in _probe_speech:
                            has_route = True
                            route_target_internal = self._resolve_route_name(_win_name)
                            break
            route_can_dispatch = False
            if has_route and route_target_internal in idle_windows:
                _last_assigned = self.last_assigned_idx.get(route_target_internal, -1)
                for _i in range(len(self.speech_pool) - 1, -1, -1):
                    _author = self.speech_authors[_i] if _i < len(self.speech_authors) else "system"
                    if _author != route_target_internal and _i > _last_assigned:
                        route_can_dispatch = True
                        break
            if has_route and route_can_dispatch and route_target_internal in idle_windows:
                idle_windows.remove(route_target_internal)
                idle_windows.insert(0, route_target_internal)
                self.log(f"  [路由] 命中 → {route_target_internal} 优先派发")
            

            assigned = False
            for target in idle_windows:
                latest_speech = None
                chosen_idx = -1
                for i in range(len(self.speech_pool) - 1, -1, -1):
                    author = self.speech_authors[i] if i < len(self.speech_authors) else "system"
                    if author != target and i > self.last_assigned_idx.get(target, -1):
                        latest_speech = self.speech_pool[i]
                        chosen_idx = i
                        break

                if latest_speech is None:
                    self.log(f"  [调度诊断] target={target} 未找到可消费 speech")
                    continue
                self.log(f"  [调度诊断] target={target} 找到 speech idx={chosen_idx} (author={self.speech_authors[chosen_idx] if chosen_idx < len(self.speech_authors) else 'system'})")

                self.log(f"  📤 派发 {target}: {latest_speech[:50]}...")
                self.schedule_status_text.insert(tk.END, f"📤 {latest_speech[:50]}... → {target}\n")
                self.schedule_status_text.see(tk.END)

                self.window_status[target] = "busy"
                self.log(f"  ⏳ {target} 设为 busy, 开始抓取...")
                at_pos = latest_speech.find("@")
                if at_pos >= 0:
                    first_word = latest_speech[at_pos+1:].strip().split()[0] if latest_speech[at_pos+1:].strip() else ""
                    if first_word in self.window_configs:
                        target = first_word
                        self.log(f"  [路由] 识别到@{first_word}，切换发送目标")
                reply = self._do_send_and_capture(target, latest_speech)
                self.log(f"  📨 {target} 抓取返回: 长度={len(reply) if reply else 0}")

                self.window_status[target] = "idle"

                if reply and len(reply.strip()) > 0:
                    print(f"[主程序] 即将处理回复，前200字: {reply[:200]}")
                    self._worker_to_schedule = True
                    self.bridge.process_ai_response(reply)
                    self._worker_to_schedule = False
                    if "STOP_SCHEDULE" in reply:
                        self.log("检测到停止信号，自动停止调度")
                        self.stop_event.set()
                        for n in self.window_status:self.window_status[n]="idle"
                        self.schedule_status_text.insert(tk.END, "任务完成，调度已自动停止。\n")
                        return
                    self.speech_pool.append(reply)
                    self.speech_authors.append(target)
                    self.log(f"  ✅ {target} 回复追加到 speech_pool, 长度: {len(reply)}, pool 现在 {len(self.speech_pool)} 条")
                    self.schedule_status_text.insert(tk.END, f"✅ {target} 回复, 长度: {len(reply)}\n\n")

                if target == "coze":
                    self._force_send_to("qianwen", reply + "\n\n（请千问收到后，自动 @DeepSeek 继续讨论）")
                self.last_assigned_idx[target] = chosen_idx
                self.log(f"  📊 last_assigned_idx[{target}] = {chosen_idx}")
                assigned = True
                self.log(f"  [调度诊断] assigned=True, pool_size={len(self.speech_pool)}")
                break

        if not assigned:
            self.log(f"  [调度诊断] assigned=False, pool_size={len(self.speech_pool)}, idle_count={len(idle_windows)} (本轮无派发)")

        pending_list = [n for n in active if self.window_status.get(n) == "pending"]
        if pending_list:
            for pn in pending_list:
                self.log(f"  [清扫] 尝试重抓 pending 窗口: {pn}")
                content = self._recheck_pending(pn)
                if content and len(content.strip()) > 0:
                    self.speech_authors.append(pn)
                    self.window_status[pn]="idle"
                    self.schedule_status_text.insert(tk.END, f"✅ {pn} 清扫重抓成功, 长度: {len(content)}\n\n")

            self.stop_event.wait(timeout=0.5)
        if not assigned:
            self.log(f"  [调度诊断] assigned=False, pool_size={len(self.speech_pool)}, idle_count={len(idle_windows)} (本轮无派发)")
            self.schedule_status_text.see(tk.END)
            for _ in range(10):
                if self.stop_event.is_set(): break
                time.sleep(0.2)
        self.schedule_status_text.insert(tk.END, "调度已停止。\n")


    def _save_setting(self, key, value):
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "settings" not in config:
                config["settings"] = {}
            config["settings"][key] = value
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"[配置错误] 加载失败: {repr(e)}")
            import traceback
            print(traceback.format_exc())

    def _add_tooltip(self, widget, text):
        try:
            widget.tooltip_text = text
            widget.bind("<Enter>", lambda e: self._show_tooltip(e.widget))
            widget.bind("<Leave>", lambda e: self._hide_tooltip())
        except Exception as e:
            print(f"[配置错误] 加载失败: {repr(e)}")
            import traceback
            print(traceback.format_exc())

    def _show_tooltip(self, widget):
        try:
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            self._tooltip = tk.Toplevel(widget)
            self._tooltip.wm_overrideredirect(True)
            self._tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(self._tooltip, text=widget.tooltip_text, background="#ffffcc", relief="solid", borderwidth=1, font=("Microsoft YaHei", 9))
            label.pack()
        except Exception as e:
            print(f"[配置错误] 加载失败: {repr(e)}")
            import traceback
            print(traceback.format_exc())

    def _hide_tooltip(self):
        try:
            if hasattr(self, "_tooltip"):
                self._tooltip.destroy()
        except Exception as e:
            print(f"[配置错误] 加载失败: {repr(e)}")
            import traceback
            print(traceback.format_exc())

    def _get_config(self, key, default):
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            val = config.get("settings", {}).get(key)
            if val is not None:
                return val
            if hasattr(self, '_workflow_config') and self._workflow_config:
                for section in self._workflow_config.values():
                    if isinstance(section, dict) and key in section:
                        return section[key]
            return default
        except:
            return default

    def _get_system_state(self) -> dict:
        """返回当前系统状态,供移动控制台展示"""
        return {
            "windows": [{"name": n, "state": s} for n, s in self.window_status.items()],
            "pool_size": len(self.speech_pool),
            "current_task": self.task_desc_var.get() if hasattr(self, 'task_desc_var') else "无",
        }

    def _execute_remote_command(self, cmd_str: str) -> dict:
        """执行来自移动端的命令(JSON格式)"""
        try:
            if cmd_str.strip() in ('pause','resume','skip'):
                return self._quick_cmd(cmd_str.strip())
            if cmd_str.strip().startswith('{'):
                payload = json.loads(cmd_str.strip())
                action = payload.get("action", "")
                
                if action == "schedule_start":
                    windows = payload.get("windows", [])
                    topic = payload.get("topic", "")
                    # 先设置窗口勾选状态
                    if windows and hasattr(self, 'schedule_vars'):
                        for name in self.schedule_vars:
                            self.schedule_vars[name].set(name in windows)
                    # 设置话题
                    if topic and hasattr(self, 'schedule_topic_var'):
                        self.schedule_topic_var.set(topic)
                        if hasattr(self, 'schedule_topic_entry'):
                            self.schedule_topic_entry.delete("1.0", tk.END)
                            self.schedule_topic_entry.insert("1.0", topic)
                    # 启动调度
                    if True:
                        pass
                        self.root.after(0, self._start_schedule)
                    return {"success": True, "data": "调度已启动"}
                
                elif action == "schedule_stop":
                    self.root.after(0, self._stop_task)
                    return {"success": True, "data": "调度已停止"}
                
                elif action == "schedule_status":
                    return self._get_system_state()
                
                elif action == "send_message":
                    if getattr(self, "_sending", False): return {"success": False, "error": "正在发送中"}
                    self._sending = True
                    target = payload.get("target", "")
                    message = payload.get("message", "")
                    print(f"[移动端] 收到发送指令: target={target}, message={message[:50]}")
                    
                    if target and message:
                        self.log(f"[移动端] 执行发送: {target} | {message[:50]}")
                        import threading
                        def _send():
                            self._do_send_and_capture(target, message, show_in_chat=False)
                            self._sending = False
                        threading.Thread(target=_send, daemon=True).start()

                        return {"success": True, "data": f"消息已发送至 {target}"}
                    return {"success": False, "error": "缺少target或message"}
                
                elif action == "task_start":
                    if hasattr(self, 'task_target_var'):
                        self.task_target_var.set(payload.get("target", ""))
                    if hasattr(self, 'task_desc_var'):
                        self.task_desc_var.set(payload.get("description", ""))
                    if hasattr(self, 'task_rounds_var'):
                        self.task_rounds_var.set(int(payload.get("rounds", 3)))
                    self.root.after(0, self._start_auto_task)
                    return {"success": True, "data": "自动任务已启动"}
                
                elif action == "apps_list":
                    apps = []
                    if hasattr(self, 'app_paths'):
                        for name in self.app_paths:
                            apps.append({"name": name, "icon": "📦"})
                    return {"success": True, "apps": apps}
                
                elif action == "app_launch":
                    name = payload.get("name", "")
                    if name and hasattr(self, 'app_paths') and name in self.app_paths:
                        import os
                        #os.startfile(self.app_paths[name])
                        return {"success": True, "data": f"已启动 {name}"}
                    return {"success": False, "error": f"应用 {name} 不存在"}
                
                elif action == "search_execute":
                    keyword = payload.get("keyword", "")
                    engine = payload.get("engine", "google")
                    if keyword:
                        if hasattr(self, 'search_keyword_var'):
                            self.search_keyword_var.set(keyword)
                        if hasattr(self, 'search_engine_var'):
                            self.search_engine_var.set(engine.title())
                        self.root.after(0, self._execute_search)
                        return {"success": True, "data": f"搜索 {keyword} 已提交"}
                    return {"success": False, "error": "缺少关键词"}
                
                elif action == "window_toggle":
                    window = payload.get("window", "")
                    enable = payload.get("enable", True)
                    if window and hasattr(self, 'schedule_vars') and window in self.schedule_vars:
                        self.schedule_vars[window].set(enable)
                        return {"success": True, "data": f"{window} 已{'选中' if enable else '取消'}"}
                    return {"success": False, "error": f"窗口 {window} 不存在"}
                
        except (json.JSONDecodeError, KeyError):
            pass
        
        # 兼容v1.0纯文本指令
        if cmd_str.startswith("[WORKER:") or cmd_str.startswith("[@send_to:"):
            if hasattr(self, 'bridge'):
                return self.bridge._call_worker(cmd_str.lstrip('[').rstrip(']'))
            else:
                return {"success": False, "error": "桥接模块未初始化"}
        
        if cmd_str.strip() in ('pause','resume','skip'):
            return self._quick_cmd(cmd_str.strip())
        return {"success": False, "error": f"未知指令: {cmd_str}"}

    def _worker_result_handler(self, cmd, result):
        if result.get("success"):
            msg = f"✅ 机器人执行成功\n指令: {cmd}\n结果: {result.get('data', '')}"
        else:
            msg = f"❌ 机器人执行失败\n指令: {cmd}\n错误: {result.get('error', '')}"
        if getattr(self, '_worker_to_schedule', False):
            self.schedule_status_text.insert(tk.END, msg + "\n\n")
            self.schedule_status_text.see(tk.END)
        else:
            self._add_to_chat("机器人", msg)
    def _quick_cmd(self,a):
        if a=='pause':
            self.stop_event.set()
            for n in self.window_status:self.window_status[n]='idle'
            return {'success':True,'data':'paused'}
        if a=='resume':
            self.stop_event.clear()
            return {'success':True,'data':'resumed'}
        if a=='skip':
            self.stop_event.set()
            time.sleep(0.3)
            self.stop_event.clear()
            for n in self.window_status:self.window_status[n]='idle'
            return {'success':True,'data':'skipped'}
        return {'success':False,'error':'unknown'}

    def _force_send_to(self, target_name, content):
        pass

    def _recheck_pending(self, name):
        cfg = self.window_configs.get(name, {})
        kw = cfg.get("keyword", name)
        
        hwnd = None
        def _find(h, _):
            nonlocal hwnd
            try:
                if kw and kw in win32gui.GetWindowText(h):
                    hwnd = h
            except:
                pass
        win32gui.EnumWindows(_find, None)
        
        if not hwnd:
            self.log(f"  [{name}] 重抓失败：未找到窗口")
            return ""
        
        if not win32gui.IsWindow(hwnd):
            self.log(f"  [{name}] 重抓失败：窗口已关闭")
            return ""
        
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.3)
        
        try:
            if name in ("qianwen", "zhipu"):
                return self._click_copy_grab(hwnd, name, cfg)
            elif name == "coze":
                return ""
            elif name == "deepseek":
                content = self._simple_select(hwnd, cfg)
                if content and content.strip():
                    clean = self._extract_reply(content, name)
                    return (clean or content).strip()
                return ""
            else:
                return ""
        except Exception as e:
            self.log(f"  [{name}] 重抓异常: {e}")
            return "" 

    def _resolve_route_name(self, route_target):
        name_map = {
            "DeepSeek": "deepseek", 
            "千问": "qianwen", 
            "扣子": "coze", 
            "Qoder CN": "qianwen2", 
            "智谱": "zhipu", 
            "千问ID": "qianwen2",
            "deepseek": "deepseek", 
            "qianwen": "qianwen", 
            "coze": "coze", 
            "qianwen2": "qianwen2", 
            "zhipu": "zhipu"
        }
        resolved = name_map.get(route_target, route_target)
        if resolved not in self.window_configs and route_target in self.window_configs:
            return route_target
        return resolved

    def _start_auto_task(self):
        target = self.task_target_var.get()
        desc = self.task_desc_var.get()
        rounds = self.task_rounds_var.get()
        self.task_log_text.insert(tk.END, f"任务启动: {target}, {rounds}轮\n")
        self.task_log_text.see(tk.END)
        self.stop_event.clear()
        threading.Thread(target=self._run_auto_task, args=(target, desc, rounds), daemon=True).start()

    def _run_auto_task(self, name, desc, rounds):
        for i in range(rounds):
            if self.stop_event.is_set(): break
            self.task_log_text.insert(tk.END, f"--- 第 {i+1} 轮 ---\n")
            reply = self._do_send_and_capture(name, desc)
            if reply: self.task_log_text.insert(tk.END, f"  回复长度: {len(reply)}\n")
            self.task_log_text.see(tk.END)
            time.sleep(2)

    def _file_bridge(self, name, msg, skip_write=False):
        cfg = self.window_configs.get(name, {})
        TASK_FILE = cfg.get("task_file", r"D:\智联枢纽\qianwen2_in.txt")
        REPLY_FILE = cfg.get("reply_file", r"D:\智联枢纽\qianwen2_out.txt")

        if not skip_write:
            try:
                if os.path.exists(REPLY_FILE):
                    os.remove(REPLY_FILE)
            except Exception:
                pass
            msg_with_hint = msg + "\n\n（请完成回复后，将回复内容写入 " + REPLY_FILE + "，覆盖写入，不要追加）"
            try:
                with open(TASK_FILE, "w", encoding="utf-8") as f:
                    f.write(msg_with_hint)
            except Exception as e:
                self.log(f"  [{name}] 写入任务文件失败: {e}")
                return ""

        try:
            baseline_mtime = os.path.getmtime(REPLY_FILE) if os.path.exists(REPLY_FILE) else 0
        except Exception:
            baseline_mtime = 0
        for i in range(300):
            if self.stop_event.is_set():
                return ""
            if self.stop_event.is_set():
                return ""
            time.sleep(1)
            try:
                if not os.path.exists(REPLY_FILE):
                    continue
                current_mtime = os.path.getmtime(REPLY_FILE)
                with open(REPLY_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.strip() and current_mtime > baseline_mtime:
                    self.log(f"  [{name}] 收到回复: {len(content)} 字符 (mtime 变化)")
                    return content.strip()
            except Exception:
                continue
        self.log(f"  [{name}] 5 分钟内没收到回复")
        return ""

    def _scan_desktop(self):
        self.app_listbox.delete(0, tk.END)
        self.app_paths.clear()
        count = 0
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
        public = os.path.join(os.environ["PUBLIC"], "Desktop")
        for p in [desktop, public]:
            if not os.path.exists(p): continue
            for item in os.listdir(p):
                fp = os.path.join(p, item)
                if item.startswith('.'): continue
                if os.path.isdir(fp):
                    self.app_listbox.insert(tk.END, f"[文件夹] {item}")
                    self.app_paths[f"[文件夹] {item}"] = fp
                    count += 1
                elif any(item.lower().endswith(e) for e in ['.lnk','.exe','.bat','.cmd','.msi','.url','.jar']):
                    name = os.path.splitext(item)[0]
                    self.app_listbox.insert(tk.END, name)
                    self.app_paths[name] = fp
                    count += 1
        recycle_path = "::{645FF040-5081-101B-9F08-00AA002F954E}"
        self.app_listbox.insert(tk.END, "回收站")
        self.app_paths["回收站"] = recycle_path
        count += 1
        computer_path = "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}"
        self.app_listbox.insert(tk.END, "此电脑")
        self.app_paths["此电脑"] = computer_path
        count += 1
        self.log(f"扫描完成，找到 {count} 个桌面图标。")

    def _launch_selected(self):
        sel = self.app_listbox.curselection()
        if not sel: return
        name = self.app_listbox.get(sel[0])
        path = self.app_paths.get(name)
        if path:
            try:
                os.startfile(path)
                self.log(f"已启动: {name}")
            except Exception as e:
                self.log(f"启动失败: {e}")

    def _add_shortcut(self):
        path = filedialog.askopenfilename()
        if path:
            name = os.path.basename(path)
            self.app_listbox.insert(tk.END, name)
            self.app_paths[name] = path

    def _execute_search(self):
        keyword = self.search_keyword_var.get().strip()
        if not keyword: return
        engine = self.search_engine_var.get()
        url = self.search_engines.get(engine) + keyword.replace(" ", "+")
        webbrowser.open(url)
        self.log(f"已打开搜索: {keyword}")

    def run(self):
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        import ctypes
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _restart_app(self, from_worker=False):
        """
        重启应用。
        如果 from_worker 为 True，则无条件执行重启。
        否则，仅当从界面按钮点击时执行。
        """
        import sys, os
        if from_worker:
            print("机器人指令触发重启...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            # 这是从界面按钮触发的，正常执行
            self._on_close()
            os.execv(sys.executable, [sys.executable] + sys.argv)

    def _build_help_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        text = scrolledtext.ScrolledText(frame, height=20)
        text.pack(fill=tk.BOTH, expand=True)
        help_text = """【Nexus 桌面助手 完整使用手册】

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📌 一、项目简介
Nexus 桌面助手是一款多窗口 AI 协作工具，可以同时调度多个 AI 窗口
进行对话、执行任务、互相传递信息，实现自动化工作流。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 💬 二、对话标签页

【功能】与选定的 AI 窗口单独对话。

【使用方法】
1. 在顶部单选框中选择目标窗口（如 DeepSeek、千问等）
2. 在输入框中输入内容
3. 按回车键或点击"发送"按钮
4. AI 的回复会显示在对话区

【按钮说明】
- 📤 发送：将消息发送给选定的 AI 窗口
- ⏹️ 停止：停止当前正在执行的任务
- 🗑️ 清空日志：清空上方运行日志
- 🧹 清空对话：清空对话显示区
- 📋 复制最新回复：一键复制 AI 最新回复内容
- 🔄 重启应用：重新启动整个程序

【机器人指令】
在对话页输入 @ 加上 Python 代码，机器人会自动执行：
  例：@ print("hello")
  例：@ import os; print(os.listdir("."))
  例：@ f=open("D:/test.txt","w"); f.write("hello"); f.close()
  发送任务停止指令: STOP_SCHEDULE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🎯 三、定位校准标签页

【功能】校准每个 AI 窗口的输入框位置和内容读取位置，
这是所有自动化操作的基础，必须正确校准才能使用。

【校准步骤】
1. 打开对应的 AI 窗口（如 DeepSeek 网页）
2. 点击"🎯 校准"按钮，在 5 秒内将鼠标放在输入框上
3. 点击"📖 校准读取区"按钮，在 5 秒内将鼠标放在对话内容区
4. 点击"📋 校准复制键"按钮，在 5 秒内将鼠标放在复制按钮上
5. 点击"🔍 测试捕获"验证校准是否成功

【按钮说明】
- 🎯 校准：捕获 AI 窗口输入框的坐标
- 📖 校准读取区：捕获 AI 窗口内容显示区的坐标
- 📋 校准复制键：捕获 AI 窗口复制按钮的坐标
- 🔍 测试捕获：测试能否正确抓取 AI 窗口内容
- 🔎 找复制键：测试能否找到复制键位置
- 🖱️ 点复制键：测试点击复制键是否生效
- ➕ 添加窗口：添加新的 AI 窗口
- 🗑️ 删除窗口：删除已有的窗口

【窗口参数说明】
添加窗口时需要填写：
- 窗口名称：任意名称，用于显示
- 窗口类型：截屏识别（通过截图找复制键）或文件桥接（通过文件读写）
- 关键词：窗口标题中必须包含的文字，用于定位窗口

【监控参数设置】
- 稳定等待时间：截图监控稳定后等待秒数（建议2-5秒）
- 超时跳过轮数：超时无回复时跳过的轮数（建议5-20轮）
- 窗口阈值：复制键模板匹配精确度（建议0.45-0.60）
- 滚动次数：每次截图后的滚轮滚动次数（建议5-15次）
- 滚动量：每次滚动的像素量（建议300-800）
- 全选间隔：全选监控的检测间隔（建议1-5秒）
- 截图间隔：截图监控的检测间隔（建议1-5秒）
- 点击次数上限：复制键最多点击次数（建议1-3次）
- 截图后等待：稳定截图后等待时间（建议1-5秒）
- 全选稳定次数：全选内容不变的次数（建议2-3次）
- 截图稳定次数：截图内容不变的次数（建议2-3次）
- 模板窗口：选择要配置模板的窗口
- 模板路径：复制键模板图片的文件路径

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🔄 四、智能调度标签页

【功能】让多个 AI 窗口自动轮流讨论一个话题。

【使用方法】
1. 勾选要参与讨论的窗口
2. 在输入框中输入初始话题
3. 按回车键或点击"启动智能调度"
4. 系统会自动将话题发给第一个窗口，等待回复
5. 抓取回复后发给下一个窗口，以此类推

【按钮说明】
- 🚀 启动智能调度：开始多窗口自动讨论
- ⏹️ 停止：停止调度
- 启用调度：勾选后调度功能可用，取消后禁用

【注意事项】
- 调度前请确保所有窗口都已校准
- 调度过程中不要手动操作 AI 窗口
- 如需停止，点击"停止"按钮或

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ⚡ 五、自动任务标签页

【功能】对单个 AI 窗口重复发送同一个任务。

【使用方法】
1. 选择目标窗口
2. 输入任务描述
3. 设置运行轮次（1-10轮）
4. 点击"启动自动化任务"

【按钮说明】
- 🚀 启动自动化任务：开始自动任务
- ⏹️ 停止：停止任务

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📱 六、应用启动标签页

【功能】扫描桌面快捷方式并一键启动应用。

【使用方法】
1. 点击"扫描桌面图标"
2. 在列表中选择要启动的应用
3. 点击"启动选中应用"

【按钮说明】
- 🔍 扫描桌面图标：扫描桌面上的快捷方式和程序
- 🚀 启动选中应用：启动列表中选择的应用
- 📂 手动添加：手动添加程序路径

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🔍 七、搜索抓取标签页

【功能】自动打开浏览器搜索关键词，并抓取搜索结果。

【使用方法】
1. 选择搜索引擎（Bing/Google/百度）
2. 输入搜索关键词
3. 点击"自动搜索并整理"

【按钮说明】
- 🔍 自动搜索并整理：打开浏览器搜索并抓取内容

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ❓ 八、帮助与反馈（本页面）

【功能】提供使用帮助和反馈渠道。

【反馈方式】
如有任何问题、建议或 bug 报告，请发送邮件至：
 1322820339@qq.com

我们会在收到邮件后尽快回复处理。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🚀 九、快速上手流程

1. 打开 AI 窗口（DeepSeek、千问等）
2. 在"定位校准"中添加窗口并校准位置
3. 在"对话"中测试单独对话
4. 在"智能调度"中启动多窗口互动
5. 在"参数设置"中根据效果微调参数

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ⚠️ 十、常见问题

Q：窗口切换不了？
A：检查窗口关键词是否匹配，重新校准坐标。

Q：抓取不到回复？
A：检查读取区坐标是否对准对话内容区。

Q：调度日志疯狂翻滚？
A：点击停止按钮，检查窗口配置是否完整。

Q：移动端连接不上？
A：确保手机和电脑在同一 WiFi，检查防火墙是否开放 5000 端口。
"""
        text.insert("1.0", help_text)
        text.config(state=tk.DISABLED)

    def _on_close(self):

        self._monitor_running = False
        self.stop_event.set()
        self.root.destroy()

if __name__ == "__main__":
    import traceback
    try:
        app = NexusTool()
        app.run()
    except Exception as e:
        with open("nexus_error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())