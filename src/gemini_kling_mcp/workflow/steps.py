"""
工作流步骤定义

定义各种类型的工作流步骤和执行器。
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum

from ..logger import get_logger
from ..exceptions import WorkflowError, ToolExecutionError
from ..services.gemini.text_service import GeminiTextService
from ..services.gemini.image_service import GeminiImageService
from ..services.kling.video_service import KlingVideoService
from ..file_manager.core import FileManager
from ..config import get_config


class StepType(Enum):
    """步骤类型枚举"""
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation" 
    TEXT_ANALYSIS = "text_analysis"
    IMAGE_ANALYSIS = "image_analysis"
    FILE_OPERATION = "file_operation"
    CONDITION = "condition"
    PARALLEL = "parallel"
    CUSTOM = "custom"


@dataclass
class StepResult:
    """步骤执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    execution_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata or {},
            "execution_time": self.execution_time
        }


class WorkflowStep(ABC):
    """工作流步骤抽象基类"""
    
    def __init__(self, step_id: str, name: str, config: Dict[str, Any]):
        self.step_id = step_id
        self.name = name
        self.config = config
        self.logger = get_logger(f"workflow_step_{step_id}")
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        """执行步骤"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """验证配置"""
        pass
    
    def get_required_inputs(self) -> List[str]:
        """获取必需的输入参数"""
        return []
    
    def get_outputs(self) -> List[str]:
        """获取输出参数"""
        return []


class TextGenerationStep(WorkflowStep):
    """文本生成步骤"""
    
    def __init__(self, step_id: str, name: str, config: Dict[str, Any]):
        super().__init__(step_id, name, config)
        self.service = GeminiTextService()
    
    def validate_config(self) -> bool:
        required_fields = ["prompt", "model"]
        return all(field in self.config for field in required_fields)
    
    def get_required_inputs(self) -> List[str]:
        return ["prompt"]
    
    def get_outputs(self) -> List[str]:
        return ["text", "usage", "model"]
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        start_time = time.time()
        
        try:
            # 从配置和上下文中获取参数
            prompt = self._resolve_value(self.config.get("prompt", ""), context)
            model = self.config.get("model", "gemini-1.5-flash-002")
            max_tokens = self.config.get("max_tokens", 1000)
            temperature = self.config.get("temperature", 0.7)
            
            from ..services.gemini.models import TextGenerationRequest, GeminiModel
            
            # 转换模型名称
            if isinstance(model, str):
                model_enum = GeminiModel.from_string(model)
            else:
                model_enum = model
            
            request = TextGenerationRequest(
                prompt=prompt,
                model=model_enum,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            response = await self.service.generate_text(request)
            
            execution_time = time.time() - start_time
            
            return StepResult(
                success=True,
                data={
                    "text": response.text,
                    "usage": response.usage,
                    "model": response.model,
                    "finish_reason": response.finish_reason
                },
                metadata={
                    "step_type": "text_generation",
                    "prompt_length": len(prompt),
                    "response_length": len(response.text)
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"文本生成步骤失败: {e}")
            return StepResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def _resolve_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """解析模板值，支持上下文变量替换"""
        if isinstance(value, str):
            # 简单的模板变量替换
            import re
            def replace_var(match):
                var_name = match.group(1)
                return str(context.get(var_name, match.group(0)))
            
            return re.sub(r'\{\{(\w+)\}\}', replace_var, value)
        return value


class ImageGenerationStep(WorkflowStep):
    """图像生成步骤"""
    
    def __init__(self, step_id: str, name: str, config: Dict[str, Any]):
        super().__init__(step_id, name, config)
        self.service = GeminiImageService()
    
    def validate_config(self) -> bool:
        required_fields = ["prompt"]
        return all(field in self.config for field in required_fields)
    
    def get_required_inputs(self) -> List[str]:
        return ["prompt"]
    
    def get_outputs(self) -> List[str]:
        return ["images", "file_paths", "usage"]
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        start_time = time.time()
        
        try:
            # 从配置和上下文中获取参数
            prompt = self._resolve_value(self.config.get("prompt", ""), context)
            model = self.config.get("model", "imagen-3.0-generate-001")
            num_images = self.config.get("num_images", 1)
            aspect_ratio = self.config.get("aspect_ratio", "1:1")
            output_mode = self.config.get("output_mode", "file")
            
            from ..services.gemini.models import ImageGenerationRequest
            
            request = ImageGenerationRequest(
                prompt=prompt,
                model=model,
                num_images=num_images,
                aspect_ratio=aspect_ratio,
                output_mode=output_mode
            )
            
            response = await self.service.generate_image(request)
            
            execution_time = time.time() - start_time
            
            return StepResult(
                success=True,
                data={
                    "images": response.images,
                    "file_paths": response.file_paths,
                    "usage": response.usage,
                    "model": response.model
                },
                metadata={
                    "step_type": "image_generation",
                    "prompt_length": len(prompt),
                    "num_images": num_images
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"图像生成步骤失败: {e}")
            return StepResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def _resolve_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """解析模板值，支持上下文变量替换"""
        if isinstance(value, str):
            import re
            def replace_var(match):
                var_name = match.group(1)
                return str(context.get(var_name, match.group(0)))
            
            return re.sub(r'\{\{(\w+)\}\}', replace_var, value)
        return value


class VideoGenerationStep(WorkflowStep):
    """视频生成步骤"""
    
    def __init__(self, step_id: str, name: str, config: Dict[str, Any]):
        super().__init__(step_id, name, config)
        self.service = KlingVideoService() if get_config().kling else None
    
    def validate_config(self) -> bool:
        if not self.service:
            return False
        required_fields = ["prompt"]
        return all(field in self.config for field in required_fields)
    
    def get_required_inputs(self) -> List[str]:
        return ["prompt"]
    
    def get_outputs(self) -> List[str]:
        return ["video_url", "file_path", "task_id"]
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        if not self.service:
            return StepResult(
                success=False,
                error="Kling service not available"
            )
        
        start_time = time.time()
        
        try:
            # 从配置和上下文中获取参数
            prompt = self._resolve_value(self.config.get("prompt", ""), context)
            image_url = self.config.get("image_url")
            duration = self.config.get("duration", 5)
            aspect_ratio = self.config.get("aspect_ratio", "16:9")
            output_mode = self.config.get("output_mode", "file")
            
            from ..services.kling.models import VideoGenerationRequest
            
            request = VideoGenerationRequest(
                prompt=prompt,
                image_url=image_url,
                duration=duration,
                aspect_ratio=aspect_ratio,
                output_mode=output_mode
            )
            
            response = await self.service.generate_video(request)
            
            execution_time = time.time() - start_time
            
            return StepResult(
                success=True,
                data={
                    "video_url": response.video_url,
                    "file_path": response.file_path,
                    "task_id": response.task_id,
                    "status": response.status
                },
                metadata={
                    "step_type": "video_generation",
                    "prompt_length": len(prompt),
                    "duration": duration
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"视频生成步骤失败: {e}")
            return StepResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def _resolve_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """解析模板值，支持上下文变量替换"""
        if isinstance(value, str):
            import re
            def replace_var(match):
                var_name = match.group(1)
                return str(context.get(var_name, match.group(0)))
            
            return re.sub(r'\{\{(\w+)\}\}', replace_var, value)
        return value


class ConditionStep(WorkflowStep):
    """条件分支步骤"""
    
    def validate_config(self) -> bool:
        return "condition" in self.config
    
    def get_required_inputs(self) -> List[str]:
        return self.config.get("input_vars", [])
    
    def get_outputs(self) -> List[str]:
        return ["condition_result", "branch"]
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        start_time = time.time()
        
        try:
            condition = self.config["condition"]
            result = self._evaluate_condition(condition, context)
            
            # 根据条件结果确定分支
            if result:
                branch = self.config.get("true_branch", "true")
            else:
                branch = self.config.get("false_branch", "false")
            
            execution_time = time.time() - start_time
            
            return StepResult(
                success=True,
                data={
                    "condition_result": result,
                    "branch": branch
                },
                metadata={
                    "step_type": "condition",
                    "condition": condition
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"条件步骤失败: {e}")
            return StepResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        # 简单的条件评估，实际项目中可能需要更复杂的表达式解析器
        try:
            # 替换上下文变量
            import re
            def replace_var(match):
                var_name = match.group(1)
                value = context.get(var_name, None)
                if isinstance(value, str):
                    return f'"{value}"'
                return str(value)
            
            evaluated_condition = re.sub(r'\{\{(\w+)\}\}', replace_var, condition)
            
            # 安全的表达式评估（仅允许基本操作）
            allowed_names = {
                "__builtins__": {},
                "True": True,
                "False": False,
                "None": None,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
            }
            
            result = eval(evaluated_condition, allowed_names)
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"条件评估失败: {e}")
            return False


class ParallelStep(WorkflowStep):
    """并行执行步骤"""
    
    def validate_config(self) -> bool:
        return "steps" in self.config and isinstance(self.config["steps"], list)
    
    def get_required_inputs(self) -> List[str]:
        # 收集所有子步骤的输入
        inputs = []
        for step_config in self.config.get("steps", []):
            step = self._create_step(step_config)
            inputs.extend(step.get_required_inputs())
        return list(set(inputs))
    
    def get_outputs(self) -> List[str]:
        # 收集所有子步骤的输出
        outputs = ["parallel_results"]
        for step_config in self.config.get("steps", []):
            step = self._create_step(step_config)
            outputs.extend(step.get_outputs())
        return list(set(outputs))
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        start_time = time.time()
        
        try:
            steps_config = self.config["steps"]
            max_concurrency = self.config.get("max_concurrency", len(steps_config))
            
            # 创建子步骤
            steps = []
            for i, step_config in enumerate(steps_config):
                step_id = f"{self.step_id}_parallel_{i}"
                step = self._create_step({**step_config, "id": step_id})
                steps.append(step)
            
            # 并行执行步骤
            semaphore = asyncio.Semaphore(max_concurrency)
            
            async def execute_step(step):
                async with semaphore:
                    return await step.execute(context)
            
            results = await asyncio.gather(*[execute_step(step) for step in steps])
            
            execution_time = time.time() - start_time
            
            # 检查是否有失败的步骤
            failed_steps = [r for r in results if not r.success]
            if failed_steps:
                errors = [r.error for r in failed_steps]
                return StepResult(
                    success=False,
                    error=f"并行执行中有 {len(failed_steps)} 个步骤失败: {errors}",
                    data={"results": results},
                    execution_time=execution_time
                )
            
            # 合并结果数据
            combined_data = {"parallel_results": [r.data for r in results]}
            for i, result in enumerate(results):
                if result.data:
                    for key, value in result.data.items():
                        combined_data[f"step_{i}_{key}"] = value
            
            return StepResult(
                success=True,
                data=combined_data,
                metadata={
                    "step_type": "parallel",
                    "num_steps": len(steps),
                    "max_concurrency": max_concurrency
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"并行步骤失败: {e}")
            return StepResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def _create_step(self, step_config: Dict[str, Any]) -> WorkflowStep:
        """根据配置创建步骤实例"""
        step_type = step_config.get("type")
        step_id = step_config.get("id", f"step_{int(time.time())}")
        name = step_config.get("name", step_id)
        config = step_config.get("config", {})
        
        return StepFactory.create_step(step_type, step_id, name, config)


class CustomStep(WorkflowStep):
    """自定义步骤，支持用户定义的执行函数"""
    
    def __init__(self, step_id: str, name: str, config: Dict[str, Any], 
                 execute_func: Optional[Callable] = None):
        super().__init__(step_id, name, config)
        self.execute_func = execute_func
    
    def validate_config(self) -> bool:
        return self.execute_func is not None
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        if not self.execute_func:
            return StepResult(
                success=False,
                error="No execute function provided"
            )
        
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(self.execute_func):
                result = await self.execute_func(context, self.config)
            else:
                result = self.execute_func(context, self.config)
            
            execution_time = time.time() - start_time
            
            return StepResult(
                success=True,
                data=result,
                metadata={"step_type": "custom"},
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"自定义步骤失败: {e}")
            return StepResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )


class StepFactory:
    """步骤工厂类"""
    
    _step_classes = {
        StepType.TEXT_GENERATION: TextGenerationStep,
        StepType.IMAGE_GENERATION: ImageGenerationStep,
        StepType.VIDEO_GENERATION: VideoGenerationStep,
        StepType.CONDITION: ConditionStep,
        StepType.PARALLEL: ParallelStep,
        StepType.CUSTOM: CustomStep
    }
    
    @classmethod
    def create_step(cls, step_type: Union[str, StepType], 
                   step_id: str, name: str, config: Dict[str, Any],
                   **kwargs) -> WorkflowStep:
        """创建步骤实例"""
        if isinstance(step_type, str):
            try:
                step_type = StepType(step_type)
            except ValueError:
                raise WorkflowError(f"不支持的步骤类型: {step_type}")
        
        step_class = cls._step_classes.get(step_type)
        if not step_class:
            raise WorkflowError(f"未找到步骤类型 {step_type} 的实现")
        
        return step_class(step_id, name, config, **kwargs)
    
    @classmethod
    def register_step_type(cls, step_type: StepType, step_class: type):
        """注册新的步骤类型"""
        cls._step_classes[step_type] = step_class