# run_video_processing/report_generator.py
import os
from datetime import datetime
from .video_utils import format_duration_human
import html # 用于HTML转义，防止XSS

def generate_html_report(results, output_dir, start_time, end_time):
    """生成HTML处理报告 (针对完整视频打标，增加最终得分和视频预览)"""
    html_path = os.path.join(output_dir, "processing_report.html")
    
    total_processing_duration_seconds = end_time - start_time
    formatted_total_processing_duration = format_duration_human(total_processing_duration_seconds)
    
    start_time_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
    end_time_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>视频标注处理报告</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; color: #333; }}
            .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }}
            h1, h2, h3, h4 {{ color: #333; }}
            .video-item {{ margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            .success {{ border-left: 5px solid #4CAF50; }}
            .failed {{ border-left: 5px solid #F44336; }}
            .summary {{ margin-bottom: 30px; padding: 15px; background-color: #e8f5e9; border-radius: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 15px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; word-wrap: break-word; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            .time-info {{ background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .video-player-container {{ margin-top: 15px; margin-bottom: 10px; }}
            .video-player-container video {{ 
                max-width: 100%; 
                height: auto; 
                border-radius: 4px; 
                border: 1px solid #ccc; 
            }}
            .status-合格 {{ color: green; font-weight: bold; }}
            .status-不合格 {{ color: red; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>视频标注处理报告</h1>
            
            <div class="time-info">
                <h3>处理时间信息</h3>
                <p>开始时间: {start_time_str}</p>
                <p>结束时间: {end_time_str}</p>
                <p>总处理时长: {formatted_total_processing_duration}</p>
            </div>
            
            <div class="summary">
                <h2>处理摘要</h2>
                <p>总视频数: {len(results)}</p>
                <p>成功处理: {sum(1 for r in results.values() if r['status'] == 'success')}</p>
                <p>处理失败: {sum(1 for r in results.values() if r['status'] == 'failed')}</p>
            </div>
            
            <h2>视频处理详情</h2>
    """
    
    for video_name_orig, result in results.items(): # video_name_orig 是原始文件名
        status_class_html = "success" if result["status"] == "success" else "failed"
        video_name_html = html.escape(video_name_orig)
        html_content += f"""
            <div class="video-item {status_class_html}">
                <h3>原始视频: {video_name_html}</h3>
                <p>处理状态: <span class="status-{result["status"]}">{html.escape(result["status"])}</span></p>
        """
        
        if result["status"] == "success" and result.get("processed_video_info"):
            video_info = result["processed_video_info"]
            html_content += """
                <h4>已处理视频信息:</h4>
                <table>
                    <tr><th>项目</th><th>详情</th></tr>
            """
            try:
                duration = video_info.get("duration", 0.0)
                if isinstance(duration, (int, float)):
                    formatted_duration_video = f"{duration:.2f} 秒"
                else:
                    formatted_duration_video = str(duration) # Fallback
            except (ValueError, TypeError):
                formatted_duration_video = "未知"

            gemini_label_html = html.escape(video_info.get("label", "未标注"))
            # 新增：获取并格式化最终得分
            final_score = video_info.get("final_score", "不合格")
            final_score_class = "status-合格" if final_score == "合格" else "status-不合格"
            final_score_html = f'<span class="{final_score_class}">{html.escape(final_score)}</span>'
            
            new_filename_html = html.escape(video_info.get("new_filename", "未知"))

            html_content += f"""
                    <tr><td>Gemini 标签</td><td>{gemini_label_html}</td></tr>
                    <tr><td>最终得分</td><td>{final_score_html}</td></tr>
                    <tr><td>新文件名</td><td>{new_filename_html}</td></tr>
                    <tr><td>时长</td><td>{formatted_duration_video}</td></tr>
            """
            html_content += "</table>"
            
            # 新增：视频播放器
            relative_video_path = video_info.get("relative_video_path")
            if relative_video_path:
                # 路径已经被处理成用 '/' 分隔
                safe_video_path = html.escape(relative_video_path) 
                
                # 从新文件名确定MIME类型
                new_filename_for_ext = video_info.get("new_filename", "")
                video_ext = ""
                if new_filename_for_ext:
                    video_ext = os.path.splitext(new_filename_for_ext)[1].lower()
                
                mime_type = "video/mp4" # 默认MIME类型
                if video_ext == ".mp4": mime_type = "video/mp4"
                elif video_ext == ".webm": mime_type = "video/webm"
                elif video_ext == ".ogv": mime_type = "video/ogg"
                elif video_ext: mime_type = f"video/{video_ext[1:]}" # 其他类型尝试直接使用

                html_content += f"""
                <div class="video-player-container">
                    <h4>视频预览:</h4>
                    <video width="560" height="315" controls preload="metadata">
                        <source src="{safe_video_path}" type="{mime_type}">
                        您的浏览器不支持播放此视频。尝试的视频类型: {html.escape(mime_type)}
                    </video>
                </div>
                """
            
            output_dir_display = html.escape(result.get("output_dir", "未知"))
            html_content += f"""
                <p>已保存到处理子目录: {output_dir_display}</p>
            """

        elif result["status"] == "failed":
            error_message_html = html.escape(result.get("error", "未知错误"))
            html_content += f"""
                <p>错误信息: {error_message_html}</p>
            """
        
        html_content += "</div>" # video-item
    
    html_content += """
        </div> <!-- container -->
    </body>
    </html>
    """
    
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML报告已生成: {html_path}")
    except Exception as e:
        print(f"生成HTML报告失败: {e}")