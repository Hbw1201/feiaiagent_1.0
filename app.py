# app.py
import os, pathlib, shutil, subprocess, tempfile, logging, time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from zhipu_agent import zhipu_conversation
from xfyun_asr import asr_transcribe_file
# from xfyun_tts import tts_text_to_mp3# [MOD] 不再直接使用本地科大讯飞 TTS
from config import validate_config, TTS_OUT_DIR, FFMPEG_PATH, questions, questionnaire_reference

# [ADD] 引入数字人模块（通义 CosyVoice + LivePortrait）
from digital_human import generate_digital_human_assets  # [ADD]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

validate_config()

# 1) 开场首问（自我介绍 + 简短说明 + 先问姓名）
PROMPT_LUNG_SCREEN_START = (
    "你是一名温和耐心的健康顾问，正在进行肺癌早筛问卷。\n"
    "对话目标：收集必要信息，在最后生成《肺癌早筛风险评估报告》。\n"
    "语气：友善、拟人化、耐心，用“您”称呼用户；用简短自然的句子；一次只问一个问题。\n"
    "风格：先轻松问候，用一小句说明流程会很快，鼓励用户随时提问。\n"
    "现在请用一句简短自然的话开始：先问用户姓名（只需名字或称呼即可）。"
)

# 2) 正常轮次：承接用户回答 -> 下一题（必要时轻柔澄清；完成后生成报告）
PROMPT_LUNG_SCREEN_CONTINUE = (
    "用户回答：{answer}\n"
    "请用友善且耐心的语气继续肺癌早筛问卷。一条原则：一次只问一个问题；"
    "如用户回答含糊或不在选项内，请先用一句话温柔复述/澄清，再给出示例或可选项；"
    "避免重复已问过的问题；尽量用简短句子；避免专业术语堆叠。\n"
    "当你判断信息已足够时，请生成《肺癌早筛风险评估报告》，"
    "报告结构包含：【基本信息】【风险评估】【建议措施】三部分，条理清晰，避免过度医疗化表达，"
    "并附上一句温和的收尾提醒（如：如有不适请及时就医）。\n"
    "若仍在问卷流程中，请只输出下一道题的一句话提问（不要额外解释）。"
)

# 3) 仅重问“同一题”（用户答非所问/模型节点报错时的柔性重提）
PROMPT_LUNG_SCREEN_RETRY_SAME = (
    "用户刚才的回答：{answer}\n"
    "请以更清晰、友善、耐心的方式，重新询问刚才那一道题。\n"
    "请简化表述，并给出示例或可选项（如：1/2/3），帮助用户快速作答；"
    "一次只问一个问题，并避免指责或强硬语气。\n"
    "输出仅保留这一道题的简短提问。"
)

# 4) 全局重启（温柔重启 + 先问姓名）
PROMPT_LUNG_SCREEN_RESTART = (
    "我们重新开始肺癌早筛问卷吧。请先用一句简短自然的话做轻松开场，"
    "说明整个过程很快、只需回答必要问题，并鼓励用户随时提问。"
    "然后第一题先询问用户姓名（只需名字或称呼）。"
)

# 5) 调试接口默认提示词（简短、中文、拟人化）
PROMPT_LUNG_SCREEN_DEBUG_DEFAULT = "请用一句简短亲切的中文回复：测试成功，已就绪。"
app = Flask(__name__, static_url_path="/static", static_folder="static")
CORS(app)

# 添加缓存控制，防止静态文件被缓存
@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

def check_tool_exists(tool_name_or_path):
    return shutil.which(tool_name_or_path) is not None or pathlib.Path(tool_name_or_path).exists()

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

# [ADD] 新增视频静态文件路由（与现有 tts 保持一致）
@app.route("/static/video/<path:filename>")   # [ADD]
def serve_video(filename):                     # [ADD]
    return send_from_directory("static/video", filename)  # [ADD]

@app.route("/api/agent/start", methods=["POST"])
def agent_start():
    data = request.get_json(force=True)
    session_id = data["session_id"]

    try:
        logger.info(f"开始智谱AI对话，会话ID: {session_id}")

        ai_response, conversation_id = zhipu_conversation(
            prompt=PROMPT_LUNG_SCREEN_START  # ← 原来是固定字符串，这里改为变量
        )

        question = ai_response
        logger.info(f"智谱AI开始对话成功: {question}")
        final_session_id = conversation_id

    except Exception as e:
        logger.error(f"智谱AI调用失败: {e}")
        question = "系统暂时不可用，请稍后重试"
        final_session_id = session_id

    # [MOD] 使用通义 CosyVoice + LivePortrait 替代原来的 TTS
    try:
        mp3_path, mp4_path, tts_url, video_url = generate_digital_human_assets(
            text=question,
            prefix=str(final_session_id),
            ffmpeg_path=FFMPEG_PATH,
            static_root="static",
        )
    except Exception as e:
        logger.error(f"数字人生成失败，回退为原 TTS 文本音频：{e}")
        # 回退方案：若数字人失败，仅返回文本（无视频）
        # 仍然生成一个可用的最小响应，避免前端卡住
        # 你也可以在这里调用 tts_text_to_mp3 做兜底（若仍保留 xfyun 的实现）
        # from xfyun_tts import tts_text_to_mp3
        mp3_path = pathlib.Path(TTS_OUT_DIR) / f"{final_session_id}_{int(time.time())}.mp3"
        mp3_path.parent.mkdir(parents=True, exist_ok=True)
        # 简易兜底：生成空白音频或直接不给音频（这里直接不给音频）
        tts_url = ""
        video_url = ""

    return jsonify({"session_id": final_session_id, "question": question, "tts_url": tts_url, "video_url": video_url})  # [MOD] 增加 video_url 字段

@app.route("/api/agent/reply", methods=["POST"])
def agent_reply():
    data = request.get_json(force=True)
    session_id = data["session_id"]
    answer_text = data["answer"]

    try:
        logger.info(f"智谱AI继续对话，会话ID: {session_id}, 用户回答: {answer_text[:50]}...")

        ai_response, conversation_id = zhipu_conversation(
            prompt=PROMPT_LUNG_SCREEN_CONTINUE.format(answer=answer_text),  # ← 使用 format 注入用户回答
            conversation_id=session_id
        )

        # 检查是否完成 - 通过检查响应内容来判断
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

        logger.info(f"🔍 问卷完成检测调试信息:")
        logger.info(f"  - ai_response长度: {len(ai_response)}")
        logger.info(f"  - 包含'肺癌早筛风险评估报告': {'肺癌早筛风险评估报告' in ai_response}")
        logger.info(f"  - 包含'Agent_结果': {'Agent_结果' in ai_response}")
        logger.info(f"  - 包含'评估报告': {'评估报告' in ai_response}")
        logger.info(f"  - 包含'风险评估': {'风险评估' in ai_response}")
        logger.info(f"  - 包含'报告': {'报告' in ai_response}")
        logger.info(f"  - 包含'问卷已完成': {'问卷已完成' in ai_response}")
        logger.info(f"  - 包含'问卷完成': {'问卷完成' in ai_response}")
        logger.info(f"  - 包含'所有问题': {'所有问题' in ai_response}")
        logger.info(f"  - 包含'总结': {'总结' in ai_response}")
        logger.info(f"  - 长度>800: {len(ai_response) > 800}")
        logger.info(f"  - 最终判断is_completed: {is_completed}")
        logger.info(f"  - ai_response内容预览: {ai_response[:200]}...")

        if "未获取到有效回复" in ai_response or "java.lang.IllegalArgumentException" in ai_response or "Agent流程错误" in ai_response:
            logger.error(f"智谱AI调用失败或中断: {ai_response}")
            if "Agent流程错误" in ai_response:
                logger.info("检测到Agent流程错误，尝试重新询问当前问题...")
                try:
                    retry_response, retry_conversation_id = zhipu_conversation(
                        prompt=PROMPT_LUNG_SCREEN_RETRY_SAME.format(answer=answer_text),  # ← 柔性重提
                        conversation_id=session_id
                    )
                    if "未获取到有效回复" not in retry_response and "java.lang.IllegalArgumentException" not in retry_response and "Agent流程错误" not in retry_response:
                        logger.info("重新询问成功，继续对话")
                        question = retry_response
                        is_complete = False
                        final_session_id = retry_conversation_id
                    else:
                        logger.error("重新询问失败，尝试重新开始对话")
                        question = "刚才的问题出现了错误，让我重新开始询问。请告诉我您的姓名。"
                        is_complete = False
                        new_response, new_conversation_id = zhipu_conversation(
                            prompt=PROMPT_LUNG_SCREEN_RESTART  # ← 温和重启 + 先问姓名
                        )
                        if "未获取到有效回复" not in new_response and "java.lang.IllegalArgumentException" not in new_response and "Agent流程错误" not in new_response:
                            question = new_response
                            final_session_id = new_conversation_id
                        else:
                            question = "智谱AI暂时不可用，请稍后重试。错误：Agent流程中断"
                            final_session_id = session_id
                except Exception as retry_e:
                    logger.error(f"重新询问失败: {retry_e}")
                    question = "刚才的问题出现了错误，让我重新开始询问。请告诉我您的姓名。"
                    is_complete = False
                    final_session_id = session_id
            else:
                try:
                    logger.info("尝试重新开始对话...")
                    retry_response, retry_conversation_id = zhipu_conversation(
                        prompt=PROMPT_LUNG_SCREEN_START  # ← 与首问一致
                    )
                    if "未获取到有效回复" not in retry_response and "java.lang.IllegalArgumentException" not in retry_response:
                        logger.info("重试成功，继续对话")
                        question = retry_response
                        is_complete = False
                        final_session_id = retry_conversation_id
                    else:
                        logger.error("重试失败，返回错误信息")
                        question = "智谱AI暂时不可用，请稍后重试。错误：Agent流程中断"
                        is_complete = False
                        final_session_id = session_id
                except Exception as retry_e:
                    logger.error(f"重试失败: {retry_e}")
                    question = "智谱AI暂时不可用，请稍后重试。错误：Agent流程中断"
                    is_complete = False
                    final_session_id = session_id
        elif is_completed:
            logger.info("检测到问卷完成")
            logger.info(f"ai_response内容长度: {len(ai_response)}")
            question = ai_response
            is_complete = True
            final_session_id = conversation_id
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

    # [MOD] 使用通义 CosyVoice + LivePortrait 生成语音与数字人视频
    try:
        mp3_path, mp4_path, tts_url, video_url = generate_digital_human_assets(
            text=question,
            prefix=str(final_session_id),
            ffmpeg_path=FFMPEG_PATH,
            static_root="static",
        )
    except Exception as e:
        logger.error(f"数字人生成失败，回退为最小可用响应：{e}")
        tts_url = ""
        video_url = ""

    return jsonify({
        "session_id": final_session_id,
        "question": question,
        "tts_url": tts_url,      # [MOD] 仍返回语音（mp3 或 wav）
        "video_url": video_url,  # [ADD] 新增：数字人视频
        "is_complete": is_complete
    })

@app.route("/api/asr", methods=["POST"])
def asr():
    try:
        logger.info("=== ASR接口开始处理 ===")
        logger.info(f"请求方法: {request.method}")
        logger.info(f"请求头: {dict(request.headers)}")
        logger.info(f"请求文件: {list(request.files.keys()) if request.files else '无文件'}")

        if "audio" not in request.files:
            logger.error("ASR接口错误: 没有audio字段")
            return jsonify({"error": "no audio field"}), 400

        logger.info(f"当前FFMPEG_PATH: {FFMPEG_PATH}")
        logger.info(f"FFMPEG_PATH存在: {check_tool_exists(FFMPEG_PATH)}")
        logger.info(f"speexdec存在: {check_tool_exists('speexdec')}")

        if not check_tool_exists("speexdec") and not check_tool_exists(FFMPEG_PATH):
            error_msg = f"缺少 ffmpeg 或 speexdec，请安装或在 FFMPEG_PATH 中指定路径。当前FFMPEG_PATH: {FFMPEG_PATH}"
            logger.error(f"ASR接口错误: {error_msg}")
            return jsonify({"error": error_msg}), 500

        f = request.files["audio"]
        logger.info(f"音频文件信息: 文件名={f.filename}, 大小={f.content_length or '未知'} bytes")

        with tempfile.TemporaryDirectory() as td:
            in_path = pathlib.Path(td) / f"input.{f.filename.split('.')[-1]}"
            out_wav = pathlib.Path(td) / "converted.wav"

            logger.info(f"保存音频文件到: {in_path}")
            f.save(in_path)
            logger.info(f"音频文件保存成功，大小: {in_path.stat().st_size} bytes")

            try:
                if in_path.suffix.lower() in ['.spx', '.speex']:
                    if check_tool_exists("speexdec"):
                        logger.info(f"使用 speexdec 解码 speex 文件: {in_path}")
                        subprocess.run(["speexdec", str(in_path), str(out_wav)],
                                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        logger.info(f"speexdec 不存在，使用 ffmpeg 解码 speex 文件: {in_path}")
                        subprocess.run([FFMPEG_PATH, "-y", "-i", str(in_path),
                                        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(out_wav)],
                                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    logger.info(f"使用 ffmpeg 转换音频文件: {in_path} -> {out_wav}")
                    subprocess.run([FFMPEG_PATH, "-y", "-i", str(in_path),
                                    "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(out_wav)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                logger.info(f"音频转换完成，输出文件: {out_wav}, 大小: {out_wav.stat().st_size} bytes")

            except FileNotFoundError as e:
                error_msg = f"找不到 ffmpeg，请安装或修改 FFMPEG_PATH（当前值：{FFMPEG_PATH}）。错误: {str(e)}"
                logger.error(f"ASR接口错误: {error_msg}")
                return jsonify({"error": error_msg}), 500
            except subprocess.CalledProcessError as e:
                error_msg = f"音频转换失败，请检查文件格式。错误: {str(e)}"
                logger.error(f"ASR接口错误: {error_msg}")
                return jsonify({"error": error_msg}), 500
            except Exception as e:
                error_msg = f"音频转换过程中发生未知错误: {str(e)}"
                logger.error(f"ASR接口错误: {error_msg}")
                return jsonify({"error": error_msg}), 500

            logger.info("开始调用讯飞ASR进行语音识别...")
            text = asr_transcribe_file(str(out_wav))
            logger.info(f"ASR识别完成，结果: '{text}'")

            return jsonify({"text": text})

    except Exception as e:
        error_msg = f"ASR接口处理过程中发生异常: {str(e)}"
        logger.error(f"ASR接口异常: {error_msg}")
        logger.error(f"异常类型: {type(e).__name__}")
        logger.error(f"异常详情: {str(e)}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return jsonify({"error": error_msg}), 500

@app.route("/static/tts/<path:filename>")
def serve_tts(filename):
    return send_from_directory("static/tts", filename)

@app.route("/api/health")
def health():
    return jsonify({"ok": True})

@app.route("/api/asr/health")
def asr_health():
    """ASR接口健康检查"""
    try:
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
                result = subprocess.run([FFMPEG_PATH, "-version"],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    health_status["ffmpeg"]["version"] = version_line
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
        logger.error(f"ASR健康检查失败: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }), 500

@app.route("/api/questionnaire_status", methods=["GET"])
def get_questionnaire_status():
    return jsonify({
        "current_system": "智谱AI",
        "use_zhipu": True
    })

@app.route("/api/local_questionnaire/start", methods=["POST"])
def local_questionnaire_start():
    """启动本地问卷"""
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", str(int(time.time() * 1000)))

        if not hasattr(app, 'questionnaire_sessions'):
            app.questionnaire_sessions = {}

        app.questionnaire_sessions[session_id] = {
            "current_question_index": 0,
            "answers": {},
            "start_time": time.time()
        }

        first_question = questions[0]
        question_info = get_question_info(0)

        # [MOD] 用数字人链路生成音频 & 视频
        try:
            mp3_path, mp4_path, tts_url, video_url = generate_digital_human_assets(
                text=first_question,
                prefix=str(session_id),
                ffmpeg_path=FFMPEG_PATH,
                static_root="static",
            )
        except Exception as e:
            logger.error(f"数字人生成失败（local start）：{e}")
            tts_url = ""
            video_url = ""

        return jsonify({
            "session_id": session_id,
            "question": first_question,
            "question_info": question_info,
            "tts_url": tts_url,       # [MOD]
            "video_url": video_url,   # [ADD]
            "progress": f"1/{len(questions)}",
            "total_questions": len(questions)
        })

    except Exception as e:
        logger.error(f"启动本地问卷失败: {e}")
        return jsonify({"error": f"启动失败: {str(e)}"}), 500

@app.route("/api/local_questionnaire/reply", methods=["POST"])
def local_questionnaire_reply():
    """提交本地问卷回答"""
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

            # [MOD] 把报告也做成数字人视频 + 语音
            try:
                mp3_path, mp4_path, tts_url, video_url = generate_digital_human_assets(
                    text=report,
                    prefix=f"{session_id}_report",
                    ffmpeg_path=FFMPEG_PATH,
                    static_root="static",
                )
            except Exception as e:
                logger.error(f"数字人生成失败（local report）：{e}")
                tts_url = ""
                video_url = ""

            return jsonify({
                "session_id": session_id,
                "question": report,
                "tts_url": tts_url,        # [MOD]
                "video_url": video_url,    # [ADD]
                "is_complete": True,
                "progress": f"{len(questions)}/{len(questions)}",
                "total_questions": len(questions)
            })
        else:
            next_question = questions[next_index]
            question_info = get_question_info(next_index)
            session["current_question_index"] = next_index

            # [MOD] 对下一题同样生成音频 & 视频
            try:
                mp3_path, mp4_path, tts_url, video_url = generate_digital_human_assets(
                    text=next_question,
                    prefix=str(session_id),
                    ffmpeg_path=FFMPEG_PATH,
                    static_root="static",
                )
            except Exception as e:
                logger.error(f"数字人生成失败（local reply）：{e}")
                tts_url = ""
                video_url = ""

            return jsonify({
                "session_id": session_id,
                "question": next_question,
                "question_info": question_info,
                "tts_url": tts_url,      # [MOD]
                "video_url": video_url,  # [ADD]
                "is_complete": False,
                "progress": f"{next_index + 1}/{len(questions)}",
                "total_questions": len(questions)
            })

    except Exception as e:
        logger.error(f"本地问卷回答失败: {e}")
        return jsonify({"error": f"提交失败: {str(e)}"}), 500

@app.route("/api/local_questionnaire/status/<session_id>", methods=["GET"])
def get_local_questionnaire_status(session_id):
    """获取本地问卷状态"""
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
    """获取问题信息，包括分类和格式要求"""
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

def generate_assessment_report(answers):
    """生成评估报告"""
    report = "肺癌早筛风险评估报告\n\n"
    report += "=" * 50 + "\n\n"

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

    if "吸烟史(1是 2否)" in answers and answers["吸烟史(1是 2否)"] == "1":
        report += "⚠️ 吸烟史：有吸烟史，增加肺癌风险\n"
        if "累计吸烟年数" in answers and "吸烟频率(支/天)" in answers:
            try:
                years = float(answers["累计吸烟年数"])
                daily = float(answers["吸烟频率(支/天)"])
                pack_years = (years * daily) / 20
                if pack_years > 30:
                    report += f"   重度吸烟：{pack_years:.1f}包年，高风险\n"
                elif pack_years > 20:
                    report += f"   中度吸烟：{pack_years:.1f}包年，中风险\n"
                else:
                    report += f"   轻度吸烟：{pack_years:.1f}包年，低风险\n"
            except:
                report += "   吸烟情况：需进一步评估\n"

    if "被动吸烟(1否 2是)" in answers and answers["被动吸烟(1否 2是)"] == "2":
        report += "⚠️ 被动吸烟：存在被动吸烟情况\n"

    if "职业致癌物质接触(1有 2无)" in answers and answers["职业致癌物质接触(1有 2无)"] == "1":
        report += "⚠️ 职业暴露：存在职业致癌物质接触\n"

    if "三代以内直系亲属肺癌家族史(1有 2无)" in answers and answers["三代以内直系亲属肺癌家族史(1有 2无)"] == "1":
        report += "⚠️ 家族史：存在肺癌家族史，遗传风险增加\n"

    if "最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)" in answers and answers["最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)"] == "1":
        report += "⚠️ 症状：存在可疑症状，建议及时就医\n"

    if "一年内胸部CT检查(1是 2否)" in answers and answers["一年内胸部CT检查(1是 2否)"] == "2":
        report += "📋 建议：建议进行胸部CT检查\n"

    report += "\n【总体评估】\n"

    risk_score = 0
    if "吸烟史(1是 2否)" in answers and answers["吸烟史(1是 2否)"] == "1":
        risk_score += 3
    if "被动吸烟(1否 2是)" in answers and answers["被动吸烟(1否 2是)"] == "2":
        risk_score += 1
    if "职业致癌物质接触(1有 2无)" in answers and answers["职业致癌物质接触(1有 2无)"] == "1":
        risk_score += 2
    if "三代以内直系亲属肺癌家族史(1有 2无)" in answers and answers["三代以内直系亲属肺癌家族史(1有 2无)"] == "1":
        risk_score += 2
    if "最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)" in answers and answers["最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)"] == "1":
        risk_score += 3

    if risk_score >= 6:
        report += "🔴 高风险：建议立即就医，进行详细检查\n"
    elif risk_score >= 3:
        report += "🟡 中风险：建议定期体检，关注症状变化\n"
    else:
        report += "🟢 低风险：保持健康生活方式，定期体检\n"

    report += "\n【建议措施】\n"
    report += "1. 戒烟限酒，避免二手烟\n"
    report += "2. 保持室内通风，减少油烟接触\n"
    report += "3. 定期体检，关注肺部健康\n"
    report += "4. 如有异常症状，及时就医\n"
    report += "5. 保持健康生活方式，适量运动\n"

    report += "\n" + "=" * 50 + "\n"
    report += f"报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"

    return report

@app.route("/api/assessment_report/<session_id>", methods=["GET"])
def get_assessment_report(session_id):
    """获取指定会话的评估报告"""
    try:
        return jsonify({
            "session_id": session_id,
            "has_report": True,
            "message": "评估报告已生成，请查看对话历史"
        })
    except Exception as e:
        logger.error(f"获取评估报告失败: {e}")
        return jsonify({"error": f"获取评估报告失败: {str(e)}"}), 500

@app.route("/api/debug/zhipu", methods=["POST"])
def debug_zhipu():
    """调试智谱AI连接"""
    try:
        data = request.get_json(force=True)
        test_prompt = data.get("prompt", "请简单回复：测试成功")

        logger.info(f"测试智谱AI连接，提示词: {test_prompt}")

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
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }), 500

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
