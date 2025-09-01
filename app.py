# app.py
import os, pathlib, shutil, subprocess, tempfile, logging, time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from zhipu_agent import zhipu_conversation
from xfyun_asr import asr_transcribe_file
from config import validate_config, TTS_OUT_DIR, FFMPEG_PATH, questions, questionnaire_reference

# 数字人模块（生成 & 预热）
# 注意：digital_human.py 需为"极速版"，其 generate_digital_human_assets 返回 5 个值
from digital_human import generate_digital_human_assets, warmup_tts

# 媒体文件清理模块
from cleanup_media import cleanup_old_media_files, cleanup_by_session_id

# 报告管理模块
from report_manager import report_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

validate_config()

app = Flask(__name__, static_url_path="/static", static_folder="static")
CORS(app)

# --------- 缓存控制 ---------
@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# --------- 启动预热（首句加速） ---------
try:
    warmup_tts(static_root="static")
except Exception as _:
    logger.warning("TTS 预热失败（忽略）")

def check_tool_exists(tool_name_or_path):
    return shutil.which(tool_name_or_path) is not None or pathlib.Path(tool_name_or_path).exists()

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

# 静态路由
@app.route("/static/video/<path:filename>")
def serve_video(filename):
    return send_from_directory("static/video", filename)

@app.route("/static/tts/<path:filename>")
def serve_tts(filename):
    return send_from_directory("static/tts", filename)

# ========= 文本限长 & 切段（核心：缩短每段时长以提速渲染） =========
AVG_CHARS_PER_SEC = 4.0   # 中文口播粗略 4字/秒
TARGET_SECS = 7           # 单段目标 6~8 秒（更像“实时”）
MAX_CHARS = 45            # 约 6~8 秒

def shorten_for_avatar(text: str, max_chars: int = MAX_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    cutpoints = ['。', '！', '？', '\n', '；', ';', '，', ',']
    for cp in cutpoints:
        idx = t.rfind(cp, 0, max_chars)
        if idx != -1 and idx >= int(max_chars * 0.6):
            return t[:idx+1]
    return t[:max_chars]

def split_for_avatar(text: str, target_secs: int = TARGET_SECS) -> list[str]:
    import re
    t = (text or "").strip()
    if not t:
        return []
    parts = re.split(r'(?<=[。！？\n])', t)
    parts = [p.strip() for p in parts if p.strip()]
    chunks, cur, cur_len = [], [], 0
    target_chars = int(target_secs * AVG_CHARS_PER_SEC * 1.15)
    for p in parts:
        if cur_len + len(p) > target_chars and cur:
            chunks.append("".join(cur).strip())
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += len(p)
    if cur:
        chunks.append("".join(cur).strip())
    out = []
    for ch in chunks:
        if len(ch) <= MAX_CHARS * 2:
            out.append(ch)
        else:
            for i in range(0, len(ch), MAX_CHARS):
                out.append(ch[i:i+MAX_CHARS])
    return out

# ========= API =========

@app.route("/api/agent/start", methods=["POST"])
def agent_start():
    data = request.get_json(force=True)
    session_id = data["session_id"]

    # 在开始新对话前，清理上一次对话的音频和视频文件
    try:
        logger.info("开始清理上一次对话的媒体文件...")
        audio_count, video_count = cleanup_old_media_files(static_root="static", keep_latest=0)
        logger.info(f"清理完成: 删除了 {audio_count} 个音频文件和 {video_count} 个视频文件")
    except Exception as e:
        logger.warning(f"清理媒体文件时发生错误（继续执行）: {e}")

    try:
        logger.info(f"开始智谱AI对话，会话ID: {session_id}")
        ai_response, conversation_id = zhipu_conversation(
            prompt="请开始肺癌早筛问卷，询问用户姓名"
        )
        question = ai_response
        logger.info(f"智谱AI开始对话成功: {question}")
        final_session_id = conversation_id
    except Exception as e:
        logger.error(f"智谱AI调用失败: {e}")
        question = "系统暂时不可用，请稍后重试"
        final_session_id = session_id

    # 数字人：限长 + 即播直链（video_stream_url）
    try:
        wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
            text=shorten_for_avatar(question),
            prefix=str(final_session_id),
            ffmpeg_path=FFMPEG_PATH,
            static_root="static",
        )
    except Exception as e:
        logger.error(f"数字人生成失败，回退为最小可用响应：{e}")
        tts_url = ""
        video_url = ""
        video_stream_url = ""

    return jsonify({
        "session_id": final_session_id,
        "question": question,
        "tts_url": tts_url,
        "video_url": video_url,
        "video_stream_url": video_stream_url  # ★ 前端优先用它“即播”
    })

@app.route("/api/agent/reply", methods=["POST"])
def agent_reply():
    data = request.get_json(force=True)
    session_id = data["session_id"]
    answer_text = data["answer"]

    try:
        logger.info(f"智谱AI继续对话，会话ID: {session_id}, 用户回答: {answer_text[:50]}...")

        ai_response, conversation_id = zhipu_conversation(
            prompt=f"用户回答：{answer_text}。请继续询问问卷中的下一个问题，不要重复已经问过的问题。如果问卷已完成，请生成肺癌早筛风险评估报告。",
            conversation_id=session_id
        )

        # 是否完成
        is_completed = (
            "肺癌早筛风险评估报告" in ai_response or
            "Agent_结果" in ai_response or
            "评估报告" in ai_response or
            "风险评估" in ai_response or
            "报告" in ai_response or
            "问卷已完成" in ai_response or
            "问卷完成" in ai_response or
            "所有问题" in ai_response or
            "总结" in ai_response or
            len(ai_response) > 800
        )

        logger.info("🔍 问卷完成检测调试信息:")
        logger.info(f"  - ai_response长度: {len(ai_response)}")
        logger.info(f"  - 长度>800: {len(ai_response) > 800}")
        logger.info(f"  - 最终判断is_completed: {is_completed}")
        logger.info(f"  - ai_response内容预览: {ai_response[:200]}...")

        if is_completed:
            question = ai_response
            is_complete = True
            final_session_id = conversation_id
            
            # 智谱AI模式：尝试从对话历史中提取用户信息并保存报告
            try:
                # 从智谱AI的回复中提取用户信息
                user_info = extract_user_info_from_response(ai_response)
                
                # 如果无法提取用户信息，尝试使用默认信息
                if not user_info:
                    logger.warning("无法从智谱AI回复中提取用户信息，使用默认信息")
                    user_info = {
                        "姓名": "智谱AI用户",
                        "性别(1男 2女)": "未知",
                        "出生年份": "未知",
                        "联系电话2(手机)": "无手机号",
                        "联系电话1(住宅)": "无",
                        "家庭地址": "无"
                    }
                
                if user_info:
                    saved_path = report_manager.save_report(ai_response, user_info, session_id)
                    if saved_path:
                        logger.info(f"智谱AI报告已保存: {saved_path}")
                        # 同时保存JSON格式
                        json_path = report_manager.save_report_json(ai_response, user_info, session_id)
                        if json_path:
                            logger.info(f"智谱AI JSON报告已保存: {json_path}")
                    else:
                        logger.warning("智谱AI报告保存失败")
                else:
                    logger.warning("无法从智谱AI回复中提取用户信息，跳过报告保存")
            except Exception as e:
                logger.error(f"保存智谱AI报告时发生错误: {e}")
        else:
            question = ai_response
            logger.info(f"智谱AI继续对话成功: {question}")
            is_complete = False
            final_session_id = conversation_id

    except Exception as e:
        logger.error(f"智谱AI调用失败: {e}")
        question = "系统暂时不可用，请稍后重试"
        final_session_id = session_id
        is_complete = False

    # 数字人生成（限长） + 即播直链
    try:
        wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
            text=shorten_for_avatar(question),
            prefix=str(final_session_id),
            ffmpeg_path=FFMPEG_PATH,
            static_root="static",
        )
    except Exception as e:
        logger.error(f"数字人生成失败，回退为最小可用响应：{e}")
        tts_url = ""
        video_url = ""
        video_stream_url = ""

    return jsonify({
        "session_id": final_session_id,
        "question": question,
        "tts_url": tts_url,
        "video_url": video_url,
        "video_stream_url": video_stream_url,  # ★ 新增
        "is_complete": is_complete
    })

@app.route("/api/asr", methods=["POST"])
def asr():
    try:
        logger.info("=== ASR接口开始处理 ===")
        if "audio" not in request.files:
            logger.error("ASR接口错误: 没有audio字段")
            return jsonify({"text": "", "error": "no audio field"}), 400

        def check_tool_exists(tool_name_or_path):
            return shutil.which(tool_name_or_path) is not None or pathlib.Path(tool_name_or_path).exists()

        f = request.files["audio"]
        td = tempfile.mkdtemp(prefix="asr_")
        td_path = pathlib.Path(td)
        suffix = f.filename.split('.')[-1] or 'webm'
        in_path = td_path / f"input.{suffix}"
        out_wav = td_path / "converted.wav"

        try:
            f.save(in_path)

            if in_path.suffix.lower() in ['.spx', '.speex']:
                if check_tool_exists("speexdec"):
                    subprocess.run(["speexdec", str(in_path), str(out_wav)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run([FFMPEG_PATH, "-y", "-i", str(in_path),
                                    "-ac", "1", "-ar", "16000",
                                    "-acodec", "pcm_s16le", str(out_wav)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run([FFMPEG_PATH, "-y", "-i", str(in_path),
                                "-ac", "1", "-ar", "16000",
                                "-acodec", "pcm_s16le", str(out_wav)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            text = asr_transcribe_file(str(out_wav))
            return jsonify({"text": text or ""})

        finally:
            for i in range(5):
                try:
                    shutil.rmtree(td_path, ignore_errors=False)
                    break
                except PermissionError:
                    time.sleep(0.1)
                except Exception:
                    break

    except Exception as e:
        return jsonify({"text": "", "error": f"ASR接口异常: {str(e)}"}), 500

@app.route("/api/health")
def health():
    return jsonify({"ok": True})

@app.route("/api/asr/health")
def asr_health():
    try:
        def check_tool_exists(tool_name_or_path):
            return shutil.which(tool_name_or_path) is not None or pathlib.Path(tool_name_or_path).exists()

        health_status = {
            "status": "ok",
            "ffmpeg": {
                "path": FFMPEG_PATH,
                "exists": check_tool_exists(FFMPEG_PATH),
                "version": None
            },
            "speexdec": {
                "exists": check_tool_exists("speexdec"),
                "path": shutil.which("speexdec")
            },
            "temp_dir": {
                "writable": True,
                "path": str(tempfile.gettempdir())
            }
        }

        if check_tool_exists(FFMPEG_PATH):
            try:
                result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    health_status["ffmpeg"]["version"] = result.stdout.split('\n')[0]
            except Exception as e:
                health_status["ffmpeg"]["version"] = f"获取版本失败: {str(e)}"

        try:
            from config import XFYUN_APPID, XFYUN_APIKEY, XFYUN_APISECRET
            health_status["xfyun"] = {
                "appid": XFYUN_APPID,
                "apikey": "已设置" if XFYUN_APIKEY else "未设置",
                "apisecret": "已设置" if XFYUN_APISECRET else "未设置"
            }
        except Exception as e:
            health_status["xfyun"] = {"error": str(e)}

        return jsonify(health_status)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "timestamp": time.time()}), 500

@app.route("/api/questionnaire_status", methods=["GET"])
def get_questionnaire_status():
    return jsonify({"current_system": "智谱AI", "use_zhipu": True})

@app.route("/api/local_questionnaire/start", methods=["POST"])
def local_questionnaire_start():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", str(int(time.time() * 1000)))

        # 在开始新问卷前，清理上一次对话的音频和视频文件
        try:
            logger.info("开始清理上一次对话的媒体文件...")
            audio_count, video_count = cleanup_old_media_files(static_root="static", keep_latest=0)
            logger.info(f"清理完成: 删除了 {audio_count} 个音频文件和 {video_count} 个视频文件")
        except Exception as e:
            logger.warning(f"清理媒体文件时发生错误（继续执行）: {e}")

        if not hasattr(app, 'questionnaire_sessions'):
            app.questionnaire_sessions = {}

        app.questionnaire_sessions[session_id] = {
            "current_question_index": 0,
            "answers": {},
            "start_time": time.time()
        }

        first_question = questions[0]
        question_info = get_question_info(0)

        try:
            wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
                text=shorten_for_avatar(first_question),
                prefix=str(session_id),
                ffmpeg_path=FFMPEG_PATH,
                static_root="static",
            )
        except Exception as e:
            logger.error(f"数字人生成失败（local start）：{e}")
            tts_url = ""
            video_url = ""
            video_stream_url = ""

        return jsonify({
            "session_id": session_id,
            "question": first_question,
            "question_info": question_info,
            "tts_url": tts_url,
            "video_url": video_url,
            "video_stream_url": video_stream_url,  # ★ 新增
            "progress": f"1/{len(questions)}",
            "total_questions": len(questions)
        })
    except Exception as e:
        logger.error(f"启动本地问卷失败: {e}")
        return jsonify({"error": f"启动失败: {str(e)}"}), 500

@app.route("/api/local_questionnaire/reply", methods=["POST"])
def local_questionnaire_reply():
    try:
        data = request.get_json(force=True)
        session_id = data["session_id"]
        answer_text = data["answer"]

        if session_id not in app.questionnaire_sessions:
            return jsonify({"error": "会话不存在"}), 400

        session = app.questionnaire_sessions[session_id]
        current_index = session["current_question_index"]
        current_question = questions[current_index]
        session["answers"][current_question] = answer_text

        next_index = current_index + 1

        if next_index >= len(questions):
            report = generate_assessment_report(session["answers"])
            session["completed"] = True
            session["report"] = report

            # 保存报告到文件
            try:
                saved_path = report_manager.save_report(report, session["answers"], session_id)
                if saved_path:
                    logger.info(f"本地问卷报告已保存: {saved_path}")
                    # 同时保存JSON格式
                    json_path = report_manager.save_report_json(report, session["answers"], session_id)
                    if json_path:
                        logger.info(f"本地问卷JSON报告已保存: {json_path}")
                else:
                    logger.warning("本地问卷报告保存失败")
            except Exception as e:
                logger.error(f"保存本地问卷报告时发生错误: {e}")

            # 报告很长 -> 先做"摘要快视频"（6~8秒）
            first_seg = shorten_for_avatar(report)
            try:
                wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
                    text=first_seg,
                    prefix=f"{session_id}_report",
                    ffmpeg_path=FFMPEG_PATH,
                    static_root="static",
                )
            except Exception as e:
                logger.error(f"数字人生成失败（local report）：{e}")
                tts_url = ""
                video_url = ""
                video_stream_url = ""

            return jsonify({
                "session_id": session_id,
                "question": report,              # 完整报告文本
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,  # ★ 新增
                "is_complete": True,
                "progress": f"{len(questions)}/{len(questions)}",
                "total_questions": len(questions)
            })
        else:
            next_question = questions[next_index]
            question_info = get_question_info(next_index)
            session["current_question_index"] = next_index

            try:
                wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
                    text=shorten_for_avatar(next_question),
                    prefix=str(session_id),
                    ffmpeg_path=FFMPEG_PATH,
                    static_root="static",
                )
            except Exception as e:
                logger.error(f"数字人生成失败（local reply）：{e}")
                tts_url = ""
                video_url = ""
                video_stream_url = ""

            return jsonify({
                "session_id": session_id,
                "question": next_question,
                "question_info": question_info,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,  # ★ 新增
                "is_complete": False,
                "progress": f"{next_index + 1}/{len(questions)}",
                "total_questions": len(questions)
            })

    except Exception as e:
        logger.error(f"本地问卷回答失败: {e}")
        return jsonify({"error": f"提交失败: {str(e)}"}), 500

@app.route("/api/local_questionnaire/status/<session_id>", methods=["GET"])
def get_local_questionnaire_status(session_id):
    try:
        if session_id not in app.questionnaire_sessions:
            return jsonify({"error": "会话不存在"}), 404

        session = app.questionnaire_sessions[session_id]
        current_index = session["current_question_index"]

        return jsonify({
            "session_id": session_id,
            "current_question_index": current_index,
            "current_question": questions[current_index] if current_index < len(questions) else None,
            "progress": f"{current_index + 1}/{len(questions)}",
            "total_questions": len(questions),
            "completed": session.get("completed", False),
            "answers_count": len(session["answers"])
        })
    except Exception as e:
        logger.error(f"获取本地问卷状态失败: {e}")
        return jsonify({"error": f"获取状态失败: {str(e)}"}), 500

def get_question_info(question_index):
    if question_index >= len(questions):
        return None
    question = questions[question_index]
    for category, questions_dict in questionnaire_reference.items():
        if question in questions_dict:
            return {
                "category": category,
                "question": question,
                "format": questions_dict[question],
                "question_index": question_index + 1,
                "total_questions": len(questions)
            }
    return {
        "category": "其他",
        "question": question,
        "format": "自由回答",
        "question_index": question_index + 1,
        "total_questions": len(questions)
    }

def extract_user_info_from_response(response_text):
    """
    从智谱AI的回复中提取用户信息
    
    Args:
        response_text: 智谱AI的回复文本
        
    Returns:
        用户信息字典，如果无法提取则返回None
    """
    import re
    
    user_info = {}
    
    try:
        # 清理文本，移除多余的空白字符
        cleaned_text = re.sub(r'\s+', ' ', response_text.strip())
        logger.info(f"开始提取用户信息，文本长度: {len(cleaned_text)}")
        logger.info(f"文本预览: {cleaned_text[:200]}...")
        
        # 提取姓名 - 增强模式匹配
        name_patterns = [
            r'姓名[：:]\s*([^\n\r，,。！!？?；;]+)',
            r'用户姓名[：:]\s*([^\n\r，,。！!？?；;]+)',
            r'患者姓名[：:]\s*([^\n\r，,。！!？?；;]+)',
            r'姓名\s*([^\n\r，,。！!？?；;：:]+)',
            r'用户\s*([^\n\r，,。！!？?；;：:]+)',
            r'患者\s*([^\n\r，,。！!？?；;：:]+)',
            # 匹配常见的中文姓名格式
            r'([\u4e00-\u9fa5]{2,4})\s*[，,。！!？?；;]',
            # 匹配"我是XXX"格式
            r'我是\s*([\u4e00-\u9fa5]{2,4})',
            r'我叫\s*([\u4e00-\u9fa5]{2,4})',
            # 匹配"XXX，男/女"格式
            r'([\u4e00-\u9fa5]{2,4})\s*[,，]\s*[男女]',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                name = match.group(1).strip()
                # 过滤掉明显不是姓名的内容
                if (len(name) >= 2 and len(name) <= 4 and 
                    not any(keyword in name for keyword in ['年龄', '性别', '出生', '电话', '手机', '地址', '职业', '文化', '吸烟', '被动', '厨房', '职业', '肿瘤', '家族', '检查', '支气管', '肺气肿', '肺结核', '阻塞', '纤维化', '消瘦', '干咳', '感觉'])):
                    user_info["姓名"] = name
                    logger.info(f"提取到姓名: {name}")
                    break
        
        # 提取性别
        gender_patterns = [
            r'性别[：:]\s*([男女12])',
            r'([男女])性',
            r'([男女])\s*[,，]',
            r'([12])\s*[,，]',
            # 匹配"男/女，XX岁"格式
            r'([男女])\s*[,，]\s*\d+岁',
            # 匹配"我是男/女性"格式
            r'我是\s*([男女])性',
        ]
        
        for pattern in gender_patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                gender = match.group(1).strip()
                if gender in ['1', '男']:
                    user_info["性别(1男 2女)"] = "1"
                    logger.info("提取到性别: 男")
                elif gender in ['2', '女']:
                    user_info["性别(1男 2女)"] = "2"
                    logger.info("提取到性别: 女")
                break
        
        # 提取年龄/出生年份
        age_patterns = [
            r'年龄[：:]\s*(\d+)',
            r'(\d+)岁',
            r'出生年份[：:]\s*(\d{4})',
            r'(\d{4})年出生',
            r'(\d{4})年',
            # 匹配"XX岁，男/女"格式
            r'(\d+)岁\s*[,，]\s*[男女]',
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                age_or_year = match.group(1).strip()
                if len(age_or_year) == 4 and 1900 <= int(age_or_year) <= 2024:  # 出生年份
                    user_info["出生年份"] = age_or_year
                    logger.info(f"提取到出生年份: {age_or_year}")
                elif age_or_year.isdigit() and 1 <= int(age_or_year) <= 120:  # 年龄
                    try:
                        age = int(age_or_year)
                        current_year = 2024  # 可以根据需要调整
                        birth_year = current_year - age
                        user_info["出生年份"] = str(birth_year)
                        logger.info(f"提取到年龄: {age}岁，转换为出生年份: {birth_year}")
                    except:
                        pass
                break
        
        # 提取手机号
        phone_patterns = [
            r'手机[号]?[：:]\s*(\d{11})',
            r'联系电话[：:]\s*(\d{11})',
            r'电话[：:]\s*(\d{11})',
            r'手机\s*(\d{11})',
            r'电话\s*(\d{11})',
            # 匹配纯11位数字（手机号格式）
            r'(\d{11})',
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                phone = match.group(1).strip()
                if len(phone) == 11 and phone.startswith(('1')):
                    user_info["联系电话2(手机)"] = phone
                    logger.info(f"提取到手机号: {phone}")
                    break
        
        # 提取家庭地址
        address_patterns = [
            r'家庭地址[：:]\s*([^\n\r，,。！!？?；;]+)',
            r'地址[：:]\s*([^\n\r，,。！!？?；;]+)',
            r'住址[：:]\s*([^\n\r，,。！!？?；;]+)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                address = match.group(1).strip()
                if len(address) > 5:  # 地址应该比较长
                    user_info["家庭地址"] = address
                    logger.info(f"提取到家庭地址: {address}")
                    break
        
        # 如果至少提取到了姓名，就认为成功
        if user_info.get("姓名"):
            # 为缺失的字段设置默认值
            if "性别(1男 2女)" not in user_info:
                user_info["性别(1男 2女)"] = "未知"
            if "出生年份" not in user_info:
                user_info["出生年份"] = "未知"
            if "联系电话2(手机)" not in user_info:
                user_info["联系电话2(手机)"] = "无手机号"
            if "联系电话1(住宅)" not in user_info:
                user_info["联系电话1(住宅)"] = "无"
            if "家庭地址" not in user_info:
                user_info["家庭地址"] = "无"
            
            logger.info(f"从智谱AI回复中提取到用户信息: {user_info}")
            return user_info
        else:
            logger.warning("无法从智谱AI回复中提取到用户姓名")
            logger.warning(f"原始文本内容: {cleaned_text[:500]}...")
            return None
            
    except Exception as e:
        logger.error(f"提取用户信息时发生错误: {e}")
        return None

def generate_assessment_report(answers):
    report = "肺癌早筛风险评估报告\n\n" + "=" * 50 + "\n\n"
    report += "【基本信息】\n"
    if "姓名" in answers:
        report += f"姓名：{answers['姓名']}\n"
    if "性别(1男 2女)" in answers:
        gender = "男" if answers["性别(1男 2女)"] == "1" else "女"
        report += f"性别：{gender}\n"
    if "出生年份" in answers:
        report += f"出生年份：{answers['出生年份']}\n"
    if "身高(cm)" in answers and "体重(kg)" in answers:
        try:
            height = float(answers["身高(cm)"])
            weight = float(answers["体重(kg)"])
            bmi = weight / ((height / 100) ** 2)
            report += f"身高：{height}cm，体重：{weight}kg，BMI：{bmi:.1f}\n"
        except:
            report += f"身高：{answers['身高(cm)']}cm，体重：{answers['体重(kg)']}kg\n"

    report += "\n【风险评估】\n"
    if answers.get("吸烟史(1是 2否)") == "1":
        report += "⚠️ 吸烟史：有吸烟史，增加肺癌风险\n"
        try:
            years = float(answers.get("累计吸烟年数","0"))
            daily = float(answers.get("吸烟频率(支/天)","0"))
            pack_years = (years * daily) / 20
            if pack_years > 30:
                report += f"   重度吸烟：{pack_years:.1f}包年，高风险\n"
            elif pack_years > 20:
                report += f"   中度吸烟：{pack_years:.1f}包年，中风险\n"
            else:
                report += f"   轻度吸烟：{pack_years:.1f}包年，低风险\n"
        except:
            report += "   吸烟情况：需进一步评估\n"
    if answers.get("被动吸烟(1否 2是)") == "2":
        report += "⚠️ 被动吸烟：存在被动吸烟情况\n"
    if answers.get("职业致癌物质接触(1有 2无)") == "1":
        report += "⚠️ 职业暴露：存在职业致癌物质接触\n"
    if answers.get("三代以内直系亲属肺癌家族史(1有 2无)") == "1":
        report += "⚠️ 家族史：存在肺癌家族史，遗传风险增加\n"
    if answers.get("最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)") == "1":
        report += "⚠️ 症状：存在可疑症状，建议及时就医\n"
    if answers.get("一年内胸部CT检查(1是 2否)") == "2":
        report += "📋 建议：建议进行胸部CT检查\n"

    report += "\n【总体评估】\n"
    risk_score = 0
    if answers.get("吸烟史(1是 2否)") == "1": risk_score += 3
    if answers.get("被动吸烟(1否 2是)") == "2": risk_score += 1
    if answers.get("职业致癌物质接触(1有 2无)") == "1": risk_score += 2
    if answers.get("三代以内直系亲属肺癌家族史(1有 2无)") == "1": risk_score += 2
    if answers.get("最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)") == "1": risk_score += 3

    if risk_score >= 6:
        report += "🔴 高风险：建议立即就医，进行详细检查\n"
    elif risk_score >= 3:
        report += "🟡 中风险：建议定期体检，关注症状变化\n"
    else:
        report += "🟢 低风险：保持健康生活方式，定期体检\n"

    report += "\n【建议措施】\n"
    report += "1. 戒烟限酒，避免二手烟\n2. 保持室内通风，减少油烟接触\n3. 定期体检，关注肺部健康\n4. 如有异常症状，及时就医\n5. 保持健康生活方式，适量运动\n"
    report += "\n" + "=" * 50 + "\n"
    report += f"报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    return report

@app.route("/api/assessment_report/<session_id>", methods=["GET"])
def get_assessment_report(session_id):
    try:
        return jsonify({"session_id": session_id, "has_report": True, "message": "评估报告已生成，请查看对话历史"})
    except Exception as e:
        logger.error(f"获取评估报告失败: {e}")
        return jsonify({"error": f"获取评估报告失败: {str(e)}"}), 500

@app.route("/api/debug/zhipu", methods=["POST"])
def debug_zhipu():
    try:
        data = request.get_json(force=True)
        test_prompt = data.get("prompt", "请简单回复：测试成功")
        ai_response, conversation_id = zhipu_conversation(prompt=test_prompt)
        return jsonify({
            "success": True,
            "response": ai_response,
            "conversation_id": conversation_id,
            "response_length": len(ai_response) if ai_response else 0,
            "has_error": "未获取到有效回复" in ai_response or "java.lang.IllegalArgumentException" in ai_response
        })
    except Exception as e:
        logger.error(f"智谱AI调试失败: {e}")
        return jsonify({"success": False, "error": str(e), "error_type": type(e).__name__}), 500

@app.route("/api/cleanup/media", methods=["POST"])
def cleanup_media():
    """手动清理媒体文件API"""
    try:
        data = request.get_json(force=True) if request.is_json else {}
        keep_latest = data.get("keep_latest", 0)  # 保留最新的文件数量
        max_age_hours = data.get("max_age_hours", None)  # 按年龄清理
        
        if max_age_hours:
            # 按年龄清理
            from cleanup_media import cleanup_old_files_by_age
            audio_count, video_count = cleanup_old_files_by_age(
                static_root="static", 
                max_age_hours=max_age_hours
            )
            cleanup_type = f"按年龄清理（超过{max_age_hours}小时）"
        else:
            # 按数量清理
            audio_count, video_count = cleanup_old_media_files(
                static_root="static", 
                keep_latest=keep_latest
            )
            cleanup_type = f"按数量清理（保留最新{keep_latest}个）"
        
        logger.info(f"手动清理完成: {cleanup_type}, 删除了 {audio_count} 个音频文件和 {video_count} 个视频文件")
        
        return jsonify({
            "success": True,
            "cleanup_type": cleanup_type,
            "deleted_audio_count": audio_count,
            "deleted_video_count": video_count,
            "message": f"清理完成: 删除了 {audio_count} 个音频文件和 {video_count} 个视频文件"
        })
    except Exception as e:
        logger.error(f"手动清理媒体文件失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/media/info", methods=["GET"])
def get_media_info():
    """获取媒体文件信息API"""
    try:
        from cleanup_media import get_media_files_info
        info = get_media_files_info(static_root="static")
        
        # 格式化文件大小
        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
        
        # 格式化修改时间
        def format_time(timestamp):
            import datetime
            return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        # 处理音频文件信息
        audio_files = []
        for file_info in info["audio_files"]:
            audio_files.append({
                "name": file_info["name"],
                "size": format_size(file_info["size"]),
                "modified": format_time(file_info["modified"])
            })
        
        # 处理视频文件信息
        video_files = []
        for file_info in info["video_files"]:
            video_files.append({
                "name": file_info["name"],
                "size": format_size(file_info["size"]),
                "modified": format_time(file_info["modified"])
            })
        
        return jsonify({
            "success": True,
            "audio_count": info["audio_count"],
            "video_count": info["video_count"],
            "total_audio_size": format_size(info["total_audio_size"]),
            "total_video_size": format_size(info["total_video_size"]),
            "audio_files": audio_files,
            "video_files": video_files
        })
    except Exception as e:
        logger.error(f"获取媒体文件信息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reports/list", methods=["GET"])
def get_reports_list():
    """获取报告列表API"""
    try:
        reports = report_manager.get_reports_list()
        
        # 格式化文件大小
        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
        
        # 处理报告文件信息
        formatted_reports = []
        for report in reports:
            formatted_reports.append({
                "filename": report["filename"],
                "size": format_size(report["size"]),
                "created": report["created"],
                "modified": report["modified"]
            })
        
        return jsonify({
            "success": True,
            "reports": formatted_reports,
            "total_count": len(formatted_reports)
        })
    except Exception as e:
        logger.error(f"获取报告列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reports/<filename>", methods=["GET"])
def get_report_content(filename):
    """获取指定报告内容API"""
    try:
        content = report_manager.get_report_content(filename)
        if content:
            return jsonify({
                "success": True,
                "filename": filename,
                "content": content
            })
        else:
            return jsonify({"success": False, "error": "报告文件不存在"}), 404
    except Exception as e:
        logger.error(f"获取报告内容失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reports/<filename>", methods=["DELETE"])
def delete_report(filename):
    """删除指定报告API"""
    try:
        success = report_manager.delete_report(filename)
        if success:
            return jsonify({
                "success": True,
                "message": f"报告 {filename} 删除成功"
            })
        else:
            return jsonify({"success": False, "error": "报告文件不存在"}), 404
    except Exception as e:
        logger.error(f"删除报告失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reports/stats", methods=["GET"])
def get_reports_stats():
    """获取报告统计信息API"""
    try:
        stats = report_manager.get_reports_stats()
        return jsonify({
            "success": True,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"获取报告统计失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reports/cleanup", methods=["POST"])
def cleanup_old_reports():
    """清理旧报告API"""
    try:
        data = request.get_json(force=True) if request.is_json else {}
        days = data.get("days", 30)  # 默认保留30天
        
        deleted_count = report_manager.cleanup_old_reports(days)
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"清理完成，删除了 {deleted_count} 个超过 {days} 天的旧报告"
        })
    except Exception as e:
        logger.error(f"清理旧报告失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"未处理的异常: {e}")
    return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "接口不存在"}), 404

if __name__ == "__main__":
    print("启动Flask服务器...")
    print("访问地址: http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)

