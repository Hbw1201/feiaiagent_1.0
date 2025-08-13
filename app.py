# app.py
import os, pathlib, shutil, subprocess, tempfile, logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from config import validate_config, TTS_OUT_DIR, FFMPEG_PATH
from zhipu_agent import zhipu_conversation
from xfyun_asr import asr_transcribe_file
from xfyun_tts import tts_text_to_mp3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

validate_config()

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
    
    mp3_path = tts_text_to_mp3(question, out_dir=TTS_OUT_DIR, prefix=final_session_id)
    filename = mp3_path.name
    tts_url = f"/static/tts/{filename}"
    
    return jsonify({"session_id": final_session_id, "question": question, "tts_url": tts_url})

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
        
        # 检查是否完成 - 通过检查响应内容来判断
        # 注意：不包含"未获取到有效回复"，因为这只是API调用失败，不是问卷完成
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
            len(ai_response) > 800  # 如果回复很长，可能是评估报告（提高阈值）
        )
        
        # 首先检查是否是API调用失败
        if "未获取到有效回复" in ai_response or "java.lang.IllegalArgumentException" in ai_response or "Agent流程错误" in ai_response:
            logger.error(f"智谱AI调用失败或中断: {ai_response}")
            
            # 检查是否是Agent流程错误（节点报错）
            if "Agent流程错误" in ai_response:
                logger.info("检测到Agent流程错误，尝试重新询问当前问题...")
                
                # 尝试重新询问当前问题，而不是重新开始整个问卷
                try:
                    retry_response, retry_conversation_id = zhipu_conversation(
                        prompt=f"用户回答：{answer_text}。请重新询问刚才的问题，如果用户回答有误，请给出更清晰的提示或重新表述问题。",
                        conversation_id=session_id
                    )
                    
                    if "未获取到有效回复" not in retry_response and "java.lang.IllegalArgumentException" not in retry_response and "Agent流程错误" not in retry_response:
                        logger.info("重新询问成功，继续对话")
                        question = retry_response
                        is_complete = False
                        final_session_id = retry_conversation_id
                    else:
                        logger.error("重新询问失败，尝试重新开始对话")
                        # 如果重新询问也失败，则尝试重新开始
                        question = "刚才的问题出现了错误，让我重新开始询问。请告诉我您的姓名。"
                        is_complete = False
                        # 创建新的会话
                        new_response, new_conversation_id = zhipu_conversation(
                            prompt="请开始肺癌早筛问卷，询问用户姓名"
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
                # 其他类型的API错误，尝试重新开始对话
                try:
                    logger.info("尝试重新开始对话...")
                    retry_response, retry_conversation_id = zhipu_conversation(
                        prompt="请重新开始肺癌早筛问卷，询问用户姓名"
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
                except Exception as retry_e:
                    logger.error(f"重试失败: {retry_e}")
                    question = "智谱AI暂时不可用，请稍后重试。错误：Agent流程中断"
                    is_complete = False
        elif is_completed:
            # 问卷完成，直接使用ai_response
            logger.info("检测到问卷完成")
            logger.info(f"ai_response内容长度: {len(ai_response)}")
            question = ai_response
            is_complete = True
        else:
            # 继续下一个问题
            question = ai_response
            logger.info(f"智谱AI继续对话成功: {question}")
            is_complete = False
        
        final_session_id = conversation_id
        
    except Exception as e:
        logger.error(f"智谱AI调用失败: {e}")
        question = "系统暂时不可用，请稍后重试"
        final_session_id = session_id
        is_complete = False
    
    mp3_path = tts_text_to_mp3(question, out_dir=TTS_OUT_DIR, prefix=final_session_id)
    filename = mp3_path.name
    tts_url = f"/static/tts/{filename}"
    
    return jsonify({
        "session_id": final_session_id, 
        "question": question, 
        "tts_url": tts_url,
        "is_complete": is_complete
    })

@app.route("/api/asr", methods=["POST"])
def asr():
    if "audio" not in request.files:
        return jsonify({"error": "no audio field"}), 400

    if not check_tool_exists("speexdec") and not check_tool_exists(FFMPEG_PATH):
        return jsonify({"error": "缺少 ffmpeg 或 speexdec，请安装或在 FFMPEG_PATH 中指定路径"}), 500

    f = request.files["audio"]
    with tempfile.TemporaryDirectory() as td:
        in_path  = pathlib.Path(td) / f"input.{f.filename.split('.')[-1]}"
        out_wav  = pathlib.Path(td) / "converted.wav"
        f.save(in_path)

        try:
            if in_path.suffix.lower() in ['.spx', '.speex']:
                if check_tool_exists("speexdec"):
                    subprocess.run(["speexdec", str(in_path), str(out_wav)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    logger.info(f"使用 speexdec 解码 speex 文件: {in_path}")
                else:
                    logger.info(f"speexdec 不存在，使用 ffmpeg 解码 speex 文件: {in_path}")
                    subprocess.run([FFMPEG_PATH, "-y", "-i", str(in_path),
                                    "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(out_wav)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run([FFMPEG_PATH, "-y", "-i", str(in_path),
                                "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(out_wav)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            return jsonify({"error": f"找不到 ffmpeg，请安装或修改 FFMPEG_PATH（当前值：{FFMPEG_PATH}）"}), 500
        except subprocess.CalledProcessError:
            return jsonify({"error": "音频转换失败，请检查文件格式"}), 500

        text = asr_transcribe_file(str(out_wav))
        return jsonify({"text": text})

@app.route("/static/tts/<path:filename>")
def serve_tts(filename):
    return send_from_directory("static/tts", filename)

@app.route("/api/health")
def health():
    return jsonify({"ok": True})

@app.route("/api/questionnaire_status", methods=["GET"])
def get_questionnaire_status():
    return jsonify({
        "current_system": "智谱AI",
        "use_zhipu": True
    })

@app.route("/api/assessment_report/<session_id>", methods=["GET"])
def get_assessment_report(session_id):
    """获取指定会话的评估报告"""
    try:
        # 这里可以添加从数据库或缓存中获取评估报告的逻辑
        # 目前先返回一个示例响应
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
        
        # 测试智谱AI连接
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
