import numpy as np
from typing import Dict, List, Optional
import logging
import hashlib
from ..llm import LLMClient

logger = logging.getLogger(__name__)


class EmbeddingRecognizer:
    """
    基于向量匹配的意图识别器

    离线：将场景/意图的文本描述转为向量缓存到数据库
    在线：从数据库加载向量，将用户输入转为向量，余弦相似度匹配
    """

    def __init__(self, llm_client: LLMClient, confidence_threshold: float = 0.5):
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold
        self.scenes: Dict[str, Dict] = {}
        self.intents: Dict[str, Dict] = {}
        self._scene_vectors: Dict[str, np.ndarray] = {}
        self._intent_vectors: Dict[str, np.ndarray] = {}
        self._vector_dirty = True
        self._text_hashes: Dict[str, str] = {}

    def _compute_text_hash(self, data: Dict, is_scene: bool = True) -> str:
        text = self._build_text(data, is_scene)
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def register_scene(self, scene_id: str, name: str,
                       keywords: List[str], examples: List[str] = None,
                       description: str = None, metadata: Dict = None,
                       vector: np.ndarray = None, text_hash: str = None) -> None:
        self.scenes[scene_id] = {
            "scene_id": scene_id,
            "name": name,
            "description": description or "",
            "keywords": keywords,
            "examples": examples or [],
            "metadata": metadata or {}
        }
        if vector is not None:
            self._scene_vectors[scene_id] = vector
            if text_hash:
                self._text_hashes[f"scene_{scene_id}"] = text_hash
        else:
            self._vector_dirty = True

    def register_intent(self, intent_id: str, scene_id: str, name: str,
                        keywords: List[str], examples: List[str] = None,
                        description: str = None, agent_id: str = None,
                        parameters: Dict = None, metadata: Dict = None,
                        vector: np.ndarray = None, text_hash: str = None) -> None:
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
        if vector is not None:
            self._intent_vectors[intent_id] = vector
            if text_hash:
                self._text_hashes[f"intent_{intent_id}"] = text_hash
        else:
            self._vector_dirty = True

    def _build_text(self, data: Dict, is_scene: bool = True) -> str:
        parts = []
        if is_scene:
            parts.append(f"场景: {data['name']}")
        else:
            parts.append(f"意图: {data['name']}")
            parts.append(f"所属场景: {data.get('scene_id', '')}")

        if data.get("description"):
            parts.append(data["description"])

        if data.get("keywords"):
            parts.append("关键词: " + ", ".join(data["keywords"]))

        if data.get("examples"):
            parts.append("示例: " + ", ".join(data["examples"]))

        return " | ".join(parts)

    def load_vectors_from_db(self) -> int:
        """
        从数据库加载已存储的向量
        返回成功加载的向量数量
        """
        from ..database import db, SceneVector, IntentVector
        from sqlalchemy.orm import Session

        loaded_count = 0
        session = Session(db.engine)

        try:
            for scene_id, scene in self.scenes.items():
                stored = session.query(SceneVector).filter_by(scene_id=scene_id).first()
                if stored:
                    current_hash = self._compute_text_hash(scene, is_scene=True)
                    if stored.text_hash == current_hash:
                        self._scene_vectors[scene_id] = stored.get_vector()
                        self._text_hashes[f"scene_{scene_id}"] = current_hash
                        loaded_count += 1
                        logger.debug(f"从数据库加载场景向量: {scene_id}")

            for intent_id, intent in self.intents.items():
                stored = session.query(IntentVector).filter_by(intent_id=intent_id).first()
                if stored:
                    current_hash = self._compute_text_hash(intent, is_scene=False)
                    if stored.text_hash == current_hash:
                        self._intent_vectors[intent_id] = stored.get_vector()
                        self._text_hashes[f"intent_{intent_id}"] = current_hash
                        loaded_count += 1
                        logger.debug(f"从数据库加载意图向量: {intent_id}")

            all_scenes_loaded = len(self._scene_vectors) == len(self.scenes)
            all_intents_loaded = len(self._intent_vectors) == len(self.intents)

            if all_scenes_loaded and all_intents_loaded:
                self._vector_dirty = False
                logger.info(f"从数据库加载 {loaded_count} 个向量，无需重新计算")
            else:
                missing_scenes = set(self.scenes.keys()) - set(self._scene_vectors.keys())
                missing_intents = set(self.intents.keys()) - set(self._intent_vectors.keys())
                logger.info(f"从数据库加载 {loaded_count} 个向量，需计算 {len(missing_scenes)} 个场景 + {len(missing_intents)} 个意图")

        except Exception as e:
            logger.error(f"从数据库加载向量失败: {e}")
        finally:
            session.close()

        return loaded_count

    def save_vectors_to_db(self) -> int:
        """
        将当前向量保存到数据库
        返回成功保存的向量数量
        """
        from ..database import db, SceneVector, IntentVector
        from sqlalchemy.orm import Session

        saved_count = 0
        session = Session(db.engine)

        try:
            for scene_id, vector in self._scene_vectors.items():
                if scene_id not in self.scenes:
                    continue
                scene = self.scenes[scene_id]
                text_hash = self._compute_text_hash(scene, is_scene=True)

                stored = session.query(SceneVector).filter_by(scene_id=scene_id).first()
                if stored:
                    stored.vector_data = None
                    stored.set_vector(vector)
                    stored.text_hash = text_hash
                else:
                    stored = SceneVector(
                        scene_id=scene_id,
                        text_hash=text_hash
                    )
                    stored.set_vector(vector)
                    session.add(stored)
                saved_count += 1

            for intent_id, vector in self._intent_vectors.items():
                if intent_id not in self.intents:
                    continue
                intent = self.intents[intent_id]
                text_hash = self._compute_text_hash(intent, is_scene=False)

                stored = session.query(IntentVector).filter_by(intent_id=intent_id).first()
                if stored:
                    stored.vector_data = None
                    stored.set_vector(vector)
                    stored.text_hash = text_hash
                else:
                    stored = IntentVector(
                        intent_id=intent_id,
                        text_hash=text_hash
                    )
                    stored.set_vector(vector)
                    session.add(stored)
                saved_count += 1

            session.commit()
            logger.info(f"保存 {saved_count} 个向量到数据库")

        except Exception as e:
            session.rollback()
            logger.error(f"保存向量到数据库失败: {e}")
        finally:
            session.close()

        return saved_count

    def build_vectors(self) -> None:
        if not self._vector_dirty:
            return

        logger.info("正在构建场景和意图的向量索引...")

        self.load_vectors_from_db()

        missing_scene_ids = set(self.scenes.keys()) - set(self._scene_vectors.keys())
        missing_intent_ids = set(self.intents.keys()) - set(self._intent_vectors.keys())

        if not missing_scene_ids and not missing_intent_ids:
            self._vector_dirty = False
            logger.info("所有向量已从数据库加载，无需调用LLM")
            return

        all_texts = []
        text_keys = []

        for scene_id in missing_scene_ids:
            scene = self.scenes[scene_id]
            text = self._build_text(scene, is_scene=True)
            all_texts.append(text)
            text_keys.append(("scene", scene_id))

        for intent_id in missing_intent_ids:
            intent = self.intents[intent_id]
            text = self._build_text(intent, is_scene=False)
            all_texts.append(text)
            text_keys.append(("intent", intent_id))

        if not all_texts:
            self._vector_dirty = False
            return

        logger.info(f"需要计算 {len(all_texts)} 个新向量...")
        vectors = self._batch_embed(all_texts)

        if vectors is None:
            logger.error("向量构建失败")
            return

        for i, (key_type, key_id) in enumerate(text_keys):
            if i < len(vectors):
                if key_type == "scene":
                    self._scene_vectors[key_id] = vectors[i]
                else:
                    self._intent_vectors[key_id] = vectors[i]

        self._vector_dirty = False
        logger.info(f"向量索引构建完成: {len(self._scene_vectors)} 个场景, {len(self._intent_vectors)} 个意图")

        self.save_vectors_to_db()

    def _batch_embed(self, texts: List[str]) -> Optional[List[np.ndarray]]:
        vectors = []
        for text in texts:
            vec = self.llm_client.get_embedding(text)
            if vec is None:
                logger.error(f"获取向量失败: {text[:50]}")
                return None
            vectors.append(np.array(vec))
        return vectors

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def recognize(self, user_input: str) -> Dict:
        """
        使用向量匹配识别场景和意图

        Returns:
            {
                "success": bool,
                "scene_id": str,
                "scene_name": str,
                "intent_id": str,
                "intent_name": str,
                "agent_id": str,
                "confidence": float,
                "method": "embedding",
                "scene_scores": dict,
                "intent_scores": dict
            }
        """
        self.build_vectors()

        if not self._scene_vectors or not self._intent_vectors:
            return {"success": False, "confidence": 0.0, "method": "embedding"}

        user_vec = self.llm_client.get_embedding(user_input)
        if user_vec is None:
            return {"success": False, "confidence": 0.0, "method": "embedding"}
        user_vec = np.array(user_vec)

        scene_scores = {}
        for scene_id, scene_vec in self._scene_vectors.items():
            scene_scores[scene_id] = self._cosine_similarity(user_vec, scene_vec)

        if not scene_scores:
            return {"success": False, "confidence": 0.0, "method": "embedding"}

        best_scene_id = max(scene_scores, key=scene_scores.get)
        best_scene_score = scene_scores[best_scene_id]

        scene_intents = {
            iid: i for iid, i in self.intents.items()
            if i["scene_id"] == best_scene_id
        }

        intent_scores = {}
        for intent_id in scene_intents:
            if intent_id in self._intent_vectors:
                intent_scores[intent_id] = self._cosine_similarity(user_vec, self._intent_vectors[intent_id])

        if not intent_scores:
            best_scene = self.scenes.get(best_scene_id, {})
            return {
                "success": False,
                "scene_id": best_scene_id,
                "scene_name": best_scene.get("name", ""),
                "confidence": best_scene_score,
                "method": "embedding",
                "scene_scores": scene_scores,
                "intent_scores": intent_scores,
                "reasoning": f"场景匹配成功（{best_scene_score:.3f}），但该场景下无意图向量"
            }

        best_intent_id = max(intent_scores, key=intent_scores.get)
        best_intent_score = intent_scores[best_intent_id]

        overall_confidence = (best_scene_score + best_intent_score) / 2

        best_scene = self.scenes.get(best_scene_id, {})
        best_intent = self.intents.get(best_intent_id, {})
        agent_id = best_intent.get("agent_id")

        success = overall_confidence >= self.confidence_threshold

        return {
            "success": success,
            "scene_id": best_scene_id,
            "scene_name": best_scene.get("name", ""),
            "intent_id": best_intent_id,
            "intent_name": best_intent.get("name", ""),
            "agent_id": agent_id,
            "confidence": overall_confidence,
            "method": "embedding",
            "scene_scores": {k: round(v, 4) for k, v in scene_scores.items()},
            "intent_scores": {k: round(v, 4) for k, v in intent_scores.items()},
            "reasoning": f"向量匹配 - 场景: {best_scene.get('name', '')}({best_scene_score:.3f}), "
                         f"意图: {best_intent.get('name', '')}({best_intent_score:.3f})"
        }

    def mark_dirty(self) -> None:
        self._vector_dirty = True
