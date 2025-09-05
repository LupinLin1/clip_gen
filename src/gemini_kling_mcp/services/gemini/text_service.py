"""
Gemini 文本服务

提供统一的 Gemini 文本生成、对话完成和文本分析功能。
"""

import asyncio
from typing import Dict, List, Any, Optional, Union
from contextlib import asynccontextmanager

from ...config import GeminiConfig, get_config
from ...logger import get_logger  
from ...exceptions import ToolExecutionError, ValidationError
from .client import GeminiClient, GeminiHTTPError
from .models import (
    TextGenerationRequest, TextGenerationResponse,
    ChatCompletionRequest, ChatCompletionResponse,
    TextAnalysisRequest, TextAnalysisResponse,
    GeminiMessage, GeminiModel, MessageRole,
    DEFAULT_SAFETY_SETTINGS
)
from .validators import (
    validate_text_generation_request,
    validate_chat_completion_request,
    validate_text_analysis_request
)

class GeminiTextService:
    """Gemini 文本服务"""
    
    def __init__(self, config: Optional[GeminiConfig] = None):
        self.config = config or get_config().gemini
        self.logger = get_logger("gemini_text_service")
        self._client: Optional[GeminiClient] = None
    
    @asynccontextmanager
    async def _get_client(self):
        """获取客户端实例（上下文管理器）"""
        if self._client is None:
            self._client = GeminiClient(self.config)
        
        async with self._client as client:
            yield client
    
    async def generate_text(
        self, 
        request: Union[TextGenerationRequest, Dict[str, Any]]
    ) -> TextGenerationResponse:
        """生成文本"""
        # 转换请求格式
        if isinstance(request, dict):
            try:
                request = TextGenerationRequest(**request)
            except Exception as e:
                raise ValidationError(f"请求参数无效: {e}", details={"request": request})
        
        self.logger.info(
            "开始文本生成",
            model=request.model.value,
            prompt_length=len(request.prompt),
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        try:
            # 额外的参数验证
            validate_text_generation_request(
                prompt=request.prompt,
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                stop_sequences=request.stop_sequences,
                safety_settings=request.safety_settings
            )
            
            # 构建 API 请求数据
            api_request = self._build_generation_request(request)
            
            # 调用 API
            async with self._get_client() as client:
                response_data = await client.generate_content(request.model, api_request)
            
            # 解析响应
            response = self._parse_generation_response(response_data, request.model.value)
            
            self.logger.info(
                "文本生成完成",
                generated_length=len(response.text),
                finish_reason=response.finish_reason
            )
            
            return response
            
        except GeminiHTTPError as e:
            self.logger.error(f"Gemini API调用失败: {e.message}", status_code=e.status_code)
            raise ToolExecutionError(
                f"文本生成失败: {e.message}",
                tool_name="gemini_generate_text",
                details={"api_error": e.response_data}
            )
        
        except Exception as e:
            self.logger.exception("文本生成异常")
            raise ToolExecutionError(
                f"文本生成异常: {str(e)}",
                tool_name="gemini_generate_text",
                details={"error": str(e)}
            )
    
    async def complete_chat(
        self,
        request: Union[ChatCompletionRequest, Dict[str, Any]]
    ) -> ChatCompletionResponse:
        """完成对话"""
        # 转换请求格式
        if isinstance(request, dict):
            try:
                # 处理消息格式转换
                if "messages" in request and isinstance(request["messages"][0], dict):
                    messages = [
                        GeminiMessage.from_dict(msg) if isinstance(msg, dict) else msg
                        for msg in request["messages"]
                    ]
                    request["messages"] = messages
                
                request = ChatCompletionRequest(**request)
            except Exception as e:
                raise ValidationError(f"请求参数无效: {e}", details={"request": request})
        
        self.logger.info(
            "开始对话完成",
            model=request.model.value,
            message_count=len(request.messages),
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        try:
            # 额外的参数验证
            messages_dict = [{"role": msg.role.value, "content": msg.content} for msg in request.messages]
            validate_chat_completion_request(
                messages=messages_dict,
                model=request.model,
                system_instruction=request.system_instruction,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                stop_sequences=request.stop_sequences,
                safety_settings=request.safety_settings
            )
            
            # 构建 API 请求数据
            api_request = self._build_chat_request(request)
            
            # 调用 API
            async with self._get_client() as client:
                response_data = await client.chat_completion(request.model, api_request)
            
            # 解析响应
            response = self._parse_chat_response(response_data, request.model.value)
            
            self.logger.info(
                "对话完成完成",
                response_length=len(response.message.content),
                finish_reason=response.finish_reason
            )
            
            return response
            
        except GeminiHTTPError as e:
            self.logger.error(f"Gemini API调用失败: {e.message}", status_code=e.status_code)
            raise ToolExecutionError(
                f"对话完成失败: {e.message}",
                tool_name="gemini_chat_completion",
                details={"api_error": e.response_data}
            )
        
        except Exception as e:
            self.logger.exception("对话完成异常")
            raise ToolExecutionError(
                f"对话完成异常: {str(e)}",
                tool_name="gemini_chat_completion",
                details={"error": str(e)}
            )
    
    async def analyze_text(
        self,
        request: Union[TextAnalysisRequest, Dict[str, Any]]
    ) -> TextAnalysisResponse:
        """分析文本"""
        # 转换请求格式
        if isinstance(request, dict):
            try:
                request = TextAnalysisRequest(**request)
            except Exception as e:
                raise ValidationError(f"请求参数无效: {e}", details={"request": request})
        
        self.logger.info(
            "开始文本分析",
            model=request.model.value,
            text_length=len(request.text),
            analysis_type=request.analysis_type,
            language=request.language
        )
        
        try:
            # 额外的参数验证
            validate_text_analysis_request(
                text=request.text,
                model=request.model,
                analysis_type=request.analysis_type,
                language=request.language,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            # 构建分析提示
            analysis_prompt = self._build_analysis_prompt(request)
            
            # 构建 API 请求数据
            api_request = self._build_analysis_request(analysis_prompt, request)
            
            # 调用 API
            async with self._get_client() as client:
                response_data = await client.analyze_text(request.model, api_request)
            
            # 解析响应
            response = self._parse_analysis_response(response_data, request.model.value)
            
            self.logger.info(
                "文本分析完成",
                analysis_length=len(response.analysis)
            )
            
            return response
            
        except GeminiHTTPError as e:
            self.logger.error(f"Gemini API调用失败: {e.message}", status_code=e.status_code)
            raise ToolExecutionError(
                f"文本分析失败: {e.message}",
                tool_name="gemini_analyze_text",
                details={"api_error": e.response_data}
            )
        
        except Exception as e:
            self.logger.exception("文本分析异常")
            raise ToolExecutionError(
                f"文本分析异常: {str(e)}",
                tool_name="gemini_analyze_text",
                details={"error": str(e)}
            )
    
    def _build_generation_request(self, request: TextGenerationRequest) -> Dict[str, Any]:
        """构建文本生成请求（gptproto.com OpenAI格式）"""
        api_request = {
            "model": request.model.value,
            "messages": [
                {"role": "user", "content": request.prompt}
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        
        if request.stop_sequences:
            api_request["stop"] = request.stop_sequences
        
        return api_request
    
    def _build_chat_request(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """构建对话请求（gptproto.com OpenAI格式）"""
        # 转换消息格式
        messages = []
        
        # 添加系统指令
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        
        # 添加对话历史
        for message in request.messages:
            messages.append({
                "role": message.role.value if hasattr(message.role, 'value') else str(message.role),
                "content": message.content
            })
        
        api_request = {
            "model": request.model.value,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        
        if request.stop_sequences:
            api_request["stop"] = request.stop_sequences
        
        return api_request
    
    def _build_analysis_prompt(self, request: TextAnalysisRequest) -> str:
        """构建分析提示"""
        analysis_prompts = {
            "general": "请对以下文本进行全面分析，包括主题、关键信息、语言特点等：",
            "sentiment": "请分析以下文本的情感倾向，包括积极、消极或中性情绪：",
            "summarize": "请对以下文本进行简洁准确的摘要：",
            "keywords": "请从以下文本中提取关键词和关键短语：",
            "entities": "请从以下文本中识别命名实体（人名、地名、组织等）：",
            "classify": "请对以下文本进行分类：",
            "translate": "请检测以下文本的语言并进行翻译：",
            "grammar": "请检查以下文本的语法和拼写错误："
        }
        
        base_prompt = analysis_prompts.get(request.analysis_type, analysis_prompts["general"])
        
        # 添加语言提示
        if request.language and request.language != "auto":
            base_prompt += f"\n（文本语言：{request.language}）"
        
        # 添加输出格式要求
        if request.analysis_type == "sentiment":
            base_prompt += "\n请以JSON格式返回结果，包含sentiment（positive/negative/neutral）和confidence（0-1）。"
        elif request.analysis_type == "entities":
            base_prompt += "\n请以JSON格式返回结果，包含实体列表。"
        elif request.analysis_type == "keywords":
            base_prompt += "\n请以列表形式返回关键词。"
        
        return f"{base_prompt}\n\n文本内容：\n{request.text}"
    
    def _build_analysis_request(self, prompt: str, request: TextAnalysisRequest) -> Dict[str, Any]:
        """构建分析请求（gptproto.com OpenAI格式）"""
        api_request = {
            "model": request.model.value,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        
        return api_request
    
    def _parse_generation_response(
        self, 
        response_data: Dict[str, Any], 
        model: str
    ) -> TextGenerationResponse:
        """解析文本生成响应"""
        # 直接使用客户端的静态方法来解析响应
        client = GeminiClient(self.config)
        text = client.extract_generated_text(response_data)
        usage = client.extract_usage_info(response_data)
        safety_ratings = client.extract_safety_ratings(response_data)
        
        # 提取完成原因（支持OpenAI和Gemini格式）
        finish_reason = None
        if "choices" in response_data and response_data["choices"]:
            # OpenAI 格式
            finish_reason = response_data["choices"][0].get("finish_reason", "stop")
        elif "candidates" in response_data and response_data["candidates"]:
            # Gemini 原生格式
            finish_reason = response_data["candidates"][0].get("finishReason", "STOP")
        
        return TextGenerationResponse(
            text=text,
            model=model,
            finish_reason=finish_reason,
            usage=usage,
            safety_ratings=safety_ratings
        )
    
    def _parse_chat_response(
        self, 
        response_data: Dict[str, Any], 
        model: str
    ) -> ChatCompletionResponse:
        """解析对话响应"""
        # 直接使用客户端的静态方法来解析响应
        client = GeminiClient(self.config)
        text = client.extract_generated_text(response_data)
        usage = client.extract_usage_info(response_data)
        safety_ratings = client.extract_safety_ratings(response_data)
        
        # 提取完成原因（支持OpenAI和Gemini格式）
        finish_reason = None
        if "choices" in response_data and response_data["choices"]:
            # OpenAI 格式
            finish_reason = response_data["choices"][0].get("finish_reason", "stop")
        elif "candidates" in response_data and response_data["candidates"]:
            # Gemini 原生格式
            finish_reason = response_data["candidates"][0].get("finishReason", "STOP")
        
        # 创建响应消息
        message = GeminiMessage(role=MessageRole.MODEL, content=text)
        
        return ChatCompletionResponse(
            message=message,
            model=model,
            finish_reason=finish_reason,
            usage=usage,
            safety_ratings=safety_ratings
        )
    
    def _parse_analysis_response(
        self, 
        response_data: Dict[str, Any], 
        model: str
    ) -> TextAnalysisResponse:
        """解析文本分析响应"""
        # 直接使用客户端的静态方法来解析响应
        client = GeminiClient(self.config)
        text = client.extract_generated_text(response_data)
        usage = client.extract_usage_info(response_data)
        
        # 尝试解析结构化结果
        confidence = None
        categories = None
        sentiment = None
        entities = None
        
        try:
            # 尝试解析JSON格式的分析结果
            import json
            if text.strip().startswith('{'):
                analysis_result = json.loads(text)
                
                if "sentiment" in analysis_result:
                    sentiment = analysis_result
                    confidence = analysis_result.get("confidence")
                
                if "entities" in analysis_result:
                    entities = analysis_result["entities"]
                
                if "categories" in analysis_result:
                    categories = analysis_result["categories"]
                    
        except json.JSONDecodeError:
            # 如果不是JSON格式，保持原始文本
            pass
        
        return TextAnalysisResponse(
            analysis=text,
            model=model,
            confidence=confidence,
            categories=categories,
            sentiment=sentiment,
            entities=entities,
            usage=usage
        )
    
    async def close(self) -> None:
        """关闭服务"""
        if self._client:
            await self._client.close()
            self._client = None
        self.logger.info("Gemini文本服务已关闭")