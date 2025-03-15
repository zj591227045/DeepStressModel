"""
结果导出插件，用于将跑分结果导出为不同格式
"""
import os
import json
import csv
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.benchmark.plugin_manager import BenchmarkPlugin
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("result_exporter_plugin")

class ResultExporterPlugin(BenchmarkPlugin):
    """
    结果导出插件类，用于将跑分结果导出为不同格式
    """
    
    def __init__(self, config):
        """
        初始化插件
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.name = "result_exporter"
        self.version = "1.0.0"
        self.description = "将跑分结果导出为不同格式"
        self.author = "DeepStressModel团队"
        
        # 导出目录
        self.export_dir = os.path.join(os.getcwd(), "data", "benchmark", "exports")
        os.makedirs(self.export_dir, exist_ok=True)
        
        # 支持的导出格式
        self.supported_formats = ["json", "csv", "markdown", "html"]
        
        # 当前结果
        self.current_result = None
        
        logger.info("结果导出插件初始化完成")
    
    def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 确保导出目录存在
            os.makedirs(self.export_dir, exist_ok=True)
            
            # 读取配置
            self.auto_export = self.config.get("benchmark.result_exporter.auto_export", False)
            self.default_format = self.config.get("benchmark.result_exporter.default_format", "json")
            
            # 验证默认格式
            if self.default_format not in self.supported_formats:
                logger.warning(f"不支持的导出格式: {self.default_format}，将使用json格式")
                self.default_format = "json"
            
            logger.info(f"结果导出插件初始化成功，自动导出: {self.auto_export}，默认格式: {self.default_format}")
            return True
        except Exception as e:
            logger.error(f"结果导出插件初始化失败: {str(e)}")
            return False
    
    def cleanup(self) -> bool:
        """
        清理插件资源
        
        Returns:
            bool: 清理是否成功
        """
        try:
            # 清理当前结果
            self.current_result = None
            
            logger.info("结果导出插件资源清理完成")
            return True
        except Exception as e:
            logger.error(f"结果导出插件资源清理失败: {str(e)}")
            return False
    
    def on_benchmark_start(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分开始事件处理
        
        Args:
            config: 跑分配置
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 清理当前结果
        self.current_result = None
        
        logger.info("跑分开始，准备导出结果")
        return {"status": "success", "message": "准备导出结果"}
    
    def on_benchmark_complete(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分完成事件处理
        
        Args:
            result: 跑分结果
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 保存当前结果
        self.current_result = result
        
        # 如果配置了自动导出，则导出结果
        if self.auto_export:
            export_path = self.export_result(self.default_format)
            return {
                "status": "success",
                "message": f"结果已自动导出为{self.default_format}格式",
                "export_path": export_path
            }
        
        logger.info("跑分完成，结果已保存")
        return {"status": "success", "message": "结果已保存，可以手动导出"}
    
    def export_result(self, format_type: str = None, output_path: str = None) -> str:
        """
        导出结果
        
        Args:
            format_type: 导出格式，支持json、csv、markdown、html
            output_path: 输出路径，如果为None则使用默认路径
            
        Returns:
            str: 导出文件路径，如果导出失败则返回空字符串
        """
        if not self.current_result:
            logger.error("没有可导出的结果")
            return ""
        
        # 使用默认格式
        if not format_type:
            format_type = self.default_format
        
        # 验证格式
        if format_type not in self.supported_formats:
            logger.error(f"不支持的导出格式: {format_type}")
            return ""
        
        # 生成输出路径
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"benchmark_result_{timestamp}.{format_type}"
            output_path = os.path.join(self.export_dir, filename)
        
        try:
            # 根据格式导出结果
            if format_type == "json":
                return self._export_json(output_path)
            elif format_type == "csv":
                return self._export_csv(output_path)
            elif format_type == "markdown":
                return self._export_markdown(output_path)
            elif format_type == "html":
                return self._export_html(output_path)
            else:
                logger.error(f"不支持的导出格式: {format_type}")
                return ""
        except Exception as e:
            logger.error(f"导出结果失败: {str(e)}")
            return ""
    
    def _export_json(self, output_path: str) -> str:
        """
        导出为JSON格式
        
        Args:
            output_path: 输出路径
            
        Returns:
            str: 导出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"结果已导出为JSON格式: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"导出JSON格式失败: {str(e)}")
            return ""
    
    def _export_csv(self, output_path: str) -> str:
        """
        导出为CSV格式
        
        Args:
            output_path: 输出路径
            
        Returns:
            str: 导出文件路径
        """
        try:
            # 提取关键信息
            result = self.current_result
            
            # 基本信息
            basic_info = {
                "设备ID": result.get("device_id", ""),
                "设备名称": result.get("nickname", ""),
                "数据集版本": result.get("dataset_version", ""),
                "模型": result.get("model", ""),
                "精度": result.get("precision", ""),
                "开始时间": result.get("start_time", ""),
                "结束时间": result.get("end_time", ""),
                "总耗时(秒)": result.get("total_duration", 0)
            }
            
            # 性能指标
            metrics = result.get("metrics", {})
            metrics_info = {
                "吞吐量": metrics.get("throughput", 0),
                "延迟(毫秒)": metrics.get("latency", 0),
                "GPU利用率(%)": metrics.get("gpu_utilization", 0),
                "内存利用率(%)": metrics.get("memory_utilization", 0)
            }
            
            # 系统信息
            system_info = result.get("system_info", {})
            system_info_flat = {
                "操作系统": system_info.get("os", ""),
                "Python版本": system_info.get("python_version", ""),
                "CPU型号": system_info.get("cpu", {}).get("brand", ""),
                "CPU核心数": system_info.get("cpu", {}).get("cores", 0),
                "CPU线程数": system_info.get("cpu", {}).get("threads", 0),
                "内存总量(字节)": system_info.get("memory", {}).get("total", 0),
                "可用内存(字节)": system_info.get("memory", {}).get("available", 0),
                "GPU数量": len(system_info.get("gpus", []))
            }
            
            # 合并所有信息
            all_info = {**basic_info, **metrics_info, **system_info_flat}
            
            # 写入CSV文件
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(all_info.keys())
                writer.writerow(all_info.values())
            
            logger.info(f"结果已导出为CSV格式: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"导出CSV格式失败: {str(e)}")
            return ""
    
    def _export_markdown(self, output_path: str) -> str:
        """
        导出为Markdown格式
        
        Args:
            output_path: 输出路径
            
        Returns:
            str: 导出文件路径
        """
        try:
            result = self.current_result
            
            # 生成Markdown内容
            markdown_content = f"""# DeepStressModel 跑分结果

## 基本信息

- **设备ID**: {result.get("device_id", "")}
- **设备名称**: {result.get("nickname", "")}
- **数据集版本**: {result.get("dataset_version", "")}
- **模型**: {result.get("model", "")}
- **精度**: {result.get("precision", "")}
- **开始时间**: {result.get("start_time", "")}
- **结束时间**: {result.get("end_time", "")}
- **总耗时**: {result.get("total_duration", 0):.2f} 秒

## 性能指标

| 指标 | 值 |
|------|-----|
| 吞吐量 | {result.get("metrics", {}).get("throughput", 0):.2f} |
| 延迟 | {result.get("metrics", {}).get("latency", 0):.2f} 毫秒 |
| GPU利用率 | {result.get("metrics", {}).get("gpu_utilization", 0):.2f}% |
| 内存利用率 | {result.get("metrics", {}).get("memory_utilization", 0):.2f}% |

## 系统信息

### 基本系统信息

- **操作系统**: {result.get("system_info", {}).get("os", "")}
- **Python版本**: {result.get("system_info", {}).get("python_version", "")}

### CPU信息

- **CPU型号**: {result.get("system_info", {}).get("cpu", {}).get("brand", "")}
- **CPU核心数**: {result.get("system_info", {}).get("cpu", {}).get("cores", 0)}
- **CPU线程数**: {result.get("system_info", {}).get("cpu", {}).get("threads", 0)}

### 内存信息

- **内存总量**: {self._format_bytes(result.get("system_info", {}).get("memory", {}).get("total", 0))}
- **可用内存**: {self._format_bytes(result.get("system_info", {}).get("memory", {}).get("available", 0))}

### GPU信息

"""
            
            # 添加GPU信息
            gpus = result.get("system_info", {}).get("gpus", [])
            for i, gpu in enumerate(gpus):
                markdown_content += f"""#### GPU {i+1}

- **型号**: {gpu.get("name", "")}
- **显存总量**: {self._format_bytes(gpu.get("memory_total", 0))}
- **显存使用**: {self._format_bytes(gpu.get("memory_used", 0))}
- **利用率**: {gpu.get("utilization", 0):.2f}%

"""
            
            # 添加排名信息
            if "rankings" in result:
                markdown_content += """## 排名信息

| 排名 | 设备 | 得分 | 相对性能 |
|------|------|------|----------|
"""
                
                for rank in result.get("rankings", []):
                    markdown_content += f"| {rank.get('rank', '')} | {rank.get('nickname', '')} | {rank.get('score', 0):.2f} | {rank.get('relative_performance', 0):.2f}% |\n"
            
            # 写入Markdown文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"结果已导出为Markdown格式: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"导出Markdown格式失败: {str(e)}")
            return ""
    
    def _export_html(self, output_path: str) -> str:
        """
        导出为HTML格式
        
        Args:
            output_path: 输出路径
            
        Returns:
            str: 导出文件路径
        """
        try:
            result = self.current_result
            
            # 生成HTML内容
            html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DeepStressModel 跑分结果</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3, h4 {{
            color: #2c3e50;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .info-section {{
            margin-bottom: 30px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        .info-card {{
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            background-color: #f9f9f9;
        }}
        .info-card h3 {{
            margin-top: 0;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }}
        .info-item {{
            margin-bottom: 8px;
        }}
        .info-label {{
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <h1>DeepStressModel 跑分结果</h1>
    
    <div class="info-section">
        <h2>基本信息</h2>
        <div class="info-grid">
            <div class="info-card">
                <h3>测试信息</h3>
                <div class="info-item">
                    <span class="info-label">设备ID:</span> {result.get("device_id", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">设备名称:</span> {result.get("nickname", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">数据集版本:</span> {result.get("dataset_version", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">模型:</span> {result.get("model", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">精度:</span> {result.get("precision", "")}
                </div>
            </div>
            
            <div class="info-card">
                <h3>时间信息</h3>
                <div class="info-item">
                    <span class="info-label">开始时间:</span> {result.get("start_time", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">结束时间:</span> {result.get("end_time", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">总耗时:</span> {result.get("total_duration", 0):.2f} 秒
                </div>
            </div>
        </div>
    </div>
    
    <div class="info-section">
        <h2>性能指标</h2>
        <table>
            <tr>
                <th>指标</th>
                <th>值</th>
            </tr>
            <tr>
                <td>吞吐量</td>
                <td>{result.get("metrics", {}).get("throughput", 0):.2f}</td>
            </tr>
            <tr>
                <td>延迟</td>
                <td>{result.get("metrics", {}).get("latency", 0):.2f} 毫秒</td>
            </tr>
            <tr>
                <td>GPU利用率</td>
                <td>{result.get("metrics", {}).get("gpu_utilization", 0):.2f}%</td>
            </tr>
            <tr>
                <td>内存利用率</td>
                <td>{result.get("metrics", {}).get("memory_utilization", 0):.2f}%</td>
            </tr>
        </table>
    </div>
    
    <div class="info-section">
        <h2>系统信息</h2>
        <div class="info-grid">
            <div class="info-card">
                <h3>基本系统信息</h3>
                <div class="info-item">
                    <span class="info-label">操作系统:</span> {result.get("system_info", {}).get("os", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">Python版本:</span> {result.get("system_info", {}).get("python_version", "")}
                </div>
            </div>
            
            <div class="info-card">
                <h3>CPU信息</h3>
                <div class="info-item">
                    <span class="info-label">CPU型号:</span> {result.get("system_info", {}).get("cpu", {}).get("brand", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">CPU核心数:</span> {result.get("system_info", {}).get("cpu", {}).get("cores", 0)}
                </div>
                <div class="info-item">
                    <span class="info-label">CPU线程数:</span> {result.get("system_info", {}).get("cpu", {}).get("threads", 0)}
                </div>
            </div>
            
            <div class="info-card">
                <h3>内存信息</h3>
                <div class="info-item">
                    <span class="info-label">内存总量:</span> {self._format_bytes(result.get("system_info", {}).get("memory", {}).get("total", 0))}
                </div>
                <div class="info-item">
                    <span class="info-label">可用内存:</span> {self._format_bytes(result.get("system_info", {}).get("memory", {}).get("available", 0))}
                </div>
            </div>
        </div>
    </div>
    
    <div class="info-section">
        <h2>GPU信息</h2>
        <div class="info-grid">
"""
            
            # 添加GPU信息
            gpus = result.get("system_info", {}).get("gpus", [])
            for i, gpu in enumerate(gpus):
                html_content += f"""
            <div class="info-card">
                <h3>GPU {i+1}</h3>
                <div class="info-item">
                    <span class="info-label">型号:</span> {gpu.get("name", "")}
                </div>
                <div class="info-item">
                    <span class="info-label">显存总量:</span> {self._format_bytes(gpu.get("memory_total", 0))}
                </div>
                <div class="info-item">
                    <span class="info-label">显存使用:</span> {self._format_bytes(gpu.get("memory_used", 0))}
                </div>
                <div class="info-item">
                    <span class="info-label">利用率:</span> {gpu.get("utilization", 0):.2f}%
                </div>
            </div>
"""
            
            html_content += """
        </div>
    </div>
"""
            
            # 添加排名信息
            if "rankings" in result:
                html_content += """
    <div class="info-section">
        <h2>排名信息</h2>
        <table>
            <tr>
                <th>排名</th>
                <th>设备</th>
                <th>得分</th>
                <th>相对性能</th>
            </tr>
"""
                
                for rank in result.get("rankings", []):
                    html_content += f"""
            <tr>
                <td>{rank.get('rank', '')}</td>
                <td>{rank.get('nickname', '')}</td>
                <td>{rank.get('score', 0):.2f}</td>
                <td>{rank.get('relative_performance', 0):.2f}%</td>
            </tr>
"""
                
                html_content += """
        </table>
    </div>
"""
            
            html_content += """
    <footer>
        <p>生成时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
        <p>DeepStressModel 跑分工具</p>
    </footer>
</body>
</html>
"""
            
            # 写入HTML文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"结果已导出为HTML格式: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"导出HTML格式失败: {str(e)}")
            return ""
    
    def _format_bytes(self, bytes_value: int) -> str:
        """
        格式化字节数
        
        Args:
            bytes_value: 字节数
            
        Returns:
            str: 格式化后的字符串
        """
        if bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024 * 1024:
            return f"{bytes_value / 1024:.2f} KB"
        elif bytes_value < 1024 * 1024 * 1024:
            return f"{bytes_value / (1024 * 1024):.2f} MB"
        else:
            return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB" 