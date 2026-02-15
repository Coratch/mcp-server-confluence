"""Mermaid 本地渲染器"""
import os
import subprocess
import tempfile
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MermaidRenderer:
    """使用 mermaid-cli 本地渲染 Mermaid 图表"""

    @staticmethod
    def is_available() -> bool:
        """检查 mermaid-cli 是否可用"""
        try:
            result = subprocess.run(
                ['mmdc', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def render_to_png(mermaid_code: str, output_path: Optional[str] = None) -> Optional[str]:
        """渲染 Mermaid 代码为 PNG 图片

        Args:
            mermaid_code: Mermaid 代码
            output_path: 输出文件路径，如果为 None 则使用临时文件

        Returns:
            生成的 PNG 文件路径，失败返回 None
        """
        if not MermaidRenderer.is_available():
            logger.warning("mermaid-cli 不可用，无法渲染图表")
            return None

        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.mmd',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(mermaid_code)
            input_file = f.name

        # 确定输出文件路径
        if output_path is None:
            output_path = input_file.replace('.mmd', '.png')

        try:
            # 使用 mmdc 渲染
            result = subprocess.run(
                ['mmdc', '-i', input_file, '-o', output_path, '-b', 'transparent'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Mermaid 图表渲染成功: {output_path}")
                return output_path
            else:
                logger.error(f"Mermaid 渲染失败: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Mermaid 渲染异常: {e}")
            return None

        finally:
            # 清理临时输入文件
            if os.path.exists(input_file):
                os.remove(input_file)
