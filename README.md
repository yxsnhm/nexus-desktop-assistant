# Nexus 桌面助手

多窗口 AI 协作与自动化工具。支持同时调度多个 AI 窗口进行对话、执行任务、互相传递信息，并可通过移动端远程控制。

## 主要功能

- **多窗口调度**：支持 DeepSeek、千问、智谱、扣子等多个 AI 窗口自由组合
- **智能调度**：勾选参与窗口，输入话题，自动轮流讨论
- **@窗口指定**：输入 `@千问 消息` 可将内容定向发送到指定窗口
- **机器人指令**：内置 Python 执行引擎，支持 `@ print("hello")` 等指令
- **截图/全选监控**：自动检测 AI 回复完成，抓取内容
- **移动控制台**：手机浏览器访问 `http://电脑IP:5000` 远程操控
- **应用启动器**：扫描桌面快捷方式，一键启动

## 快速开始

1. 下载 `Nexus桌面助手.exe` 和 `NexusRobot.exe`，放在同一文件夹
2. 将 `nexus_config.json.example` 复制为 `nexus_config.json`
3. 编辑 `nexus_config.json`，填入你的 AI 窗口名称和标题关键词
4. 双击 `Nexus桌面助手.exe` 启动
5. 在“定位校准”标签页校准各窗口的输入框和读取区坐标

## 配置文件说明

编辑 `nexus_config.json`：

```json
{
  "windows": {
    "千问": { "keyword": "千问", "type": "", "x": 0, "y": 0 }
  },
  "coords": {
    "千问": { "x": 0, "y": 0, "rx": 0, "ry": 0 }
  },
  "settings": {
    "screenshot_interval": 3,
    "stable_wait": 3
  }
}

打包说明
如需自行打包：

cmd
cd D:\智联枢纽
pyinstaller --onefile --windowed --name="Nexus桌面助手" --icon=nexus.ico --add-data "nexus_bridge.py;." --add-data "nexus_worker.py;." --add-data "nexus_config.json;." nexus_tool.py
pyinstaller --onefile --windowed --name="NexusRobot" --icon=nexus.ico rw.py
模块集成
桌面助手可作为模块集成到智联枢纽主程序：

python
from nexus_tool import NexusTool
app = NexusTool.start_as_module(callback=my_callback)

联系方式：发送邮件至 1322820339@qq.com
如有问题或建议，欢迎提交 Issue
app.log("来自主程序的消息")
## 注意事项
- 请勿将 `nexus_config.json`、`users.db`、`.env` 等包含敏感信息的文件上传到公开仓库。
- 建议在项目根目录创建 `.gitignore` 文件，内容如下：
nexus_config.json
users.db
.env
pycache/
build/
dist/
*.spec

text
