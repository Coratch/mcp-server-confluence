"""本地 Mermaid 渲染器

使用 mermaid-cli (mmdc) 将 Mermaid 代码渲染为图片文件。
如果 mmdc 不可用，回退到在线渲染或代码块显示。
"""
import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MermaidLocalRenderer:
    """本地 Mermaid 渲染器"""

    # Mermaid 代码块正则
    MD_MERMAID_PATTERN = re.compile(r'```mermaid\s*\n(.*?)\n```', re.DOTALL)

    @classmethod
    def check_mmdc_available(cls) -> bool:
        """检查 mermaid-cli (mmdc) 是否可用

        Returns:
            是否可用
        """
        return shutil.which("mmdc") is not None

    @classmethod
    async def render_to_file(
        cls,
        mermaid_code: str,
        output_path: Path,
        format: str = "png",
        theme: str = "default",
        background: str = "white",
        width: int = 800,
        height: int = 600
    ) -> bool:
        """渲染 Mermaid 代码为图片文件

        Args:
            mermaid_code: Mermaid 代码
            output_path: 输出文件路径
            format: 输出格式 (png, svg, pdf)
            theme: 主题 (default, dark, forest, neutral)
            background: 背景色
            width: 宽度
            height: 高度

        Returns:
            是否成功
        """
        if not cls.check_mmdc_available():
            logger.warning("mermaid-cli (mmdc) 不可用，无法本地渲染")
            return False

        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".mmd",
            delete=False,
            encoding="utf-8"
        ) as tmp_input:
            tmp_input.write(mermaid_code)
            tmp_input_path = tmp_input.name

        try:
            # 构建 mmdc 命令
            cmd = [
                "mmdc",
                "-i", tmp_input_path,
                "-o", str(output_path),
                "-t", theme,
                "-b", background,
                "-w", str(width),
                "-H", str(height),
                "--quiet"
            ]

            # 执行渲染
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"mmdc 渲染失败: {stderr.decode('utf-8', errors='ignore')}")
                return False

            logger.info(f"成功渲染 Mermaid 图表到: {output_path}")
            return True

        except Exception as e:
            logger.error(f"渲染 Mermaid 时出错: {e}")
            return False
        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_input_path)
            except:
                pass

    @classmethod
    async def render_all_to_temp(
        cls,
        markdown_content: str,
        temp_dir: Optional[Path] = None,
        format: str = "png"
    ) -> Tuple[str, List[Dict[str, any]]]:
        """渲染所有 Mermaid 代码块为临时图片文件

        Args:
            markdown_content: Markdown 内容
            temp_dir: 临时目录（可选）
            format: 图片格式

        Returns:
            (修改后的 Markdown, 图片信息列表)
        """
        if not cls.check_mmdc_available():
            logger.warning("mermaid-cli 不可用，返回原始内容")
            return markdown_content, []

        # 创建临时目录
        if temp_dir is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="mermaid_"))
        else:
            temp_dir.mkdir(parents=True, exist_ok=True)

        # 查找所有 Mermaid 代码块
        matches = list(cls.MD_MERMAID_PATTERN.finditer(markdown_content))
        if not matches:
            return markdown_content, []

        logger.info(f"找到 {len(matches)} 个 Mermaid 代码块需要渲染")

        # 渲染每个代码块
        image_info = []
        replacements = []

        for i, match in enumerate(matches):
            mermaid_code = match.group(1).strip()
            
            # 生成文件名
            image_filename = f"mermaid_diagram_{i + 1}.{format}"
            image_path = temp_dir / image_filename

            # 渲染图片
            success = await cls.render_to_file(
                mermaid_code,
                image_path,
                format=format
            )

            if success and image_path.exists():
                # 记录图片信息
                info = {
                    "index": i + 1,
                    "code": mermaid_code,
                    "path": str(image_path),
                    "filename": image_filename,
                    "size": image_path.stat().st_size
                }
                image_info.append(info)

                # 准备替换内容
                # 使用占位符，稍后替换为实际的附件 URL
                placeholder = f"[[MERMAID_IMAGE_{i + 1}]]"
                replacements.append((match.span(), placeholder))

                logger.info(
                    f"渲染 Mermaid 图表 {i + 1}: "
                    f"{image_filename} ({info['size']} bytes)"
                )
            else:
                # 渲染失败，保留原始代码块
                logger.warning(f"Mermaid 图表 {i + 1} 渲染失败，保留原始代码")
                replacements.append((match.span(), match.group(0)))

        # 执行替换（从后往前，避免偏移问题）
        result = markdown_content
        for (start, end), replacement in reversed(replacements):
            result = result[:start] + replacement + result[end:]

        return result, image_info

    @classmethod
    async def render_with_fallback(
        cls,
        mermaid_code: str,
        output_dir: Path,
        index: int = 1
    ) -> Dict[str, any]:
        """渲染 Mermaid 代码，带降级策略

        Args:
            mermaid_code: Mermaid 代码
            output_dir: 输出目录
            index: 图表索引

        Returns:
            渲染结果信息
        """
        result = {
            "success": False,
            "method": None,
            "code": mermaid_code,
            "index": index
        }

        # 尝试本地渲染
        if cls.check_mmdc_available():
            output_path = output_dir / f"mermaid_{index}.png"
            success = await cls.render_to_file(
                mermaid_code,
                output_path
            )

            if success:
                result.update({
                    "success": True,
                    "method": "local",
                    "path": str(output_path),
                    "filename": output_path.name,
                    "size": output_path.stat().st_size
                })
                return result

        # 降级到在线渲染（使用 mermaid.ink）
        from .mermaid_to_image import MermaidToImageConverter
        
        image_url = MermaidToImageConverter.encode_mermaid(mermaid_code)
        result.update({
            "success": True,
            "method": "online",
            "url": image_url
        })

        return result

    @classmethod
    def install_instructions(cls) -> str:
        """获取安装说明

        Returns:
            安装 mermaid-cli 的说明
        """
        return """
要启用本地 Mermaid 渲染，请安装 mermaid-cli：

1. 确保已安装 Node.js (版本 >= 14)
2. 全局安装 mermaid-cli：
   
   npm install -g @mermaid-js/mermaid-cli
   
   或使用 yarn：
   
   yarn global add @mermaid-js/mermaid-cli
   
3. 验证安装：
   
   mmdc --version
   
4. （可选）安装 Puppeteer 依赖：
   
   如果遇到 Chromium 相关错误，可能需要安装系统依赖：
   
   # macOS
   brew install chromium
   
   # Ubuntu/Debian
   sudo apt-get install chromium-browser
   
   # CentOS/RHEL
   sudo yum install chromium

更多信息请访问：https://github.com/mermaid-js/mermaid-cli
"""