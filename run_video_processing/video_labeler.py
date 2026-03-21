"""
Video labeling orchestration — processes a folder of videos through Gemini AI
and generates structured HTML/JSON reports.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

from run_video_processing import config
from run_video_processing.gemini_utils import (
    GeminiError,
    setup_gemini_client,
    label_video_with_gemini,
)
from run_video_processing.video_utils import get_video_duration, format_duration_human
from run_video_processing.report_generator import generate_html_report

# 隐藏文件/元数据文件过滤
_HIDDEN_RE = re.compile(r"^\.|^\._")
_SUPPORTED_EXTENSIONS = frozenset(
    ext.lower() for ext in config.VIDEO_EXTENSIONS
)


def _skip_hidden(filename: str) -> bool:
    return bool(_HIDDEN_RE.match(filename))


def _is_video(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in _SUPPORTED_EXTENSIONS


def _sanitize_filename_part(text: str, max_len: int = 80) -> str:
    """Return a filename-safe string, stripped and truncated."""
    cleaned = re.sub(r"[^\w\s\-_()\[\]]", "_", text).strip("_ ")
    return cleaned[:max_len]


def _parse_gemini_label(raw: str) -> tuple[str, str]:
    """Parse Gemini raw response into (display_label, final_score).

    Gemini 响应格式：合格/不合格-合格/不合格-合格/不合格-合格/不合格
    Returns (display_string, final_score) — final_score is "合格" or "不合格".
    """
    if not raw or raw in ("标签生成失败", "未标注"):
        return raw, "不合格"

    parts = [p.strip() for p in raw.split("-")]
    if len(parts) != 4:
        # 格式不符，降级为不合格
        return raw, "不合格"

    all_pass = all(p in ("合格", "不合格") for p in parts)
    if not all_pass:
        return raw, "不合格"

    final = "合格" if all(p == "合格" for p in parts) else "不合格"

    # Human-readable display: 环境-功能-文案-品牌
    dim_names = ["环境", "功能", "文案", "品牌"]
    display = " / ".join(f"{dim_names[i]}:{parts[i]}" for i in range(4))
    return display, final


def _build_output_filename(
    original_name: str,
    display_label: str,
    ext: str,
) -> str:
    base = original_name[:80]
    label_part = _sanitize_filename_part(display_label, max_len=100)
    if not label_part:
        label_part = "labeled"
    return f"{base}-标签-{label_part}{ext}"


def label_entire_videos(
    input_folder: str | Path,
    output_folder: str | Path,
    project_id: str = config.DEFAULT_GEMINI_PROJECT_ID,
    location: str = config.DEFAULT_GEMINI_LOCATION,
) -> dict:
    """Process all videos in *input_folder*, write labelled copies to *output_folder*.

    Args:
        input_folder: Directory containing source videos.
        output_folder: Root output directory (one subfolder per video is created).
        project_id: Google Cloud project ID for Vertex AI.
        location: Google Cloud region.

    Returns:
        Summary dict with statistics.
    """
    start_time = time.time()

    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    if not input_folder.exists():
        print(f"[ERROR] 输入文件夹不存在：{input_folder}")
        return {"success": False, "results": {}}

    output_folder.mkdir(parents=True, exist_ok=True)

    # ── Gemini 客户端初始化（一次） ────────────────────────────
    gemini_client = None
    try:
        gemini_client = setup_gemini_client(project_id, location)
        print(f"[INFO] Gemini 客户端就绪 (project={project_id}, location={location})")
    except GeminiError as e:
        print(f"[WARN] Gemini 客户端初始化失败: {e} — 继续跳过 AI 标注")

    # ── 扫描文件（提前过滤非法文件） ─────────────────────────
    raw_files = os.listdir(input_folder)
    video_files = [f for f in raw_files if not _skip_hidden(f) and _is_video(f)]
    skipped = len(raw_files) - len(video_files)

    print(f"[INFO] 发现 {len(video_files)} 个视频文件，跳过 {skipped} 个非视频/隐藏文件")

    results: dict = {}
    success_count = 0
    fail_count = 0

    # ── 逐文件处理 + 单文件级异常隔离 ─────────────────────────
    for filename in video_files:
        video_path = input_folder / filename
        result_entry: dict = {
            "status": "failed",
            "error": None,
            "processed_video_info": None,
            "output_dir": "",
        }

        try:
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                raise OSError(f"文件大小为 0: {filename}")

            print(f"\n[PROCESS] {filename} ({file_size / 1024 / 1024:.1f} MB)")

            # ── 为当前视频创建独立输出子文件夹 ─────────────────
            base_name = os.path.splitext(filename)[0]
            video_output_dir = output_folder / base_name
            video_output_dir.mkdir(parents=True, exist_ok=True)
            result_entry["output_dir"] = str(video_output_dir)

            # ── Gemini 标注 ───────────────────────────────────
            raw_label = "未标注"
            final_score = "不合格"
            video_duration = get_video_duration(video_path)

            if gemini_client:
                try:
                    label_result = label_video_with_gemini(gemini_client, video_path)
                    raw_label = label_result.raw_response
                    final_score = label_result.final_score
                except GeminiError as ge:
                    print(f"[WARN] Gemini 标注失败 ({filename}): {ge}")
                    raw_label = "标签生成失败"

            # ── 解析标签 ───────────────────────────────────────
            display_label, final_score = _parse_gemini_label(raw_label)

            # ── 构建输出文件名 ────────────────────────────────
            ext = os.path.splitext(filename)[1]
            safe_filename = _build_output_filename(base_name, display_label, ext)
            output_path = video_output_dir / safe_filename

            shutil.copy2(video_path, output_path)

            # ── HTML 报告用相对路径（正斜杠） ─────────────────
            rel_path = os.path.relpath(output_path, output_folder).replace(os.sep, "/")

            result_entry["status"] = "success"
            result_entry["processed_video_info"] = {
                "original_filename": filename,
                "new_filename": safe_filename,
                "label": display_label,
                "gemini_raw": raw_label,
                "final_score": final_score,
                "duration": video_duration,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "relative_video_path": rel_path,
            }

            success_count += 1
            print(f"[OK]   → {safe_filename}  |  终评: {final_score}")

            # API 速率保护（每个视频间隔 1s）
            if gemini_client:
                time.sleep(1)

        except OSError as e:
            result_entry["error"] = f"OS错误: {e}"
            print(f"[FAIL] {filename} — {result_entry['error']}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            result_entry["error"] = f"处理异常: {e}"
            print(f"[FAIL] {filename} — 未预期的错误: {e}")

        finally:
            results[filename] = result_entry
            if result_entry["status"] == "failed":
                fail_count += 1
            print(f"[DONE] {filename}")

    # ── 生成报告 ──────────────────────────────────────────────
    end_time = time.time()
    total_duration = format_duration_human(end_time - start_time)

    if results:
        try:
            generate_html_report(
                results,
                str(output_folder),
                start_time,
                end_time,
            )
        except Exception as e:
            print(f"[WARN] HTML 报告生成失败: {e}")

    # ── 写 JSON 摘要 ─────────────────────────────────────────
    summary = {
        "success": True,
        "total": len(video_files),
        "succeeded": success_count,
        "failed": fail_count,
        "skipped_hidden": skipped,
        "total_duration_seconds": round(end_time - start_time, 1),
        "total_duration_human": total_duration,
        "results": results,
    }

    summary_path = output_folder / "processing_summary.json"
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)
        print(f"\n[INFO] 摘要已保存: {summary_path}")
    except Exception as e:
        print(f"[ERROR] 无法保存摘要: {e}")

    print(f"\n✅ 处理完成！成功: {success_count}/{len(video_files)}，耗时: {total_duration}")
    return summary
