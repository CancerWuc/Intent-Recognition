import requests
import json
from typing import Dict, Any, Optional, List
import logging


logger = logging.getLogger(__name__)


class LLMClient:
    """
    大模型客户端 - 用于调用SiliconFlow API
    """

    # def __init__(self, api_key: str, base_url: str = "https://api.siliconflow.cn/v1/chat/completions"):
    def __init__(self, api_key: str, base_url: str = "http://ai-api.citicsinfo.com/v1/chat/completions"):
        """
        初始化大模型客户端
        
        Args:
            api_key: API密钥
            base_url: API地址
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def chat_completion(self, messages: List[Dict],
                        model: str = "qwen3-32b",
                        # model: str = "Qwen/Qwen3-8B",
                        temperature: float = 0.7,
                        max_tokens: int = 1000) -> Optional[Dict]:
        """
        调用大模型API
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            响应结果或None
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API调用失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"API调用异常: {e}")
            return None
    
    def get_response_content(self, response: Dict) -> Optional[str]:
        """
        从API响应中提取内容
        
        Args:
            response: API响应
            
        Returns:
            响应内容或None
        """
        if response and "choices" in response:
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", None)
        return None
    
    def generate(self, prompt: str, system_prompt: str = None, model: str = None, max_tokens: int = 1000) -> Optional[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {}
        if model is not None:
            kwargs['model'] = model
        response = self.chat_completion(messages, max_tokens=max_tokens, **kwargs)
        return self.get_response_content(response)

    def generate_stream(self, prompt: str, system_prompt: str = None, model: str = None, max_tokens: int = 1000):
        import json as _json
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or "qwen3-32b",
            # "model": model or "Qwen/Qwen3-8B",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": True,
            "enable_thinking": False
        }

        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=120,
                stream=True
            )

            if response.status_code != 200:
                logger.error(f"流式API调用失败: {response.status_code} - {response.text}")
                yield f"data: {_json.dumps({'error': f'API调用失败: {response.status_code}'}, ensure_ascii=False)}\n\n"
                return

            buffer = b""
            for chunk_bytes in response.iter_content(chunk_size=1):
                buffer += chunk_bytes
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            yield "data: [DONE]\n\n"
                            return
                        try:
                            chunk = _json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield f"data: {_json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                        except _json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"流式API调用异常: {e}")
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    def get_embedding(self, text: str, model: str = "bge-m3") -> Optional[List[float]]:
        """
        获取文本的向量表示

        Args:
            text: 输入文本
            model: Embedding模型名称

        Returns:
            向量列表或None
        """
        embedding_url = self.base_url.replace("/chat/completions", "/embeddings")

        payload = {
            "model": model,
            "input": text,
            "encoding_format": "float"
        }

        try:
            response = requests.post(
                embedding_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    return data["data"][0].get("embedding")
            else:
                logger.error(f"Embedding API调用失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Embedding API调用异常: {e}")
            return None

    @staticmethod
    def _build_hi_agent_headers(api_key: str,
                                cap_user_name: str = None,
                                real_name: str = None,
                                kk: str = None,
                                oasis_access_token: str = None,
                                ua: str = None) -> Dict[str, str]:
        """
        构建 hi-agent 平台请求 headers。

        参数说明（与 hi-agent 接口文档对齐）:
            api_key:              API-KEY（String，必填）CAP 中用于校验调用 agent 权限的 key
            cap_user_name:        CAP 工号（String，可选）非英文需要 URL Encode 后传入
            real_name:            真实用户名（String，可选）非英文需要 URL Encode 后传入
            kk:                   KK（String，可选）
            oasis_access_token:   oasis_access_token（String，可选）
            ua:                   ua（String，可选）
        """
        headers: Dict[str, str] = {"API-KEY": api_key}
        if cap_user_name:
            headers["cap_user_name"] = cap_user_name
        if real_name:
            headers["real_name"] = real_name
        if kk:
            headers["KK"] = kk
        if oasis_access_token:
            headers["oasis_access_token"] = oasis_access_token
        if ua:
            headers["ua"] = ua
        return headers

    @staticmethod
    def _build_hi_agent_payload(query: str, agent_id: str,
                                session_id: str = None,
                                agent_args: Dict = None,
                                agent_files: List[Dict] = None,
                                agent_card: str = None) -> Dict[str, Any]:
        """
        构建 hi-agent 请求 body。

        参数说明（与 hi-agent 接口文档对齐）:
            query:          与 agent 对话的用户输入（String，必填）
            agent_id:       citics_agent_id（String，必填）
            session_id:     hi-agent 会话 id，传入则在指定会话继续对话，不传则创建新会话
            agent_args:     其他调用 agent 时涉及到的参数集
            agent_files:    上传的文件 [{"name":"xxx", "url":"xxxx"}]
            agent_card:     交互式卡片内容
        """
        payload: Dict[str, Any] = {
            "query": query,
            "citics_agent_id": agent_id,
        }
        if session_id:
            payload["session_id"] = session_id
        if agent_args:
            payload["agent_args"] = agent_args
        if agent_files:
            payload["agent_files"] = agent_files
        if agent_card:
            payload["agent_card"] = agent_card
        return payload

    def call_hi_agent_stream(self, user_input: str, api_url: str,
                             agent_id: str, system_prompt: str = None,
                             session_id: str = None,
                             cap_user_name: str = None,
                             real_name: str = None,
                             kk: str = None,
                             oasis_access_token: str = None,
                             ua: str = None):
        """
        流式调用 hi-agent 平台，yield 统一格式的 SSE 数据。

        按照 hi-agent 接口规范发起请求，逐行解析 SSE 响应，
        仅提取 step=='answer' 且 status=='running' 的 content。
        最终 yield 格式与 generate_stream() 对齐：data: {"content": "..."}\n\n
        """
        import json as _json

        query = f"{system_prompt}\n\n{user_input}" if system_prompt else user_input
        headers = self._build_hi_agent_headers(
            api_key=self.api_key,
            cap_user_name=cap_user_name,
            real_name=real_name,
            kk=kk,
            oasis_access_token=oasis_access_token,
            ua=ua,
        )
        payload = self._build_hi_agent_payload(
            query=query,
            agent_id=agent_id,
            session_id=session_id,
        )

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=120,
                stream=True,
            )

            if response.status_code != 200:
                logger.error(f"hi-agent 流式API调用失败: {response.status_code} - {response.text}")
                yield f"data: {_json.dumps({'error': f'hi-agent API调用失败: {response.status_code}'}, ensure_ascii=False)}\n\n"
                return

            buffer = b""
            for chunk_bytes in response.iter_content(chunk_size=1):
                buffer += chunk_bytes
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            return
                        try:
                            chunk = _json.loads(data_str)
                            if (chunk.get("step") == "answer"
                                    and chunk.get("status") == "running"
                                    and "content" in chunk):
                                yield f"data: {_json.dumps({'content': chunk['content']}, ensure_ascii=False)}\n\n"
                        except _json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"hi-agent 流式API调用异常: {e}")
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    def call_hi_agent(self, user_input: str, api_url: str,
                      agent_id: str, system_prompt: str = None,
                      session_id: str = None,
                      cap_user_name: str = None,
                      real_name: str = None,
                      kk: str = None,
                      oasis_access_token: str = None,
                      ua: str = None) -> Optional[str]:
        """
        非流式调用 hi-agent 平台（一次性返回完整结果）。

        Args:
            user_input:          用户输入
            api_url:             hi-agent 平台 API 地址
            agent_id:            citics_agent_id
            system_prompt:       系统提示（拼接到 query 前面）
            session_id:          hi-agent 会话 id，传入则在指定会话继续对话
            cap_user_name:       CAP 工号（可选）
            real_name:           真实用户名（可选）
            kk:                  KK（可选）
            oasis_access_token:  oasis_access_token（可选）
            ua:                  ua（可选）
        """
        query = f"{system_prompt}\n\n{user_input}" if system_prompt else user_input
        headers = self._build_hi_agent_headers(
            api_key=self.api_key,
            cap_user_name=cap_user_name,
            real_name=real_name,
            kk=kk,
            oasis_access_token=oasis_access_token,
            ua=ua,
        )
        payload = self._build_hi_agent_payload(
            query=query,
            agent_id=agent_id,
            session_id=session_id,
        )

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                return self.parse_sse_to_text(response.text)
            else:
                logger.error(f"hi-agent API调用失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"hi-agent API调用异常: {e}")
            return None

    def parse_sse_to_text(self, sse_data: str) -> str:
        """将 SSE 格式的原始输出解析为最终的文本内容。"""
        lines = sse_data.strip().split('\n')
        result_parts = []
        for line in lines:
            if line.startswith('data: '):
                json_str = line[6:]
                if json_str == '[DONE]':
                    continue
                try:
                    data = json.loads(json_str)
                    if (data.get('step') == 'answer'
                            and data.get('status') == 'running'
                            and 'content' in data):
                        result_parts.append(data['content'])
                except json.JSONDecodeError:
                    continue
        return ''.join(result_parts)
