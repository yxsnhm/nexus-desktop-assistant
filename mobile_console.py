"""
mobile_console.py - 智联枢纽移动端控制台（精简版）
移除Token认证，保留全部功能面板
"""
import os, time, queue, string, random, logging, threading
from collections import deque
from typing import Callable, Optional, Dict, Any
from flask import Flask, request, jsonify
try:
    from flask_socketio import SocketIO, emit
except ImportError as e:
    import sys
    print(f"[移动端] 依赖不可用: {e}", file=sys.stderr)
    SocketIO = None
    emit = None

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

logger = logging.getLogger("MobileConsole")

CONSOLE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>智联枢纽·移动控制台</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js?v=2"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e0e0e0;font-size:14px}
.nav{display:flex;background:#1a1a1a;border-bottom:1px solid #333;overflow-x:auto}
.nav-item{flex:0 0 auto;padding:12px 16px;font-size:13px;color:#888;cursor:pointer;border-bottom:2px solid transparent}
.nav-item.active{color:#4fc3f7;border-bottom-color:#4fc3f7}
.panel{display:none;padding:12px}
.panel.active{display:block}
.card{background:#1a1a1a;border-radius:8px;padding:12px;margin-bottom:10px;border:1px solid #333}
h3{color:#4fc3f7;margin-bottom:8px}
.btn-row{display:flex;gap:8px;flex-wrap:wrap}
button{flex:1;padding:10px;border:none;border-radius:6px;font-size:13px;font-weight:bold;cursor:pointer;min-width:70px}
.btn-primary{background:#4fc3f7;color:#000}
.btn-danger{background:#f44336;color:#fff}
.btn-success{background:#4caf50;color:#fff}
.btn-warn{background:#ff9800;color:#000}
input,select,textarea{width:100%;padding:10px;border-radius:6px;border:1px solid #444;background:#222;color:#fff;font-size:13px;margin-bottom:8px}
textarea{resize:vertical;min-height:60px}
label{font-size:12px;color:#aaa;display:block;margin-bottom:4px}
.status-item{background:#222;padding:8px;border-radius:4px;font-size:12px;margin-bottom:4px}
.log-box{height:200px;overflow-y:auto;background:#111;border-radius:6px;padding:8px;font-family:monospace;font-size:11px;line-height:1.6}
.log-entry{border-bottom:1px solid #1a1a1a;padding:2px 0}
.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:10px 20px;border-radius:6px;font-size:13px;z-index:1000;display:none}
.toast-ok{background:#4caf50;color:#fff}.toast-err{background:#f44336;color:#fff}
.win-item{display:flex;align-items:center;padding:8px;background:#222;border-radius:4px;margin-bottom:4px;font-size:12px}
.win-item input[type=checkbox]{width:auto;margin-right:8px}
</style></head><body>
<div id="toast" class="toast"></div>
<div id="app">
<div class="nav">
<div class="nav-item active" data-panel="status">📊 状态</div>
<div class="nav-item" data-panel="schedule">🧠 调度</div>
<div class="nav-item" data-panel="message">💬 对话</div>
<div class="nav-item" data-panel="task">🤖 任务</div>
<div class="nav-item" data-panel="logs">📋 日志</div>
</div>
<div class="panel active" id="panel-status">
<div class="card"><h3>📊 系统状态</h3><div id="status-panel"></div></div>
<div class="card"><h3>🎮 快捷干预</h3><div class="btn-row">
<button class="btn-warn" onclick="sendCmd('pause')">⏸ 暂停</button>
<button class="btn-success" onclick="sendCmd('resume')">▶ 恢复</button>
<button class="btn-danger" onclick="sendCmd('skip')">⏭ 跳过</button>
</div></div>
</div>
<div class="panel" id="panel-schedule">
<div class="card"><h3>🧠 智能调度</h3>
<label>参与窗口</label>
<div id="schedule-win-list"></div>
<label style="margin-top:8px">话题</label>
<textarea id="schedule-topic" placeholder="输入话题或留空"></textarea>
<div class="btn-row" style="margin-top:8px">
<button class="btn-success" onclick="scheduleStart()">▶ 启动</button>
<button class="btn-danger" onclick="scheduleStop()">⏹ 停止</button>
</div>
<div id="schedule-status" style="margin-top:8px;font-size:12px;color:#888"></div>
</div>
</div>
<div class="panel" id="panel-message">
<div class="card"><h3>💬 发送消息</h3>
<label>目标窗口</label>
<select id="msg-target"></select>
<label>消息内容</label>
<textarea id="msg-content" placeholder="输入要发送的消息"></textarea>
<button class="btn-primary" onclick="sendMessage()">发送</button>
</div>
</div>
<div class="panel" id="panel-task">
<div class="card"><h3>🤖 自动任务</h3>
<label>目标窗口</label>
<select id="task-target"></select>
<label>任务描述</label>
<textarea id="task-desc" placeholder="描述任务"></textarea>
<label>轮次</label>
<input type="number" id="task-rounds" value="3" min="1" max="50">
<button class="btn-primary" onclick="startTask()">启动</button>
</div>
</div>
<div class="panel" id="panel-logs">
<div class="card"><h3>📋 实时日志</h3><div id="log-box" class="log-box"></div></div>
</div>
</div>
<script>
let socket=null,cmdLock=false,token='';
function showToast(msg,ok){const t=document.getElementById('toast');t.textContent=msg;t.className='toast '+(ok?'toast-ok':'toast-err');t.style.display='block';setTimeout(()=>t.style.display='none',2500)}
function apiPost(path,body){return fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json())}
function apiGet(path){return fetch(path).then(r=>r.json())}
document.querySelectorAll('.nav-item').forEach(item=>{item.onclick=function(){document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));this.classList.add('active');document.getElementById('panel-'+this.dataset.panel).classList.add('active')}});
function connect(){
  socket=io({reconnection:true,reconnectionDelay:2000});
  socket.on('connect',()=>{});
  socket.on('state_update',(d)=>{renderStatus(d);updateWindowSelects(d)});
  socket.on('log_entry',(d)=>{appendLog(d)});
  socket.on('cmd_result',(d)=>{cmdLock=false;showToast(d.success?'✅ '+d.cmd:'❌ '+d.error,d.success)});
}
function renderStatus(d){const p=document.getElementById('status-panel');let h='';
  if(d.windows)d.windows.forEach(w=>{h+=`<div class="status-item">${w.name}: ${w.state}</div>`});
  if(d.current_task)h+=`<div class="status-item" style="color:#4fc3f7">任务: ${d.current_task}</div>`;
  if(d.pool_size!==undefined)h+=`<div class="status-item">发言池: ${d.pool_size}</div>`;
  p.innerHTML=h||'<div class="status-item">暂无数据</div>'}
function updateWindowSelects(d){if(!d||!d.windows)return;const wins=d.windows;
  ['msg-target','task-target'].forEach(id=>{const sel=document.getElementById(id);sel.innerHTML=wins.map(w=>`<option value="${w.name}">${w.name}</option>`).join('')});
  const wl=document.getElementById('schedule-win-list');const checked={};wl.querySelectorAll('input:checked').forEach(cb=>checked[cb.value]=true);
  wl.innerHTML=wins.map(w=>`<div class="win-item"><input type="checkbox" value="${w.name}" ${checked[w.name]?'checked':''}> ${w.name}</div>`).join('')}
function appendLog(d){const box=document.getElementById('log-box');const div=document.createElement('div');div.className='log-entry';div.textContent=`[${d.time}] ${d.msg}`;box.appendChild(div);if(box.children.length>200)box.removeChild(box.firstChild);box.scrollTop=box.scrollHeight}
function sendCmd(cmd){if(cmdLock)return;if(!confirm(`确认执行【${cmd}】？`))return;cmdLock=true;socket.emit('execute_command',{command:cmd})}
async function scheduleStart(){const wins=[...document.querySelectorAll('#schedule-win-list input:checked')].map(i=>i.value);const topic=document.getElementById('schedule-topic').value.trim();if(!wins.length){showToast('请选择窗口',false);return}try{const r=await apiPost('/api/schedule/start',{windows:wins,topic:topic});showToast(r.success?'已启动':r.error,r.success);if(r.success)document.getElementById('schedule-topic').value=''}catch(e){showToast('失败',false)}}
async function scheduleStop(){try{const r=await apiPost('/api/schedule/stop',{});showToast(r.success?'已停止':r.error,r.success)}catch(e){showToast('失败',false)}}
async function sendMessage(){const target=document.getElementById('msg-target').value;const content=document.getElementById('msg-content').value.trim();if(!target||!content){showToast('请选择窗口并输入消息',false);return}try{const r=await apiPost('/api/message/send',{target:target,message:content});document.getElementById('msg-content').value='';showToast(r.success?'已发送':r.error,r.success)}catch(e){showToast('失败',false)}}
async function startTask(){const target=document.getElementById('task-target').value;const desc=document.getElementById('task-desc').value.trim();const rounds=parseInt(document.getElementById('task-rounds').value)||3;if(!target||!desc){showToast('请填写完整',false);return}try{const r=await apiPost('/api/task/start',{target:target,description:desc,rounds:rounds});showToast(r.success?'已启动':r.error,r.success)}catch(e){showToast('失败',false)}}
connect();
</script>
</body></html>"""

class MobileConsole:
    LOG_BUFFER_SIZE = 200
    LOG_RATE_LIMIT = 5

    def __init__(self, state_provider, command_executor, log_stream, port=5000, host="0.0.0.0"):
        self._state_provider = state_provider
        self._command_executor = command_executor
        self._log_queue = log_stream
        self._host = host
        self._port = self._find_available_port(port)
        self._token = ""  # Token已废弃
        self._log_buffer = deque(maxlen=self.LOG_BUFFER_SIZE)
        self._last_log_push_time = 0.0
        self._server_thread = None
        self._running = False
        self._app = Flask(__name__)
        self._app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        self._app.config["SECRET_KEY"] = os.urandom(24).hex()
        if SocketIO is None:
            self._available = False
            return
        self._socketio = SocketIO(self._app, cors_allowed_origins="*")
        self._register_routes()
        self._register_routes()
        self._register_api_routes()
        self._register_socket_events()

    def _find_available_port(self, start, max_retry=3):
        import socket as sock
        for offset in range(max_retry):
            port = start + offset
            try:
                with sock.socket(sock.AF_INET, sock.SOCK_STREAM) as s:
                    s.settimeout(1)
                    s.bind((self._host, port))
                return port
            except OSError:
                pass
        return start

    def _register_routes(self):
        @self._app.route("/")
        def index():
            return CONSOLE_HTML
        # 桌面自动化 API 接口
        @self._app.route("/api/desktop", methods=["POST"])
        def desktop_automation():
            try:
                import json
                data = request.get_json(force=True)
                if not data:
                    return jsonify({"success": False, "error": "缺少请求数据"}), 400
                result = self._command_executor(json.dumps(data))
                return jsonify(result)
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500

    def _register_api_routes(self):
        def _exec(payload):
            import json as _json
            cmd_str = _json.dumps(payload, ensure_ascii=False)
            try:
                return self._command_executor(cmd_str)
            except Exception as e:
                return {"success": False, "error": str(e)}

        @self._app.route("/api/schedule/start", methods=["POST"])
        def schedule_start():
            data = request.get_json(silent=True) or {}
            return jsonify(_exec({"action":"schedule_start","windows":data.get("windows",[]),"topic":data.get("topic","")}))

        @self._app.route("/api/schedule/stop", methods=["POST"])
        def schedule_stop():
            return jsonify(_exec({"action":"schedule_stop"}))

        @self._app.route("/api/schedule/status", methods=["GET"])
        def schedule_status():
            return jsonify(_exec({"action":"schedule_status"}))

        @self._app.route("/api/message/send", methods=["POST"])
        def message_send():
            data = request.get_json(silent=True) or {}
            return jsonify(_exec({"action":"send_message","target":data.get("target",""),"message":data.get("message","")}))

        @self._app.route("/api/task/start", methods=["POST"])
        def task_start():
            data = request.get_json(silent=True) or {}
            return jsonify(_exec({"action":"task_start","target":data.get("target",""),"description":data.get("description",""),"rounds":data.get("rounds",3)}))

    def _register_socket_events(self):
        @self._socketio.on("connect")
        def on_connect(auth=None):
            for entry in self._log_buffer:
                emit("log_entry", entry)
            try:
                state = self._state_provider()
                emit("state_update", state)
            except Exception as e:
                logger.error(f"状态查询失败: {e}")

        @self._socketio.on("execute_command")
        def on_execute(data):
            print(f"[移动端快捷] 收到: {data}")
            cmd = (data or {}).get("command", "").strip()
            if not cmd:
                emit("cmd_result", {"success":False,"cmd":"","error":"空指令"})
                return
            try:
                result = self._command_executor(cmd)
                print(f"[移动端] 执行结果: {result}")
                emit("cmd_result", {"success":result.get("success",False),"cmd":cmd,"error":result.get("error","")})
            except Exception as e:
                import traceback
                print(f"[移动端] 执行异常: {traceback.format_exc()}")
                emit("cmd_result", {"success":False,"cmd":cmd,"error":str(e)})

    def _log_consumer_loop(self):
        while self._running:
            try:
                msg = self._log_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            now = time.time()
            elapsed = now - self._last_log_push_time
            min_interval = 1.0 / self.LOG_RATE_LIMIT
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            entry = {"time": time.strftime("%H:%M:%S"), "msg": str(msg)[:300]}
            self._log_buffer.append(entry)
            self._last_log_push_time = time.time()
            try:
                self._socketio.emit("log_entry", entry)
            except Exception:
                pass

    def _state_push_loop(self):
        while self._running:
            time.sleep(2)
            try:
                state = self._state_provider()
                self._socketio.emit("state_update", state)
            except Exception:
                pass

    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._log_consumer_loop, daemon=True).start()
        threading.Thread(target=self._state_push_loop, daemon=True).start()
        self._server_thread = threading.Thread(
            target=lambda: self._socketio.run(self._app, host=self._host, port=self._port, log_output=False, use_reloader=False),
            daemon=True
        )
        self._server_thread.start()
        self._print_access_info()

    def _print_access_info(self):
        url = f"http://localhost:{self._port}"
        print(f"\n  📱 移动控制台: {url}")
        if HAS_QRCODE:
            try:
                qr = qrcode.QRCode(box_size=10, border=2)
                qr.add_data(url)
                qr.print_ascii(invert=True)
            except Exception:
                pass

    def stop(self):
        self._running = False