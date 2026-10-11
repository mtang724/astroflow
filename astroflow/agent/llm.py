"""DeepSeek access (OpenAI-compatible API). The key is read from the project .env (api_key=...) and never logged.

planner: deepseek-v4-pro (text, tool calls)  - decides what to run and which parameters to use
vision:  deepseek-flash (text + images)       - the planner's eyes: judges previews against references
"""
import base64
import io
import json
import re
import time

from openai import OpenAI

from .. import config


class LLM:
    def __init__(self, planner=None, vision=None):
        key = config.env("api_key") or config.env("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("No DeepSeek key: put api_key=... in .env at the project root")
        self.client = OpenAI(api_key=key, base_url=config.DEEPSEEK_BASE_URL)
        self.planner = planner or config.DEEPSEEK_PLANNER_MODEL
        self.vision = vision or config.DEEPSEEK_VISION_MODEL
        self.usage = {"prompt": 0, "completion": 0, "calls": 0}

    def _call(self, **kw):
        for i in range(4):
            try:
                r = self.client.chat.completions.create(**kw)
                if r.usage:
                    self.usage["prompt"] += r.usage.prompt_tokens or 0
                    self.usage["completion"] += r.usage.completion_tokens or 0
                self.usage["calls"] += 1
                return r
            except Exception:   # rate limits / transient network errors
                if i == 3:
                    raise
                time.sleep(5 * (i + 1))

    def chat(self, messages, tools=None, max_tokens=16000):
        kw = {"model": self.planner, "messages": messages, "max_tokens": max_tokens}
        if tools:
            kw["tools"] = tools
        try:
            return self._call(**kw).choices[0].message
        except Exception as e:
            # thinking models differ on whether earlier reasoning_content may be sent back; drop it and retry
            if "reasoning" not in str(e).lower():
                raise
            kw["messages"] = [{k: v for k, v in m.items() if k != "reasoning_content"} for m in messages]
            return self._call(**kw).choices[0].message

    @staticmethod
    def _img(path, max_side=1600):
        from PIL import Image
        im = Image.open(path).convert("RGB")
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    def look(self, images, question, system=None, max_tokens=8000, want_json=False):
        """images: list of (label, path). Returns text (or parsed JSON when want_json and it parses)."""
        content = [{"type": "text", "text": question}]
        for label, path in images:
            content.append({"type": "text", "text": f"[{label}]"})
            content.append({"type": "image_url", "image_url": {"url": self._img(path)}})
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": content})
        text = self._call(model=self.vision, messages=msgs, max_tokens=max_tokens).choices[0].message.content or ""
        if want_json:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return text
