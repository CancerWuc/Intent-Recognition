from dataclasses import dataclass, field
from typing import Dict, Optional, List
from ..llm import LLMClient


@dataclass
class LLMRecognitionResult:
    """大模型识别结果"""
    success: bool
    scene_id: Optional[str] = None
    scene_name: Optional[str] = None
    intent_id: Optional[str] = None
    intent_name: Optional[str] = None
    agent_id: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    metadata: Dict = field(default_factory=dict)


class LLMBasedRecognizer:
    """
    基于大模型的意图识别器
    
    使用大模型理解用户输入，识别场景和意图
    """
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化基于大模型的识别器
        
        Args:
            llm_client: 大模型客户端
        """
        self.llm_client = llm_client
        self.scenes: Dict[str, Dict] = {}
        self.intents: Dict[str, Dict] = {}
        self.scene_intents: Dict[str, List[str]] = {}
    
    def register_scene(self, scene_id: str, name: str, 
                       keywords: List[str], examples: List[str] = None,
                       description: str = None, metadata: Dict = None) -> None:
        """注册场景"""
        self.scenes[scene_id] = {
            "scene_id": scene_id,
            "name": name,
            "description": description or "",
            "keywords": keywords,
            "examples": examples or [],
            "metadata": metadata or {}
        }
    
    def register_intent(self, intent_id: str, scene_id: str, name: str,
                        keywords: List[str], examples: List[str] = None,
                        description: str = None, agent_id: str = None, 
                        parameters: Dict = None, metadata: Dict = None) -> None:
        """注册意图"""
        self.intents[intent_id] = {
            "intent_id": intent_id,
            "scene_id": scene_id,
            "name": name,
            "description": description or "",
            "keywords": keywords,
            "examples": examples or [],
            "agent_id": agent_id,
            "parameters": parameters or {},
            "metadata": metadata or {}
        }
        
        if scene_id not in self.scene_intents:
            self.scene_intents[scene_id] = []
        self.scene_intents[scene_id].append(intent_id)
    
    def recognize(self, user_input: str, two_step: bool = False) -> LLMRecognitionResult:
        """
        使用大模型识别场景和意图
        
        Args:
            user_input: 用户输入
            two_step: 是否使用两步推理（先识别场景，再识别意图）
            
        Returns:
            LLMRecognitionResult: 识别结果
        """
        if not user_input:
            return LLMRecognitionResult(success=False)
        
        if not self.scenes:
            return LLMRecognitionResult(success=False)
        
        if two_step:
            return self._two_step_recognition(user_input)
        else:
            return self._one_step_recognition(user_input)
    
    def _one_step_recognition(self, user_input: str) -> LLMRecognitionResult:
        """
        一步推理：同时识别场景和意图
        """
        prompt = self._build_recognition_prompt(user_input)
        system_prompt = "你是一个意图识别助手，擅长理解用户需求并分类到正确的场景和意图中。"
        
        response = self.llm_client.generate(prompt, system_prompt)
        
        if not response:
            return LLMRecognitionResult(success=False)
        
        result = self._parse_response(response)
        return result
    
    def _two_step_recognition(self, user_input: str) -> LLMRecognitionResult:
        """
        两步推理：先识别场景，再识别意图
        """
        # 第一步：识别场景
        scene_result = self._recognize_scene(user_input)
        if not scene_result.success:
            return scene_result
        
        # 第二步：在识别的场景内识别意图
        intent_result = self._recognize_intent(user_input, scene_result.scene_id)
        if not intent_result.success:
            return intent_result
        
        # 合并结果
        return LLMRecognitionResult(
            success=True,
            scene_id=scene_result.scene_id,
            scene_name=scene_result.scene_name,
            intent_id=intent_result.intent_id,
            intent_name=intent_result.intent_name,
            agent_id=intent_result.agent_id,
            confidence=(scene_result.confidence + intent_result.confidence) / 2,
            reasoning=f"场景识别：{scene_result.reasoning}\n意图识别：{intent_result.reasoning}",
            metadata={
                "scene_recognition": scene_result.metadata,
                "intent_recognition": intent_result.metadata
            }
        )
    
    def _recognize_scene(self, user_input: str) -> LLMRecognitionResult:
        """
        识别场景
        """
        scenes_info = "\n".join([
            f"- 场景ID: {s['scene_id']}, 名称: {s['name']}, 描述: {s['description']}, 关键词: {', '.join(s['keywords'])}, 示例: {', '.join(s['examples'])}"
            for s in self.scenes.values()
        ])
        
        prompt = f"""
用户输入: {user_input}

可用场景:
{scenes_info}

请根据用户输入，识别最匹配的场景，并以JSON格式返回：
{{
  "scene_id": "识别的场景ID",
  "scene_name": "识别的场景名称",
  "confidence": 0.0-1.0之间的置信度,
  "reasoning": "识别的推理过程"
}}

要求：
1. 严格按照JSON格式输出
2. 只输出JSON，不要输出其他内容
3. 置信度要合理，反映匹配程度
4. reasoning要清晰说明为什么选择该场景
"""
        
        system_prompt = "你是一个场景识别助手，擅长根据用户需求识别正确的场景。"
        response = self.llm_client.generate(prompt, system_prompt)
        
        if not response:
            return LLMRecognitionResult(success=False)
        
        try:
            import json
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)
                
                return LLMRecognitionResult(
                    success=True,
                    scene_id=data.get("scene_id"),
                    scene_name=data.get("scene_name"),
                    confidence=float(data.get("confidence", 0.0)),
                    reasoning=data.get("reasoning", ""),
                    metadata={"raw_response": response}
                )
        except Exception as e:
            import logging
            logging.error(f"解析场景识别响应失败: {e}")
        
        return LLMRecognitionResult(
            success=False,
            metadata={"error": "解析场景识别响应失败", "raw_response": response}
        )
    
    def _recognize_intent(self, user_input: str, scene_id: str) -> LLMRecognitionResult:
        """
        在特定场景内识别意图
        """
        # 获取该场景下的所有意图
        scene_intents = [intent for intent in self.intents.values() if intent["scene_id"] == scene_id]
        if not scene_intents:
            return LLMRecognitionResult(
                success=False,
                metadata={"error": f"场景 {scene_id} 下无意图"}
            )
        
        intents_info = "\n".join([
            f"- 意图ID: {i['intent_id']}, 名称: {i['name']}, 描述: {i['description']}, 关键词: {', '.join(i['keywords'])}, 示例: {', '.join(i['examples'])}"
            for i in scene_intents
        ])
        
        prompt = f"""
用户输入: {user_input}

当前场景: {self.scenes.get(scene_id, {}).get('name', scene_id)}

该场景下的可用意图:
{intents_info}

请根据用户输入，在当前场景内识别最匹配的意图，并以JSON格式返回：
{{
  "intent_id": "识别的意图ID",
  "intent_name": "识别的意图名称",
  "confidence": 0.0-1.0之间的置信度,
  "reasoning": "识别的推理过程"
}}

要求：
1. 严格按照JSON格式输出
2. 只输出JSON，不要输出其他内容
3. 置信度要合理，反映匹配程度
4. reasoning要清晰说明为什么选择该意图
"""
        
        system_prompt = "你是一个意图识别助手，擅长在特定场景内识别用户的具体意图。"
        response = self.llm_client.generate(prompt, system_prompt)
        
        if not response:
            return LLMRecognitionResult(success=False)
        
        try:
            import json
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)
                
                # 查找对应的agent_id
                agent_id = None
                intent_id = data.get("intent_id")
                if intent_id:
                    intent = self.intents.get(intent_id)
                    if intent:
                        agent_id = intent.get("agent_id")
                
                return LLMRecognitionResult(
                    success=True,
                    intent_id=intent_id,
                    intent_name=data.get("intent_name"),
                    agent_id=agent_id,
                    confidence=float(data.get("confidence", 0.0)),
                    reasoning=data.get("reasoning", ""),
                    metadata={"raw_response": response}
                )
        except Exception as e:
            import logging
            logging.error(f"解析意图识别响应失败: {e}")
        
        return LLMRecognitionResult(
            success=False,
            metadata={"error": "解析意图识别响应失败", "raw_response": response}
        )
    
    def _build_recognition_prompt(self, user_input: str) -> str:
        """
        构建识别提示
        
        Args:
            user_input: 用户输入
            
        Returns:
            提示文本
        """
        scenes_info = "\n".join([
            f"- 场景ID: {s['scene_id']}, 名称: {s['name']}, 描述: {s['description']}, 关键词: {', '.join(s['keywords'])}, 示例: {', '.join(s['examples'])}"
            for s in self.scenes.values()
        ])
        
        intents_info = "\n".join([
            f"- 场景ID: {i['scene_id']}, 意图ID: {i['intent_id']}, 名称: {i['name']}, 描述: {i['description']}, 关键词: {', '.join(i['keywords'])}, 示例: {', '.join(i['examples'])}"
            for i in self.intents.values()
        ])
        
        prompt = f"""
用户输入: {user_input}

可用场景:
{scenes_info}

可用意图:
{intents_info}

请根据用户输入，识别最匹配的场景和意图，并以JSON格式返回：
{{
  "scene_id": "识别的场景ID",
  "scene_name": "识别的场景名称",
  "intent_id": "识别的意图ID",
  "intent_name": "识别的意图名称",
  "confidence": 0.0-1.0之间的置信度,
  "reasoning": "识别的推理过程"
}}

要求：
1. 严格按照JSON格式输出
2. 只输出JSON，不要输出其他内容
3. 置信度要合理，反映匹配程度
4. reasoning要清晰说明为什么选择该场景和意图
"""
        
        return prompt
    
    def _parse_response(self, response: str) -> LLMRecognitionResult:
        """
        解析大模型响应
        
        Args:
            response: 大模型响应
            
        Returns:
            LLMRecognitionResult: 识别结果
        """
        try:
            # 提取JSON部分
            import json
            # 尝试找到JSON开始和结束
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)
                
                # 查找对应的agent_id
                agent_id = None
                if data.get("intent_id"):
                    intent = self.intents.get(data["intent_id"])
                    if intent:
                        agent_id = intent.get("agent_id")
                
                return LLMRecognitionResult(
                    success=True,
                    scene_id=data.get("scene_id"),
                    scene_name=data.get("scene_name"),
                    intent_id=data.get("intent_id"),
                    intent_name=data.get("intent_name"),
                    agent_id=agent_id,
                    confidence=float(data.get("confidence", 0.0)),
                    reasoning=data.get("reasoning", ""),
                    metadata={"raw_response": response}
                )
        except Exception as e:
            import logging
            logging.error(f"解析响应失败: {e}")
        
        return LLMRecognitionResult(
            success=False,
            metadata={"error": "解析响应失败", "raw_response": response}
        )
    
    def get_scene_info(self, scene_id: str) -> Optional[Dict]:
        """获取场景信息"""
        return self.scenes.get(scene_id)
    
    def get_intent_info(self, intent_id: str) -> Optional[Dict]:
        """获取意图信息"""
        return self.intents.get(intent_id)
    
    def list_scenes(self) -> List[Dict]:
        """列出所有场景"""
        return list(self.scenes.values())
    
    def list_intents(self, scene_id: str = None) -> List[Dict]:
        """列出所有意图，可选按场景过滤"""
        if scene_id:
            return [intent for intent in self.intents.values() if intent["scene_id"] == scene_id]
        return list(self.intents.values())
