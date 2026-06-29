import io
import sys
import traceback

MAX_PATCH_LINE_LEN = 5000

def writefile(filepath, content):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return "file written"

def patch(filepath, linenum, newline):
    if len(newline) > MAX_PATCH_LINE_LEN:
        return f"error: new line too long (max {MAX_PATCH_LINE_LEN} chars)"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if linenum < 1 or linenum > len(lines):
            return f"error: line {linenum} out of range"
        old_line = lines[linenum - 1]
        indent = old_line[:len(old_line) - len(old_line.lstrip())]
        lines[linenum - 1] = indent + newline.lstrip() + "\n"
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return f"patched line {linenum}"
    except Exception as e:
        return f"error: {e}"

def parse_code(raw_code):
    """从任意混乱输入中提取第一个有效Python代码块"""
    if not isinstance(raw_code, str):
        return raw_code
    # 1. 强行清除所有可能的代码块标记
    cleaned = raw_code.replace('```python', '').replace('```', '')
    # 2. 找第一个 '@' 并截取其后内容
    if '@' in cleaned:
        cleaned = cleaned.split('@', 1)[1]
    # 3. 只取第一行作为最终执行代码
    lines = cleaned.strip().split('\n')
    return lines[0].strip() if lines else ''

def execute(code, extra_globals=None):
    code = parse_code(code)
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        g = {"__builtins__": __builtins__, "patch": patch, "writefile": writefile, "MAX_PATCH_LINE_LEN": MAX_PATCH_LINE_LEN}; g.update(extra_globals or {}); import __main__; g.setdefault("app", getattr(__main__, "app", None)); exec(code, g)
        out = sys.stdout.getvalue()
        return {"success": True, "data": out if out else "ok"}
    except SystemExit:
        return {"success": False, "error": "代码中调用了 exit()，已拦截"}
    except Exception:
        return {"success": False, "error": traceback.format_exc()}
    finally:
        sys.stdout = old