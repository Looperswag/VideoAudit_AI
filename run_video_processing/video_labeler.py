# run_video_processing/video_labeler.py
import os
import time
import json
import shutil
import re

# 使用相对导入来引入同包下的模块
from . import config
from .gemini_utils import setup_gemini_client, label_video_with_gemini
from .video_utils import get_video_duration, format_duration_human
from .report_generator import generate_html_report

def label_entire_videos(input_folder, output_folder,
                        project_id=config.DEFAULT_GEMINI_PROJECT_ID,
                        location=config.DEFAULT_GEMINI_LOCATION):
    """
    对输入文件夹中的每个完整视频进行标注，并将标注后的视频保存到输出文件夹。
    """
    start_time_processing = time.time()

    if not os.path.exists(input_folder):
        print(f"输入文件夹不存在：{input_folder}")
        return
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    gemini_client = None
    try:
        gemini_client = setup_gemini_client(project_id, location)
        print(f"Gemini API 客户端设置成功 (Project: {project_id}, Location: {location})")
    except Exception as e:
        print(f"Gemini API 客户端设置失败: {e}。处理将继续，但无法进行视频标注。")

    results = {} # 用于存储所有视频的处理结果

    for filename in os.listdir(input_folder):
        if filename.startswith('.') or filename.startswith('._'):
            print(f"跳过隐藏或元数据文件: {filename}")
            continue

        if os.path.splitext(filename)[1].lower() in config.VIDEO_EXTENSIONS:
            video_path = os.path.join(input_folder, filename)
            print(f"\n--- 开始处理视频文件：{video_path} ---")

            original_base_name = os.path.splitext(filename)[0]
            
            result_entry = {
                "status": "failed",
                "error": "未知错误",
                "processed_video_info": None, 
                "output_dir": ""
            }

            if not os.path.isfile(video_path):
                print(f"错误：文件不存在或无法访问: {video_path}")
                result_entry["error"] = "文件不存在或无法访问"
                results[filename] = result_entry
                continue
            
            try:
                file_size = os.path.getsize(video_path)
                if file_size == 0:
                    print(f"错误：文件大小为0，跳过处理: {video_path}")
                    result_entry["error"] = "文件大小为0"
                    results[filename] = result_entry
                    continue
                print(f"视频信息: {video_path} (大小: {file_size/1024/1024:.2f} MB)")
            except OSError as e:
                print(f"错误：无法获取文件大小 {video_path}: {e}")
                result_entry["error"] = f"无法获取文件大小: {e}"
                results[filename] = result_entry
                continue

            try:
                # 为当前视频创建独立的输出子文件夹
                video_specific_output_folder = os.path.join(output_folder, original_base_name)
                if not os.path.exists(video_specific_output_folder):
                    os.makedirs(video_specific_output_folder)
                result_entry["output_dir"] = video_specific_output_folder
                
                video_duration = get_video_duration(video_path)
                raw_gemini_label = "未标注"
                final_score = "不合格" # 新增：最终得分，默认为不合格

                if gemini_client:
                    print(f"对视频 {filename} 进行 Gemini 标注...")
                    raw_gemini_label = label_video_with_gemini(gemini_client, video_path)
                
                # 新增：根据 Gemini 标签计算最终得分
                # Gemini 标签格式应为 "标签1结果-标签2结果-标签3结果-标签4结果"
                if raw_gemini_label != "标签生成失败" and raw_gemini_label != "未标注":
                    labels = raw_gemini_label.split('-')
                    if len(labels) == 4 and all(label.strip() == "合格" for label in labels):
                        final_score = "合格"
                    # 其他情况（包括标签格式不符或有不合格项）final_score 保持 "不合格"
                
                # 文件名标签生成逻辑 (保持现有逻辑，您可能需要根据实际Gemini输出调整)
                label_for_filename = "未定义标签"
                if raw_gemini_label != "标签生成失败" and raw_gemini_label != "未标注":
                    # 注意：此处的解析逻辑可能与您gemini_utils.py中prompt定义的输出格式 “合格-合格-不合格-合格” 不完全匹配
                    # 如果您希望文件名基于这四个标准，需要调整这里的components解析
                    components = raw_gemini_label.split('-', 3) 
                    filename_label_parts = []
                    if len(components) > 0 and components[0].strip() in ["女性", "男性", "无人物", "合格", "不合格"]: # 扩展以尝试适应
                        filename_label_parts.append(components[0].strip())
                    if len(components) > 1 and components[1].strip() in ["有产品", "无产品", "合格", "不合格"]:
                        filename_label_parts.append(components[1].strip())
                    if len(components) > 2 and components[2].strip():
                        # 假设第三部分之后的是描述性文本，如果Gemini输出固定为4个“合格/不合格”，这部分可能为空或不适用
                        feature_desc = components[2].strip()[:50] 
                        feature_desc = re.sub(r'[^\w\s\-_]', '', feature_desc).strip()
                        if feature_desc:
                            filename_label_parts.append(feature_desc)
                    
                    if filename_label_parts:
                        label_for_filename = "-".join(filename_label_parts)
                    elif raw_gemini_label: # 如果上述解析不成功，使用原始标签的清理版本
                        label_for_filename = re.sub(r'[^\w\s\-_]', '', raw_gemini_label[:70]).strip()

                sanitized_label_str = "".join(c if c.isalnum() or c in " -_()[]" else "_" for c in label_for_filename).strip("_ ")
                sanitized_label_str = "_".join(filter(None, sanitized_label_str.replace(" ", "_").split('_')))
                if not sanitized_label_str: sanitized_label_str = "labeled_video"
                
                base_name_part = original_base_name[:80]
                label_part_for_name = sanitized_label_str[:100]

                final_filename = f"{base_name_part}-标签-{label_part_for_name}{os.path.splitext(filename)[1]}"
                final_video_path = os.path.join(video_specific_output_folder, final_filename)
                
                shutil.copy2(video_path, final_video_path)
                print(f"视频已标注并保存: {final_video_path}")

                # 新增：计算视频相对于主输出文件夹的相对路径，用于HTML报告
                relative_video_path_for_report = os.path.relpath(final_video_path, output_folder)
                # 确保在Windows上也是正斜杠 (web路径通常用/)
                relative_video_path_for_report = relative_video_path_for_report.replace(os.sep, '/')


                result_entry["status"] = "success"
                result_entry["processed_video_info"] = {
                    "original_filename": filename,
                    "new_filename": final_filename,
                    "label": raw_gemini_label, # Gemini的原始标签
                    "duration": video_duration,
                    "final_score": final_score, # 新增：最终得分
                    "relative_video_path": relative_video_path_for_report # 新增：HTML报告用的视频相对路径
                }
                results[filename] = result_entry
                
                if gemini_client: time.sleep(1) # 避免API速率限制

            except Exception as e:
                print(f"处理视频 {filename} 时发生错误：{e}")
                import traceback
                traceback.print_exc()
                result_entry["error"] = str(e)
                results[filename] = result_entry
            finally:
                print(f"--- 视频文件 {filename} 处理结束 ---")

    end_time_processing = time.time()
    
    if results:
        generate_html_report(results, output_folder, start_time_processing, end_time_processing)

    summary_path = os.path.join(output_folder, "processing_summary.json")
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"\n处理结果摘要已保存到: {summary_path}")
    except Exception as e:
        print(f"错误：无法保存处理结果摘要到 {summary_path}: {e}")

    total_duration_seconds = end_time_processing - start_time_processing
    formatted_total_duration = format_duration_human(total_duration_seconds) 
    print(f"\n所有视频处理完成！总处理时间: {formatted_total_duration}")
    print(f"所有结果保存在: {output_folder}")