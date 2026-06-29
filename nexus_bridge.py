import re
import logging

logger = logging.getLogger("NexusBridge")

RUN_PATTERN = re.compile(r'\[RUN:(.+?)\]', re.DOTALL)

class NexusBridge:
    def __init__(self, result_callback=None):
        self._callback = result_callback
        self._available = True

    @property
    def available(self):
        return self._available

    def _call_worker(self, code):
        from nexus_worker import execute
        try:
            return execute(code)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_ai_response(self, ai_text):
        if ai_text is None:
            return 0
        matches = RUN_PATTERN.findall(ai_text)
        for line in ai_text.split(chr(10)):
            at_pos = line.find(chr(64))
            if at_pos >= 0:
                code = line[at_pos+1:].strip()
                if code:
                    matches.append(code)
        if not matches:
            return 0
        executed = 0
        for code in matches:
            code = code.strip()
            result = self._call_worker(code)
            if self._callback:
                self._callback(code, result)
            if result.get("success"):
                executed += 1
        return executed
