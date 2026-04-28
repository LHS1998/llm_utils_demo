"""
工具执行器基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ToolExecutor(ABC):
    """工具执行器基类"""
    
    def __init__(self, timeout: int = 30):
        """
        初始化工具执行器
        
        Args:
            timeout: 执行超时时间（秒），默认 30 秒
        """
        self.timeout = timeout
    
    @abstractmethod
    def execute(self, code: str, working_dir: Optional[str] = None, 
                env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        执行代码
        
        Args:
            code: 要执行的代码
            working_dir: 工作目录（可选）
            env_vars: 环境变量（可选）
        
        Returns:
            包含执行结果的字典：
            {
                "success": bool,
                "output": str,
                "error": str,
                "execution_time": float
            }
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查工具是否可用"""
        pass
    
    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """获取工具定义（用于 DeepSeek API）"""
        pass

