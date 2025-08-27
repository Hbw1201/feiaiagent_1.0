# app.py
import os, pathlib, shutil, subprocess, tempfile, logging, time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from zhipu_agent import zhipu_conversation
from xfyun_asr import asr_transcribe_file
from config import validate_config, TTS_OUT_DIR, FFMPEG_PATH, questions, questionnaire_reference

# 数字人模块（生成 & 预热）
# 注意：digital_human.py 需为“极速版”，其 generate_digital_human_assets 返回 5 个值
from digital_human import generate_digital_human_assets, warmup_tts

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

            # 报告很长 -> 先做“摘要快视频”（6~8秒）
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

