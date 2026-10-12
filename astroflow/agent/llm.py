"""LLM access through any OpenAI-compatible endpoint (DeepSeek, OpenAI, local Ollama / LM Studio / vLLM ...).

The provider comes from the user settings (astroflow/settings.py); its key from the OS credential store (or the
project .env for DeepSeek, as before) and is never logged.
planner: text + tool calls   - decides what to run and which parameters to use
vision:  text + images       - the planner's eyes: judges previews against references (optional per provider)
"""
import base64
import io
import json
import re
import threading

import openai
from openai import OpenAI

from .. import jobctx, settings

# Worth another try after a pause: rate limits, an overloaded server, the network. Anything else (bad request, wrong
# key or model name) fails the same way again.
TRANSIENT = (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError)


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, provider=None):
        self.provider = provider or settings.get().provider()
        key = settings.get_api_key(self.provider.name)
        if not key:
            if self.provider.needs_key:
                raise LLMError(f"No API key for {self.provider.name}: add it in Settings (kept in the system "
                               "credential store) or put api_key=... in the project .env")
            key = "not-needed"                                  # local servers ignore it but the SDK wants one
        self.client = OpenAI(api_key=key, base_url=self.provider.base_url)
        self.planner = self.provider.planner_model
        self.vision = self.provider.vision_model
        self.usage = {"prompt": 0, "completion": 0, "calls": 0}

    def _call(self, **kw):
        for i in range(4):
            try:
                r = self._request(kw)
            except TRANSIENT:
                if i == 3:
                    raise
                jobctx.sleep(5 * (i + 1))
                continue
            if r.usage:
                self.usage["prompt"] += r.usage.prompt_tokens or 0
                self.usage["completion"] += r.usage.completion_tokens or 0
            self.usage["calls"] += 1
            return r

    def _request(self, kw):
        """One request. Reasoning models can take minutes to answer: when the job is cancelled meanwhile, stop waiting
        (the request finishes unseen in the background)."""
        box = {}
        done = threading.Event()

        def run():
            try:
                box["response"] = self.client.chat.completions.create(**kw)
            except Exception as e:
                box["error"] = e
            finally:
                done.set()

        threading.Thread(target=run, name="llm-request", daemon=True).start()
        while not done.wait(0.5):
            jobctx.check_cancelled()
        if "error" in box:
            raise box["error"]
        return box["response"]

    def chat(self, messages, tools=None, max_tokens=16000):
        kw = {"model": self.planner, "messages": messages, "max_tokens": max_tokens}
        if tools and self.provider.tools:
            kw["tools"] = tools
        try:
            return self._call(**kw).choices[0].message
        except Exception as e:
            # thinking models differ on whether earlier reasoning_content may be sent back; drop it and retry
            if "reasoning" not in str(e).lower():
                raise
            kw["messages"] = [{k: v for k, v in m.items() if k != "reasoning_content"} for m in messages]
            return self._call(**kw).choices[0].message

    def ping(self):
        """Smallest possible request: raises if the endpoint, key or model name is wrong."""
        r = self._call(model=self.planner, messages=[{"role": "user", "content": "Reply with OK."}], max_tokens=50)
        return (r.choices[0].message.content or "").strip()

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
        if not self.vision:
            raise LLMError(f"{self.provider.name} has no vision model configured: judge from the numbers "
                           "(metrics, compare_with_references) instead")
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
