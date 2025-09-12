# app.py
import os, pathlib, shutil, subprocess, tempfile, logging, time, sys, asyncio, threading
import concurrent.futures
from functools import lru_cache
from pathlib import Path

# 使用路径配置管理
try:
    from path_config import LOCAL_QUESTIONNAIRE_PATH
    os.environ["LOCAL_QUESTIONNAIRE_PATH"] = LOCAL_QUESTIONNAIRE_PATH
except ImportError:
    # 回退到默认配置
    LOCAL_QUESTIONNAIRE_PATH = os.getenv("LOCAL_QUESTIONNAIRE_PATH")
    if not LOCAL_QUESTIONNAIRE_PATH:
        LOCAL_QUESTIONNAIRE_PATH = str(pathlib.Path(__file__).parent / "local_questionnaire.py")
    os.environ["LOCAL_QUESTIONNAIRE_PATH"] = LOCAL_QUESTIONNAIRE_PATH
from flask import Flask, request, jsonify, send_from_directory
# from flask_cors import CORS  # 临时注释，避免依赖问题

# External integrations (robust import)
try:
    from zhipu_agent import zhipu_conversation
except Exception as _e:
    logging.getLogger(__name__).warning(f"加载 zhipu_agent 失败，使用降级实现: {_e}")
    def zhipu_conversation(prompt, conversation_id=None):
        return ("系统暂时不可用，请稍后重试", conversation_id or str(int(time.time()*1000)))

try:
    from xfyun_asr import asr_transcribe_file
except Exception as _e:
    logging.getLogger(__name__).warning(f"加载 xfyun_asr 失败，ASR将返回空: {_e}")
    def asr_transcribe_file(path):
        return ""

try:
    from config import validate_config, TTS_OUT_DIR, FFMPEG_PATH
except Exception as _e:
    logging.getLogger(__name__).warning(f"加载 config 失败，使用默认值: {_e}")
    TTS_OUT_DIR = "static/tts"
    FFMPEG_PATH = "ffmpeg"
    def validate_config():
        return True

from local_questionnaire import questions, questionnaire_reference, generate_assessment_report, get_question_info

# 数字人模块（生成 & 预热）- 暂时注释掉，使用预录制视频
# 注意：digital_human.py 需为"极速版"，其 generate_digital_human_assets 返回 5 个值
# from digital_human import generate_digital_human_assets, warmup_tts
try:
    from xfyun_tts import tts_text_to_mp3
except Exception as _e:
    logging.getLogger(__name__).warning(f"加载 xfyun_tts 失败，TTS将返回空: {_e}")
    def tts_text_to_mp3(text, out_dir, basename):
        return pathlib.Path(out_dir) / "warmup.wav"
from report_manager import report_manager
from intelligent_questionnaire_manager import IntelligentQuestionnaireManager

# ===== 全局线程池和缓存管理 =====
_global_thread_pool = None
_app_cache = {}
_cache_lock = threading.Lock()

def get_global_thread_pool():
    """获取全局线程池"""
    global _global_thread_pool
    if _global_thread_pool is None:
        _global_thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=8,  # 根据系统资源调整
            thread_name_prefix="app_worker"
        )
    return _global_thread_pool

def cleanup_global_thread_pool():
    """清理全局线程池"""
    global _global_thread_pool
    if _global_thread_pool:
        _global_thread_pool.shutdown(wait=True)
        _global_thread_pool = None

@lru_cache(maxsize=1000)
def _cached_question_processing(question_text: str, session_id: str) -> str:
    """缓存问题处理结果"""
    return question_text

# ===== 集成 MetaGPT 问卷工作流（DeepSeek） =====
_metagpt_init_ok = False
_metagpt_lock = threading.Lock()
_metagpt_workflow = None
_metagpt_error = None

# ===== 共享答案验证器实例 =====
_shared_answer_validator = None
_validator_lock = threading.Lock()

def get_shared_answer_validator():
    """获取共享的答案验证器实例（单例模式）"""
    global _shared_answer_validator
    if _shared_answer_validator is None:
        with _validator_lock:
            if _shared_answer_validator is None:
                try:
                    from metagpt_questionnaire.agents.answer_validator import AnswerValidatorAgent
                    _shared_answer_validator = AnswerValidatorAgent()
                    logger.info("✅ 共享答案验证器初始化成功")
                except Exception as e:
                    logger.error(f"❌ 共享答案验证器初始化失败: {e}")
                    return None
    return _shared_answer_validator

def _init_metagpt_if_needed():
    global _metagpt_init_ok, _metagpt_workflow, _metagpt_error
    if _metagpt_init_ok and _metagpt_workflow is not None:
        return True
    
    with _metagpt_lock:
        if _metagpt_init_ok and _metagpt_workflow is not None:
            return True
        
        try:
            logger.info("🚀 开始初始化 MetaGPT 问卷工作流...")
            
            # 1. 确保路径正确
            current_file = pathlib.Path(__file__).resolve()
            project_root = current_file.parent  # feiaiagent/
            metagpt_dir = project_root / "metagpt_questionnaire"
            
            if not metagpt_dir.exists():
                _metagpt_error = f"MetaGPT 目录不存在: {metagpt_dir}"
                logger.error(_metagpt_error)
                return False
            
            # 2. 添加路径到 sys.path（如果尚未添加）
            paths_to_add = [str(project_root)]
            for path in paths_to_add:
                if path not in sys.path:
                    sys.path.insert(0, path)
            
            logger.info(f"✅ MetaGPT 路径已确认: {metagpt_dir}")
            
            # 3. 检查环境变量配置
            deepseek_key = os.getenv("DEEPSEEK_API_KEY")
            if not deepseek_key or deepseek_key.startswith("your-"):
                logger.warning("⚠️ DEEPSEEK_API_KEY 未配置，MetaGPT 将使用降级模式")
            
            # 4. 尝试导入核心模块
            try:
                from metagpt_questionnaire.config.metagpt_config import validate_config, get_llm_config
                from metagpt_questionnaire.agents.base_agent import agent_registry
                logger.info("✅ 核心模块导入成功")
            except ImportError as e:
                _metagpt_error = f"核心模块导入失败: {e}"
                logger.error(_metagpt_error)
                return False
            
            # 5. 导入并注册智能体（容错处理）
            agent_classes = []
            try:
                from metagpt_questionnaire.agents.questionnaire_designer import QuestionnaireDesignerAgent
                agent_classes.append(QuestionnaireDesignerAgent)
            except Exception as e:
                logger.warning(f"导入 QuestionnaireDesignerAgent 失败: {e}")
            
            try:
                from metagpt_questionnaire.agents.risk_assessor import RiskAssessorAgent
                agent_classes.append(RiskAssessorAgent)
            except Exception as e:
                logger.warning(f"导入 RiskAssessorAgent 失败: {e}")
            
            try:
                from metagpt_questionnaire.agents.data_analyzer import DataAnalyzerAgent
                agent_classes.append(DataAnalyzerAgent)
            except Exception as e:
                logger.warning(f"导入 DataAnalyzerAgent 失败: {e}")
            
            try:
                from metagpt_questionnaire.agents.report_generator import ReportGeneratorAgent
                agent_classes.append(ReportGeneratorAgent)
            except Exception as e:
                logger.warning(f"导入 ReportGeneratorAgent 失败: {e}")
            
            try:
                from metagpt_questionnaire.agents.conversational_interviewer import ConversationalInterviewerAgent
                agent_classes.append(ConversationalInterviewerAgent)
            except Exception as e:
                logger.warning(f"导入 ConversationalInterviewerAgent 失败: {e}")
            
            try:
                from metagpt_questionnaire.agents.answer_validator import AnswerValidatorAgent
                agent_classes.append(AnswerValidatorAgent)
            except Exception as e:
                logger.warning(f"导入 AnswerValidatorAgent 失败: {e}")
            
            # 6. 注册智能体
            registered_count = 0
            for agent_class in agent_classes:
                try:
                    agent_registry.register(agent_class)
                    registered_count += 1
                except Exception as e:
                    logger.warning(f"注册智能体 {agent_class.__name__} 失败: {e}")
            
            logger.info(f"✅ 已注册 {registered_count} 个智能体")
            
            # 7. 验证配置（允许失败）
            config_ok = False
            try:
                config_ok = validate_config()
                if config_ok:
                    logger.info("✅ MetaGPT 配置验证通过")
                else:
                    logger.warning("⚠️ MetaGPT 配置验证失败，将使用降级模式")
            except Exception as e:
                logger.warning(f"⚠️ MetaGPT 配置验证异常: {e}")
            
            # 8. 创建工作流
            try:
                from metagpt_questionnaire.workflows.questionnaire_workflow import create_workflow
                _metagpt_workflow = create_workflow("standard")
                
                # 测试工作流状态
                status = _metagpt_workflow.get_agent_status()
                logger.info(f"✅ 工作流创建成功，智能体数量: {status.get('total_agents', 0)}")
                
                _metagpt_init_ok = True
                _metagpt_error = None
                logger.info("🎉 MetaGPT 问卷工作流初始化完成")
                return True
                
            except Exception as e:
                _metagpt_error = f"工作流创建失败: {e}"
                logger.error(_metagpt_error)
                return False
                
        except Exception as e:
            _metagpt_error = f"MetaGPT 初始化失败: {e}"
            logger.error(_metagpt_error)
            _metagpt_init_ok = False
            _metagpt_workflow = None
            return False

def get_metagpt_status():
    """获取 MetaGPT 状态信息"""
    return {
        "initialized": _metagpt_init_ok,
        "workflow": _metagpt_workflow is not None,
        "error": _metagpt_error
    }

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    validate_config()
except Exception as e:
    logging.getLogger(__name__).warning(f"配置验证失败（忽略以便先启动）：{e}")

app = Flask(__name__, static_url_path="/static", static_folder="static")
# CORS(app)  # 临时注释，避免依赖问题

# --------- 缓存控制 ---------
@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# --------- 启动预热（首句加速） ---------
# try:
#     warmup_tts(static_root="static")  
# except Exception as _:
#     logger.warning("TTS 预热失败（忽略）")

def check_tool_exists(tool_name_or_path):
    return shutil.which(tool_name_or_path) is not None or pathlib.Path(tool_name_or_path).exists()

# 清理 TTS 目录（在开始新问卷前清空上一次音频）
def clear_tts_dir(keep_names=None) -> int:
    try:
        keep = set(keep_names or [])
        tts_dir = pathlib.Path(TTS_OUT_DIR)
        if not tts_dir.exists():
            return 0
        deleted = 0
        for p in list(tts_dir.glob("*.mp3")) + list(tts_dir.glob("*.wav")):
            if p.name in keep:
                continue
            try:
                p.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"删除TTS文件失败: {p} -> {e}")
        if deleted:
            logger.info(f"已清理 TTS 文件 {deleted} 个")
        return deleted
    except Exception as e:
        logger.warning(f"清理TTS目录时出错: {e}")
        return 0

# 新增：生成TTS音频的函数（异步版本）
def generate_tts_audio_async(text: str, session_id: str) -> str:
    """
    使用讯飞TTS生成音频文件，返回音频URL（异步版本）
    """
    # 检查缓存
    cache_key = f"tts_{hash(text)}_{session_id}"
    with _cache_lock:
        if cache_key in _app_cache:
            cached_url = _app_cache[cache_key]
            if cached_url and cached_url.startswith("/static/tts/"):
                # 验证文件是否存在
                file_path = pathlib.Path("static") / "tts" / cached_url.split("/")[-1]
                if file_path.exists():
                    logger.info(f"使用TTS缓存: {cached_url}")
                    return cached_url
    
    # 在线程池中执行TTS生成
    thread_pool = get_global_thread_pool()
    future = thread_pool.submit(_generate_tts_audio_sync, text, session_id)
    
    try:
        result = future.result(timeout=30)  # 30秒超时
        if result:
            # 缓存结果
            with _cache_lock:
                _app_cache[cache_key] = result
            return result
        return ""
    except concurrent.futures.TimeoutError:
        logger.error(f"TTS生成超时: {text[:50]}...")
        return ""
    except Exception as e:
        logger.error(f"TTS生成异常: {e}")
        return ""

def _generate_tts_audio_sync(text: str, session_id: str) -> str:
    """
    同步版本的TTS音频生成函数（内部使用）
    """
    try:
        # 确保TTS输出目录存在
        tts_dir = pathlib.Path(TTS_OUT_DIR)
        tts_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成TTS音频文件
        audio_path = tts_text_to_mp3(text, tts_dir, f"session_{session_id}")
        
        if audio_path and audio_path.exists():
            # 返回音频文件的URL
            audio_filename = audio_path.name
            tts_url = f"/static/tts/{audio_filename}"
            logger.info(f"TTS音频生成成功: {tts_url}")
            return tts_url
        else:
            # 回退到预热音频，确保前端不因空URL卡住
            warmup = tts_dir / "warmup.wav"
            if warmup.exists():
                logger.warning("TTS生成失败，回退到 warmup.wav")
                return f"/static/tts/{warmup.name}"
            logger.error("TTS音频生成失败且无回退文件")
            return ""
            
    except Exception as e:
        logger.error(f"生成TTS音频时出错: {e}")
        # 发生异常也尝试回退
        try:
            tts_dir = pathlib.Path(TTS_OUT_DIR)
            warmup = tts_dir / "warmup.wav"
            if warmup.exists():
                return f"/static/tts/{warmup.name}"
        except Exception:
            pass
        return ""

def generate_tts_audio(text: str, session_id: str) -> str:
    """
    使用讯飞TTS生成音频文件，返回音频URL
    默认使用异步版本以提升性能
    """
    return generate_tts_audio_async(text, session_id)

# 简单“回答有效性”判定：本地规则，可扩展为LLM
def validate_user_answer(answer_text: str, question_text: str) -> (bool, str):
    try:
        text = (answer_text or "").strip()
        if not text:
            return False, "未识别到有效内容"
        if len(text) < 2:
            return False, "回答过短"
        generic_list = [
            "不知道", "不清楚", "随便", "无", "没了", "没有", "嗯", "啊", "ok", "好的", "还行",
            "是", "否", "不知道呢", "记不清", "忘了"
        ]
        if any(g in text for g in generic_list):
            # 如问题是数值/选择题，还可进一步约束；此处先给出一般判定
            return False, "回答不够具体"
        # 与问题文本高度重复（复述问题）
        if question_text:
            qt = question_text.strip()
            if len(qt) >= 6 and text in qt:
                return False, "疑似复述问题而非作答"
        return True, "ok"
    except Exception:
        # 容错：判定异常则放行，避免阻断流程
        return True, "ok"

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
TARGET_SECS = 7           # 单段目标 6~8 秒（更像"实时"）
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

def split_for_avatar(text: str, target_secs: int = TARGET_SECS):
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

    # 开始新会话前清理上次音频（保留占位/预热文件）
    clear_tts_dir(keep_names=["warmup.wav", "beep.wav"])  # 若无则忽略

    try:
        logger.info(f"智谱AI开始对话，会话ID: {session_id}")

        ai_response, conversation_id = zhipu_conversation(
            prompt="请开始询问肺癌早筛问卷中的第一个问题。",
            conversation_id=session_id
        )

        question = ai_response
        final_session_id = conversation_id

    except Exception as e:
        logger.error(f"智谱AI调用失败: {e}")
        question = "系统暂时不可用，请稍后重试"
        final_session_id = session_id

    # 注释掉数字人生成，改为使用预录制视频和TTS
    # try:
    #     wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
    #         text=shorten_for_avatar(question),
    #         prefix=str(final_session_id),
    #         ffmpeg_path=FFMPEG_PATH,
    #         static_root="static",
    #     )
    # except Exception as e:
    #     logger.error(f"数字人生成失败，回退为最小可用响应：{e}")
    #     tts_url = ""
    #     video_url = ""
    #     video_stream_url = ""

    # 使用预录制视频和TTS音频
    video_url = "/static/video/human.mp4"
    video_stream_url = "/static/video/human.mp4"
    tts_url = generate_tts_audio(shorten_for_avatar(question), final_session_id)

    return jsonify({
        "session_id": final_session_id,
        "question": question,
        "tts_url": tts_url,
        "video_url": video_url,
        "video_stream_url": video_stream_url  # ★ 前端优先用它"即播"
    })

# ========= MetaGPT 问卷（逐题）=========
@app.route("/api/metagpt_agent/start", methods=["POST"])
def metagpt_agent_start():
    """
    使用 MetaGPT 问卷工作流进行逐题问答的启动接口：
    - 初始化 MetaGPT（如未初始化）
    - 创建问卷模板并保存至会话
    - 返回第一题，并生成 TTS 与固定人像视频 URL
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", str(int(time.time() * 1000)))

        # 初始化 MetaGPT 工作流
        if not _init_metagpt_if_needed():
            return jsonify({"error": "MetaGPT 初始化失败"}), 500

        # 清理上次音频（保留占位/预热文件）
        clear_tts_dir(keep_names=["warmup.wav", "beep.wav"])

        # 仅使用本地问卷定义
        from metagpt_questionnaire.agents.questionnaire_designer import QuestionnaireDesignerAgent
        designer = QuestionnaireDesignerAgent()
        questionnaire = _run_async(designer.design_questionnaire({
            "source": "local",
            "local_questionnaire_path": os.environ.get("LOCAL_QUESTIONNAIRE_PATH")
        }))

        # 建立会话状态
        if not hasattr(app, 'metagpt_sessions'):
            app.metagpt_sessions = {}
        app.metagpt_sessions[session_id] = {
            "questionnaire": questionnaire,
            "current_index": 0,
            "responses": [],  # List[UserResponse]
            "start_time": time.time()
        }

        first_q = questionnaire.questions[0]
        question_text = first_q.text

        # 生成 TTS 与固定视频
        video_url = "/static/video/human.mp4"
        video_stream_url = "/static/video/human.mp4"
        tts_url = generate_tts_audio(shorten_for_avatar(question_text), session_id)

        return jsonify({
            "session_id": session_id,
            "question": question_text,
            "tts_url": tts_url,
            "video_url": video_url,
            "video_stream_url": video_stream_url,
            "is_complete": False
        })
    except Exception as e:
        logger.error(f"MetaGPT 问卷启动失败: {e}")
        return jsonify({"error": f"启动失败: {str(e)}"}), 500


@app.route("/api/metagpt_agent/reply", methods=["POST"])
def metagpt_agent_reply():
    """
    使用 MetaGPT 问卷工作流进行逐题问答的回复接口：
    - 记录本题用户回答
    - 若未完成，返回下一题（含 TTS 与固定视频 URL）
    - 若完成，调用工作流进行分析/报告生成并保存报告，返回报告文本
    """
    try:
        data = request.get_json(force=True)
        session_id = data["session_id"]
        answer_text = data.get("answer", "").strip()

        if not hasattr(app, 'metagpt_sessions') or session_id not in app.metagpt_sessions:
            return jsonify({"error": "会话不存在"}), 400

        sess = app.metagpt_sessions[session_id]
        questionnaire = sess["questionnaire"]
        idx = sess["current_index"]

        # 当前题目与回答判定
        from metagpt_questionnaire.models.questionnaire import UserResponse
        current_q = questionnaire.questions[idx]
        
        # 使用"回答判定/回退智能体"解析意图和验证答案（只调用一次）
        try:
            validator = get_shared_answer_validator()
            if validator:
                decision = _run_async(validator.run(answer_text, current_q.text, idx, len(questionnaire.questions)))
                logger.info(f"🔍 答案验证结果: {decision}")
            else:
                raise Exception("答案验证器初始化失败")
        except Exception as e:
            logger.warning(f"答案验证智能体调用失败: {e}")
            # 降级到基本验证
            is_valid, reason = validate_user_answer(answer_text, current_q.text)
            decision = {
                "redo": False,
                "valid": is_valid,
                "reason": reason if not is_valid else "基本验证通过"
            }

        # 1. 优先处理关键词检测和重新回答意图
        if decision.get("detected") or decision.get("redo"):
            # 回退到指定位并重问
            target_index = int(decision.get("target_index", idx))
            target_index = max(0, min(target_index, len(questionnaire.questions) - 1))
            sess["current_index"] = target_index
            
            # 处理清空答案的逻辑
            if decision.get("clear_all_answers"):
                # 清空所有答案
                sess["responses"].clear()
                logger.info("🔄 已清空所有答案，重新开始问卷")
            elif decision.get("clear_previous_answer"):
                # 清空指定问题的答案
                sess["responses"] = [
                    response for response in sess["responses"]
                    if response.question_id != questionnaire.questions[target_index].id
                ]
                logger.info(f"🔄 已清空第{target_index + 1}题的答案")
            
            target_q = questionnaire.questions[target_index]
            # 构建包含具体问题内容的返回消息
            base_message = decision.get("message", f"好的，我们回到第{target_index + 1}题")
            message = f"{base_message}，请重新回答：{target_q.text}"
            
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(message), session_id)

            return jsonify({
                "session_id": session_id,
                "question": message,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": False,
                "progress": f"{target_index + 1}/{len(questionnaire.questions)}",
                "total_questions": len(questionnaire.questions),
                "redo": True,
                "redo_target_index": target_index,
                "intent_type": decision.get("intent_type", "重新回答"),
                "message": decision.get("message", "请重新回答这个问题。")
            })

        # 2. 处理跳过意图
        if decision.get("skip"):
            target_index = int(decision.get("target_index", idx + 1))
            target_index = max(0, min(target_index, len(questionnaire.questions) - 1))
            sess["current_index"] = target_index
            
            message = decision.get("message", "好的，我们跳过这道题。")
            
            # 检查是否完成
            if target_index >= len(questionnaire.questions):
                # 问卷完成
                report_text = "问卷已完成，感谢您的参与。"
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(report_text), session_id)
                
                return jsonify({
                    "session_id": session_id,
                    "question": report_text,
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": True,
                    "progress": f"{len(questionnaire.questions)}/{len(questionnaire.questions)}",
                    "total_questions": len(questionnaire.questions),
                    "skip": True
                })
            
            # 获取下一个问题
            next_q = questionnaire.questions[target_index]
            next_message = f"{message}\n\n{next_q.text}"
            
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(next_message), session_id)
            
            return jsonify({
                "session_id": session_id,
                "question": next_message,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": False,
                "progress": f"{target_index + 1}/{len(questionnaire.questions)}",
                "total_questions": len(questionnaire.questions),
                "skip": True
            })

        # 3. 处理答案有效性验证
        if not decision.get("valid", True):
            # 答案无效，重问当前题
            reason = decision.get("reason", "回答不够具体")
            suggestion = decision.get("suggestion", "请提供更详细的回答")
            hint = f"{reason}。{suggestion}。请重新回答：{current_q.text}"
            
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(hint), session_id)

            return jsonify({
                "session_id": session_id,
                "question": hint,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": False,
                "progress": f"{idx + 1}/{len(questionnaire.questions)}",
                "total_questions": len(questionnaire.questions),
                "invalid_answer": True,
                "invalid_reason": reason,
                "suggestion": suggestion,
                "retry": True
            })

        # 3. 答案有效，记录并继续
        # 检查是否为敏感信息跳过
        if decision.get("sensitive_skip"):
            # 对于敏感信息跳过，记录为"不方便提供"
            sess["responses"].append(UserResponse(question_id=current_q.id, answer="不方便提供"))
            logger.info(f"🔒 用户选择不回答敏感信息问题: {current_q.text}")
        else:
            sess["responses"].append(UserResponse(question_id=current_q.id, answer=answer_text))

        next_index = idx + 1
        if next_index < len(questionnaire.questions):
            # 继续下一题
            sess["current_index"] = next_index
            next_q = questionnaire.questions[next_index]

            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(next_q.text), session_id)

            return jsonify({
                "session_id": session_id,
                "question": next_q.text,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": False,
                "progress": f"{next_index + 1}/{len(questionnaire.questions)}",
                "total_questions": len(questionnaire.questions)
            })
        else:
            # 问卷完成 -> 调用 MetaGPT 工作流做分析与报告
            if not _init_metagpt_if_needed():
                return jsonify({"error": "MetaGPT 初始化失败"}), 500
            try:
                from metagpt_questionnaire.main import MetaGPTQuestionnaireApp
                app_q = MetaGPTQuestionnaireApp()
                if not app_q.initialize():
                    return jsonify({"error": "MetaGPT 工作流初始化失败"}), 500

                # 运行完整工作流（传入逐题收集的 responses）
                result = _run_async(app_q.run_complete_workflow(
                    user_responses=sess["responses"],
                    user_profile={"session_id": session_id}
                ))

                # 解析报告文本
                report_text = None
                try:
                    report_text = result.get("final_results", {}).get("report", {}).get("content")
                except Exception:
                    report_text = None
                if not report_text:
                    # 回退：用风险评估摘要或简单总结
                    ra = result.get("final_results", {}).get("risk_assessment") or {}
                    report_text = (
                        "肺癌早筛风险评估报告\n\n"
                        f"总体风险: {ra.get('overall_risk','unknown')}\n"
                        f"风险分: {ra.get('risk_score','-')}\n"
                    )

                # 保存报告
                try:
                    # 将回答构造成简易 answers 字典（以问题中文文本为键更友好）
                    answers_map = {}
                    for r in sess["responses"]:
                        try:
                            # 找到问题中文文本
                            q_text = next((q.text for q in questionnaire.questions if q.id == r.question_id), r.question_id)
                            answers_map[q_text] = str(r.answer)
                        except Exception:
                            answers_map[r.question_id] = str(r.answer)
                    _ = report_manager.save_report(report_text, answers_map, session_id)
                    _ = report_manager.save_report_json(report_text, answers_map, session_id)
                    _ = report_manager.save_report_pdf(report_text, answers_map, session_id)
                except Exception as _:
                    logger.warning("保存MetaGPT报告失败（忽略）")

                # TTS 提供一个短摘要段落
                first_seg = shorten_for_avatar(report_text)
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(first_seg, session_id)

                # 可选：清理会话
                sess["completed"] = True

                return jsonify({
                    "session_id": session_id,
                    "question": report_text,
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": True,
                    "progress": f"{len(questionnaire.questions)}/{len(questionnaire.questions)}",
                    "total_questions": len(questionnaire.questions)
                })
            except Exception as e:
                logger.error(f"MetaGPT 工作流执行失败: {e}")
                return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"MetaGPT 问卷回复失败: {e}")
        return jsonify({"error": f"提交失败: {str(e)}"}), 500

# ========= MetaGPT 问卷（对话式）=========
@app.route("/api/metagpt_agent/start_conversational", methods=["POST"])
def metagpt_agent_start_conversational():
    """
    Starts a conversational interview using the ConversationalInterviewerAgent.
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", str(int(time.time() * 1000)))

        if not _init_metagpt_if_needed():
            return jsonify({"error": "MetaGPT initialization failed"}), 500

        clear_tts_dir(keep_names=["warmup.wav", "beep.wav"])

        from metagpt_questionnaire.agents.questionnaire_designer import QuestionnaireDesignerAgent
        designer = QuestionnaireDesignerAgent()
        questionnaire = _run_async(designer.design_questionnaire({
            "source": "local",
            "local_questionnaire_path": os.environ.get("LOCAL_QUESTIONNAIRE_PATH")
        }))

        if not hasattr(app, 'metagpt_sessions'):
            app.metagpt_sessions = {}
        app.metagpt_sessions[session_id] = {
            "questionnaire": questionnaire,
            "current_index": 0,
            "responses": [],
            "start_time": time.time()
        }

        # 使用简化版问卷管理器
        from metagpt_questionnaire.simple_questionnaire_manager import SimpleQuestionnaireManager
        manager = SimpleQuestionnaireManager()
        if not manager.initialize_questionnaire(questionnaire):
            return jsonify({"error": "问卷管理器初始化失败"}), 500
        
        # 获取第一个问题
        result = _run_async(manager.get_next_question())
        
        if result["status"] != "next_question":
            return jsonify({"error": "无法获取首个问题"}), 500
        
        question_text = result["question"]
        
        # 保存管理器到会话
        app.metagpt_sessions[session_id]["manager"] = manager
        app.metagpt_sessions[session_id]["current_index"] = 0

        video_url = "/static/video/human.mp4"
        video_stream_url = "/static/video/human.mp4"
        tts_url = generate_tts_audio(shorten_for_avatar(question_text), session_id)

        return jsonify({
            "session_id": session_id,
            "question": question_text,
            "tts_url": tts_url,
            "video_url": video_url,
            "video_stream_url": video_stream_url,
            "is_complete": False
        })
    except Exception as e:
        logger.error(f"MetaGPT conversational start failed: {e}")
        return jsonify({"error": f"Failed to start: {str(e)}"}), 500


@app.route("/api/metagpt_agent/reply_conversational", methods=["POST"])
def metagpt_agent_reply_conversational():
    """
    Handles a user's reply in a conversational interview with enhanced answer validation.
    """
    try:
        data = request.get_json(force=True)
        session_id = data["session_id"]
        answer_text = data.get("answer", "").strip()

        if not hasattr(app, 'metagpt_sessions') or session_id not in app.metagpt_sessions:
            return jsonify({"error": "Session not found"}), 400

        sess = app.metagpt_sessions[session_id]
        manager = sess.get("manager")
        
        if not manager:
            return jsonify({"error": "问卷管理器未找到"}), 400
        
        # 获取当前问题信息
        current_index = manager.current_question_index
        questionnaire = sess.get("questionnaire")
        
        if questionnaire and current_index < len(questionnaire.questions):
            current_q = questionnaire.questions[current_index]
            
            # 使用增强的答案验证智能体
            try:
                validator = get_shared_answer_validator()
                if validator:
                    decision = _run_async(validator.run(
                        answer_text, 
                        current_q.text, 
                        current_index, 
                        len(questionnaire.questions)
                    ))
                    logger.info(f"🔍 答案验证结果: {decision}")
                else:
                    raise Exception("答案验证器初始化失败")
            except Exception as e:
                logger.warning(f"答案验证智能体调用失败: {e}")
                decision = {"redo": False, "valid": True, "reason": "验证失败，使用默认处理"}
            
            # 1. 优先处理关键词检测和重新回答意图
            if decision.get("detected") or decision.get("redo"):
                target_index = int(decision.get("target_index", current_index))
                target_index = max(0, min(target_index, len(questionnaire.questions) - 1))
                
                # 处理清空答案的逻辑
                if decision.get("clear_all_answers"):
                    # 清空所有答案
                    manager.answered_questions.clear()
                    manager.conversation_history.clear()
                    manager.current_question_index = 0
                    sess["current_index"] = 0
                    logger.info("🔄 已清空所有答案，重新开始问卷")
                elif decision.get("clear_previous_answer"):
                    # 清空指定问题的答案
                    manager._clear_answer_at_index(target_index)
                    manager.current_question_index = target_index
                    sess["current_index"] = target_index
                    logger.info(f"🔄 已清空第{target_index + 1}题的答案")
                else:
                    # 更新管理器状态
                    manager.current_question_index = target_index
                    sess["current_index"] = target_index
                
                target_q = questionnaire.questions[target_index]
                # 构建包含具体问题内容的返回消息
                base_message = decision.get("message", f"好的，我们回到第{target_index + 1}题")
                message = f"{base_message}，请重新回答：{target_q.text}"
                
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(message), session_id)
                
                return jsonify({
                    "session_id": session_id,
                    "question": message,
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": False,
                    "progress": f"{target_index + 1}/{len(questionnaire.questions)}",
                    "total_questions": len(questionnaire.questions),
                    "redo": True,
                    "redo_target_index": target_index,
                    "intent_type": decision.get("intent_type", "重新回答"),
                    "message": decision.get("message", "请重新回答这个问题。")
                })
            
            # 2. 处理跳过意图
            if decision.get("skip"):
                target_index = int(decision.get("target_index", current_index + 1))
                target_index = max(0, min(target_index, len(questionnaire.questions) - 1))
                
                # 更新管理器状态
                manager.current_question_index = target_index
                sess["current_index"] = target_index
                
                message = decision.get("message", "好的，我们跳过这道题。")
                
                # 检查是否完成
                if target_index >= len(questionnaire.questions):
                    # 问卷完成
                    report_text = "问卷已完成，感谢您的参与。"
                    video_url = "/static/video/human.mp4"
                    video_stream_url = "/static/video/human.mp4"
                    tts_url = generate_tts_audio(shorten_for_avatar(report_text), session_id)
                    
                    return jsonify({
                        "session_id": session_id,
                        "question": report_text,
                        "tts_url": tts_url,
                        "video_url": video_url,
                        "video_stream_url": video_stream_url,
                        "is_complete": True,
                        "progress": f"{len(questionnaire.questions)}/{len(questionnaire.questions)}",
                        "total_questions": len(questionnaire.questions),
                        "skip": True
                    })
                
                # 获取下一个问题
                next_q = questionnaire.questions[target_index]
                next_message = f"{message}\n\n{next_q.text}"
                
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(next_message), session_id)
                
                return jsonify({
                    "session_id": session_id,
                    "question": next_message,
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": False,
                    "progress": f"{target_index + 1}/{len(questionnaire.questions)}",
                    "total_questions": len(questionnaire.questions),
                    "skip": True
                })
            
            # 3. 处理答案有效性验证
            if not decision.get("valid", True):
                reason = decision.get("reason", "回答不够具体")
                suggestion = decision.get("suggestion", "请提供更详细的回答")
                hint = f"{reason}。{suggestion}。请重新回答：{current_q.text}"
                
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(hint), session_id)
                
                return jsonify({
                    "session_id": session_id,
                    "question": hint,
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": False,
                    "progress": f"{current_index + 1}/{len(questionnaire.questions)}",
                    "total_questions": len(questionnaire.questions),
                    "invalid_answer": True,
                    "invalid_reason": reason,
                    "suggestion": suggestion,
                    "retry": True
                })
        
        # 3. 使用简化版问卷管理器处理有效回答
        result = _run_async(manager.get_next_question(answer_text))
        
        # 更新会话状态
        sess["current_index"] = manager.current_question_index

        if result.get("status") == "invalid_answer":
            # 答案无效，重新询问
            hint = f"回答不够具体，请重新回答：{result['question']}"
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(hint), session_id)
            
            return jsonify({
                "session_id": session_id,
                "question": hint,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": False,
                "invalid_answer": True,
                "invalid_reason": result["error"],
                "retry": True
            })
        
        elif result.get("status") == "completed":
            # 问卷完成
            report_text = result["report"]
            
            # 保存报告到历史记录
            try:
                # 获取问卷管理器中的答案数据
                manager = sess.get("manager")
                if manager and hasattr(manager, 'answered_questions'):
                    # 构建答案映射
                    answers_map = {}
                    questionnaire = sess.get("questionnaire")
                    if questionnaire:
                        for response in manager.answered_questions:
                            try:
                                # 找到问题中文文本
                                q_text = next((q.text for q in questionnaire.questions if q.id == response.question_id), response.question_id)
                                answers_map[q_text] = str(response.answer)
                            except Exception:
                                answers_map[response.question_id] = str(response.answer)
                    
                    # 保存报告
                    _ = report_manager.save_report(report_text, answers_map, session_id)
                    _ = report_manager.save_report_json(report_text, answers_map, session_id)
                    _ = report_manager.save_report_pdf(report_text, answers_map, session_id)
                    logger.info(f"✅ 对话式MetaGPT报告保存成功: {session_id}")
                else:
                    # 如果没有管理器数据，使用空答案字典
                    _ = report_manager.save_report(report_text, {}, session_id)
                    _ = report_manager.save_report_json(report_text, {}, session_id)
                    _ = report_manager.save_report_pdf(report_text, {}, session_id)
                    logger.info(f"✅ 对话式MetaGPT报告保存成功（无答案数据）: {session_id}")
            except Exception as e:
                logger.warning(f"保存对话式MetaGPT报告失败: {e}")
            
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(report_text), session_id)
            
            return jsonify({
                "session_id": session_id,
                "question": report_text,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": True,
                "progress": f"{result['total_questions']}/{result['total_questions']}",
                "total_questions": result["total_questions"]
            })
        
        elif result.get("status") == "next_question":
            # 继续下一个问题
            question_text = result["question"]
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(question_text), session_id)
            
            return jsonify({
                "session_id": session_id,
                "question": question_text,
                "question_id": result["question_id"],
                "category": result["category"],
                "progress": result["progress"],
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": False
            })
        
        else:
            return jsonify({"error": result.get("error", "未知错误")}), 500

    except Exception as e:
        logger.error(f"MetaGPT conversational reply failed: {e}")
        return jsonify({"error": f"Failed to reply: {str(e)}"}), 500

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
            try:
                # 智谱Agent模式：保存报告（无结构化answers时使用空字典）
                _ = report_manager.save_report(question, {}, final_session_id)
                _ = report_manager.save_report_json(question, {}, final_session_id)
                _ = report_manager.save_report_pdf(question, {}, final_session_id)
            except Exception as _:
                logger.warning("保存智谱Agent报告失败（忽略）")
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

    # 注释掉数字人生成，改为使用预录制视频和TTS
    # try:
    #     wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
    #         text=shorten_for_avatar(question),
    #         prefix=str(final_session_id),
    #         ffmpeg_path=FFMPEG_PATH,
    #         static_root="static",
    #     )
    # except Exception as e:
    #     logger.error(f"数字人生成失败，回退为最小可用响应：{e}")
    #     tts_url = ""
    #     video_url = ""
    #     video_stream_url = ""

    # 使用预录制视频和TTS音频
    video_url = "/static/video/human.mp4"
    video_stream_url = "/static/video/human.mp4"
    tts_url = generate_tts_audio(shorten_for_avatar(question), final_session_id)

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

# ===== MetaGPT 问卷工作流 API =====
@app.route("/api/metagpt/init", methods=["POST", "GET"])
def metagpt_init():
    ok = _init_metagpt_if_needed()
    status = get_metagpt_status()
    return jsonify({
        "initialized": ok,
        "status": status,
        "message": "MetaGPT初始化完成" if ok else f"MetaGPT初始化失败: {status.get('error', '未知错误')}"
    })

@app.route("/api/metagpt/status", methods=["GET"])
def metagpt_status():
    """获取MetaGPT详细状态"""
    status = get_metagpt_status()
    
    # 添加更多诊断信息
    diagnostic_info = {
        "paths": {
            "current_file": str(pathlib.Path(__file__).resolve()),
            "project_root": str(pathlib.Path(__file__).resolve().parent.parent),
            "metagpt_dir": str(pathlib.Path(__file__).resolve().parent.parent / "metagpt_questionnaire"),
            "metagpt_exists": (pathlib.Path(__file__).resolve().parent.parent / "metagpt_questionnaire").exists()
        },
        "environment": {
            "deepseek_key_set": bool(os.getenv("DEEPSEEK_API_KEY")) and not os.getenv("DEEPSEEK_API_KEY", "").startswith("your-"),
            "python_path": sys.path[:3],  # 只显示前3个路径
        },
        "workflow_info": None
    }
    
    # 如果工作流已初始化，获取其状态
    if _metagpt_workflow:
        try:
            diagnostic_info["workflow_info"] = _metagpt_workflow.get_agent_status()
        except Exception as e:
            diagnostic_info["workflow_info"] = {"error": str(e)}
    
    return jsonify({
        "status": status,
        "diagnostic": diagnostic_info,
        "timestamp": time.time()
    })

def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # 在已有事件循环中，创建新任务并阻塞等待
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    else:
        return asyncio.run(coro)

@app.route("/api/metagpt/demo", methods=["POST"]) 
def metagpt_demo():
    if not _init_metagpt_if_needed():
        return jsonify({"error": "MetaGPT 初始化失败"}), 500
    try:
        from metagpt_questionnaire.main import MetaGPTQuestionnaireApp
        app_q = MetaGPTQuestionnaireApp()
        if not app_q.initialize():
            return jsonify({"error": "MetaGPT 工作流初始化失败"}), 500
        result = _run_async(app_q.run_demo_workflow())
        output_file = app_q.export_results(result)
        return jsonify({
            "status": result.get("status"),
            "workflow_id": result.get("workflow_id"),
            "stages": result.get("stages", []),
            "final_results": result.get("final_results", {}),
            "output_file": output_file
        })
    except Exception as e:
        logger.error(f"MetaGPT demo 执行失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/metagpt/custom", methods=["POST"]) 
def metagpt_custom():
    if not _init_metagpt_if_needed():
        return jsonify({"error": "MetaGPT 初始化失败"}), 500
    try:
        data = request.get_json(force=True)
        workflow_config = data or {}
        from metagpt_questionnaire.main import MetaGPTQuestionnaireApp
        app_q = MetaGPTQuestionnaireApp()
        if not app_q.initialize():
            return jsonify({"error": "MetaGPT 工作流初始化失败"}), 500
        result = _run_async(app_q.run_custom_workflow(workflow_config))
        output_file = app_q.export_results(result)
        return jsonify({
            "status": result.get("status"),
            "workflow_id": result.get("workflow_id"),
            "stages": result.get("stages", []),
            "final_results": result.get("final_results", {}),
            "output_file": output_file
        })
    except Exception as e:
        logger.error(f"MetaGPT custom 执行失败: {e}")
        return jsonify({"error": str(e)}), 500

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

        # 开始本地问卷前清理上次音频（保留占位/预热文件）
        clear_tts_dir(keep_names=["warmup.wav", "beep.wav"])  # 若无则忽略

        if not hasattr(app, 'questionnaire_sessions'):
            app.questionnaire_sessions = {}

        app.questionnaire_sessions[session_id] = {
            "current_question_index": 0,
            "answers": {},
            "start_time": time.time()
        }

        from local_questionnaire import questions_structured
        first_question_obj = questions_structured[0]
        first_question = first_question_obj.get('prompt', first_question_obj['text'])
        question_info = get_question_info(0)

        # 注释掉数字人生成，改为使用预录制视频和TTS
        # try:
        #     wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
        #         text=shorten_for_avatar(first_question),
        #         prefix=str(session_id),
        #         ffmpeg_path=FFMPEG_PATH,
        #         static_root="static",
        #     )
        # except Exception as e:
        #     logger.error(f"数字人生成失败（local start）：{e}")
        #     tts_url = ""
        #     video_url = ""
        #     video_stream_url = ""

        # 使用预录制视频和TTS音频
        video_url = "/static/video/human.mp4"
        video_stream_url = "/static/video/human.mp4"
        tts_url = generate_tts_audio(shorten_for_avatar(first_question), session_id)

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

from local_questionnaire import questions_structured

def find_next_question_index(current_index: int, answers: dict) -> int:
    """
    Find the index of the next valid question, applying auto-fill logic.
    Returns -1 if the questionnaire is complete.
    """
    next_index = current_index + 1
    while next_index < len(questions_structured):
        question_data = questions_structured[next_index]
        dependency = question_data.get("depends_on")

        if not dependency:
            # No dependency, this is the next question
            return next_index

        # Check if the dependency is met
        dependent_question_id = dependency.get("id")
        required_value = dependency.get("value")
        possible_values = dependency.get("values", [required_value])  # 支持多个可能的值
        auto_fill_value = question_data.get("auto_fill_value", "0")  # 获取自动填充值

        # Find the original text of the dependent question to look up the answer
        dependent_question_text = None
        for q in questions_structured:
            if q['id'] == dependent_question_id:
                dependent_question_text = q['text']
                break
        
        actual_answer = answers.get(dependent_question_text)
        
        # 检查是否匹配任何一个可能的值
        dependency_met = False
        if actual_answer:
            answer_text = str(actual_answer).lower()
            for value in possible_values:
                value_lower = value.lower()
                # 更精确的匹配：检查是否包含完整的值，而不是部分匹配
                if (value_lower in answer_text and 
                    not any(neg_word in answer_text for neg_word in ['不', '没', '无', '否', '没有', '不会', '不会'])):
                    dependency_met = True
                    break
        
        if dependency_met:
            # Dependency met, this is the next question
            return next_index
        else:
            # Dependency not met, auto-fill the answer and continue
            question_text = question_data.get("text")
            if question_text and question_text not in answers:
                answers[question_text] = auto_fill_value
                print(f"🔄 自动填充: {question_text} = {auto_fill_value}")
            next_index += 1
    
    # No more questions found, questionnaire is complete
    return -1

@app.route("/api/local_questionnaire/reply", methods=["POST"])
def local_questionnaire_reply():
    try:
        data = request.get_json(force=True)
        session_id = data["session_id"]
        answer_text = data["answer"]

        if session_id not in app.questionnaire_sessions:
            return jsonify({"error": "会话不存在"}), 400

        from local_questionnaire import questions_structured
        session = app.questionnaire_sessions[session_id]
        current_index = session["current_question_index"]
        
        # 使用新的结构化数据
        current_question_obj = questions_structured[current_index]
        # 使用原始文本作为key，以兼容报告生成函数
        session["answers"][current_question_obj['text']] = answer_text

        next_index = find_next_question_index(current_index, session["answers"])

        if next_index == -1:
            report = generate_assessment_report(session["answers"])
            session["completed"] = True
            session["report"] = report

            # 保存报告到 report/ 目录
            try:
                _ = report_manager.save_report(report, session["answers"], session_id)
                _ = report_manager.save_report_json(report, session["answers"], session_id)
                _ = report_manager.save_report_pdf(report, session["answers"], session_id)
            except Exception as _:
                logger.warning("保存本地问卷报告失败（忽略）")

            # 报告很长 -> 先做“摘要快视频”（6~8秒）
            first_seg = shorten_for_avatar(report)
            # 注释掉数字人生成，改为使用预录制视频和TTS
            # try:
            #     wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
            #         text=first_seg,
            #         prefix=f"{session_id}_report",
            #         ffmpeg_path=FFMPEG_PATH,
            #         static_root="static",
            #     )
            # except Exception as e:
            #     logger.error(f"数字人生成失败（local report）：{e}")
            #     tts_url = ""
            #     video_url = ""
            #     video_stream_url = ""

            # 使用预录制视频和TTS音频
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(first_seg, session_id)

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
            next_question_obj = questions_structured[next_index]
            next_question = next_question_obj.get('prompt', next_question_obj['text'])
            question_info = get_question_info(next_index)
            session["current_question_index"] = next_index

            # 注释掉数字人生成，改为使用预录制视频和TTS
            # try:
            #     wav_path, mp4_path, tts_url, video_url, video_stream_url = generate_digital_human_assets(
            #         text=shorten_for_avatar(next_question),
            #         prefix=str(session_id),
            #         ffmpeg_path=FFMPEG_PATH,
            #         static_root="static",
            #     )
            # except Exception as e:
            #     logger.error(f"数字人生成失败（local reply）：{e}")
            #     tts_url = ""
            #     video_url = ""
            #     video_stream_url = ""

            # 使用预录制视频和TTS音频
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(next_question), session_id)

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

        from local_questionnaire import questions_structured
        current_question_text = None
        if current_index < len(questions_structured):
            q_obj = questions_structured[current_index]
            current_question_text = q_obj.get('prompt', q_obj['text'])

        return jsonify({
            "session_id": session_id,
            "current_question_index": current_index,
            "current_question": current_question_text,
            "progress": f"{current_index + 1}/{len(questions_structured)}",
            "total_questions": len(questions_structured),
            "completed": session.get("completed", False),
            "answers_count": len(session["answers"])
        })
    except Exception as e:
        logger.error(f"获取本地问卷状态失败: {e}")
        return jsonify({"error": f"获取状态失败: {str(e)}"}), 500

# 这些函数已移至 local_questionnaire.py 模块

@app.route("/api/assessment_report/<session_id>", methods=["GET"])
def get_assessment_report(session_id):
    try:
        return jsonify({"session_id": session_id, "has_report": True, "message": "评估报告已生成，请查看对话历史"})
    except Exception as e:
        logger.error(f"获取评估报告失败: {e}")
        return jsonify({"error": f"获取评估报告失败: {str(e)}"}), 500

# ----------------- 报告查看/下载接口 -----------------
@app.route("/api/reports", methods=["GET"])
def list_reports():
    try:
        reports = report_manager.get_reports_list()
        stats = report_manager.get_reports_stats()
        return jsonify({"reports": reports, "stats": stats})
    except Exception as e:
        logger.error(f"获取报告列表失败: {e}")
        return jsonify({"error": f"获取报告列表失败: {str(e)}"}), 500

@app.route("/api/reports/content/<path:filename>", methods=["GET"])
def get_report_content_api(filename):
    try:
        content = report_manager.get_report_content(filename)
        if content is None:
            return jsonify({"error": "报告不存在"}), 404
        return jsonify({"filename": filename, "content": content})
    except Exception as e:
        logger.error(f"读取报告失败: {e}")
        return jsonify({"error": f"读取报告失败: {str(e)}"}), 500

@app.route("/api/reports/download/<path:filename>", methods=["GET"])
def download_report(filename):
    try:
        reports_dir = str(report_manager.reports_dir)
        return send_from_directory(reports_dir, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"下载报告失败: {e}")
        return jsonify({"error": f"下载报告失败: {str(e)}"}), 500

@app.route("/api/reports/export_pdf/<path:filename>", methods=["GET"])
def export_report_pdf(filename):
    """
    将TXT报告导出为PDF格式
    """
    try:
        # 检查原始文件是否存在
        original_path = report_manager.reports_dir / filename
        if not original_path.exists():
            return jsonify({"error": "报告文件不存在"}), 404
        
        # 检查是否是TXT文件
        if not filename.endswith('.txt'):
            return jsonify({"error": "只能导出TXT格式的报告为PDF"}), 400
        
        # 读取原始报告内容
        with open(original_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 从文件名中提取信息（假设格式为：姓名_手机号_时间戳.txt）
        name_part = filename.replace('.txt', '')
        parts = name_part.split('_')
        
        # 构建答案字典（从报告内容中提取）
        answers = {}
        lines = content.split('\n')
        in_answers_section = False
        
        for line in lines:
            line = line.strip()
            if line == "【用户信息】":
                in_answers_section = True
                continue
            elif line == "【会话信息】":
                in_answers_section = False
                break
            elif in_answers_section and ':' in line:
                key, value = line.split(':', 1)
                answers[key.strip()] = value.strip()
        
        # 生成PDF
        pdf_path = report_manager.save_report_pdf(content, answers, parts[-1] if len(parts) > 2 else "unknown")
        
        if pdf_path:
            return send_from_directory(report_manager.reports_dir, 
                                    Path(pdf_path).name, 
                                    as_attachment=True,
                                    mimetype='application/pdf')
        else:
            return jsonify({"error": "PDF生成失败"}), 500
            
    except Exception as e:
        logger.error(f"导出PDF失败: {e}")
        return jsonify({"error": f"导出PDF失败: {str(e)}"}), 500

@app.route("/api/reports/create_pdf", methods=["POST"])
def create_report_pdf():
    """
    直接创建PDF报告
    """
    try:
        data = request.get_json(force=True)
        report_content = data.get("report_content", "")
        answers = data.get("answers", {})
        session_id = data.get("session_id", str(int(time.time() * 1000)))
        
        if not report_content:
            return jsonify({"error": "报告内容不能为空"}), 400
        
        # 生成PDF
        pdf_path = report_manager.save_report_pdf(report_content, answers, session_id)
        
        if pdf_path:
            return jsonify({
                "success": True,
                "pdf_path": pdf_path,
                "filename": Path(pdf_path).name,
                "download_url": f"/api/reports/download/{Path(pdf_path).name}"
            })
        else:
            return jsonify({"error": "PDF生成失败"}), 500
            
    except Exception as e:
        logger.error(f"创建PDF报告失败: {e}")
        return jsonify({"error": f"创建PDF报告失败: {str(e)}"}), 500

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

@app.route("/api/cleanup", methods=["POST", "GET"])
def cleanup():
    """
    清理会话和临时文件
    支持POST和GET请求以便于调试
    """
    try:
        logger.info(f"收到cleanup请求，方法: {request.method}")
        
        # 处理不同的请求方法
        if request.method == "POST":
            data = request.get_json(force=True) if request.is_json else {}
            session_id = data.get("session_id", "")
        else:  # GET请求
            session_id = request.args.get("session_id", "")
        
        logger.info(f"开始清理会话: {session_id}")
        
        # 清理本地问卷会话
        sessions_cleaned = 0
        if hasattr(app, 'questionnaire_sessions'):
            if session_id and session_id in app.questionnaire_sessions:
                del app.questionnaire_sessions[session_id]
                sessions_cleaned += 1
                logger.info(f"已清理本地问卷会话: {session_id}")
            elif not session_id:
                # 如果没有指定session_id，清理所有会话
                sessions_cleaned = len(app.questionnaire_sessions)
                app.questionnaire_sessions.clear()
                logger.info(f"已清理所有本地问卷会话: {sessions_cleaned} 个")
        
        # 清理TTS临时文件（可选，保留最近的文件避免过度清理）
        deleted_count = 0
        try:
            tts_dir = pathlib.Path("static/tts")
            if tts_dir.exists():
                # 获取所有TTS文件，按修改时间排序
                tts_files = list(tts_dir.glob("*.mp3")) + list(tts_dir.glob("*.wav"))
                tts_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # 保留最新的10个文件，删除其余的
                files_to_delete = tts_files[10:]
                for file_path in files_to_delete:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除TTS文件失败: {file_path}, 错误: {e}")
                
                if deleted_count > 0:
                    logger.info(f"已清理 {deleted_count} 个旧的TTS文件")
        except Exception as e:
            logger.warning(f"清理TTS文件时出错: {e}")
        
        result = {
            "success": True,
            "message": "清理完成",
            "session_id": session_id,
            "sessions_cleaned": sessions_cleaned,
            "files_cleaned": deleted_count,
            "method": request.method
        }
        
        logger.info(f"清理操作完成: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"清理操作失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "method": request.method
        }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"未处理的异常: {e}")
    return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "接口不存在"}), 404

def cleanup_all_resources():
    """清理所有资源"""
    try:
        # 清理全局线程池
        cleanup_global_thread_pool()
        
        # 清理ASR线程池
        try:
            from xfyun_asr import cleanup_thread_pool
            cleanup_thread_pool()
        except ImportError:
            pass
        
        # 清理TTS线程池
        try:
            from xfyun_tts import cleanup_tts_thread_pool
            cleanup_tts_thread_pool()
        except ImportError:
            pass
        
        # 清理数字人线程池
        try:
            from digital_human import cleanup_digital_human_thread_pool
            cleanup_digital_human_thread_pool()
        except ImportError:
            pass
        
        logger.info("所有资源清理完成")
    except Exception as e:
        logger.error(f"清理资源时出错: {e}")

if __name__ == "__main__":
    print("启动Flask服务器...")
    print("访问地址: http://localhost:8080")
    
    try:
        # 关闭调试与自动重载，避免 PowerShell 下 watchdog 导致的重启与中断
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    finally:
        # 确保在应用关闭时清理所有资源
        cleanup_all_resources()

@app.route("/api/metagpt/agent_stats", methods=["GET"])
def metagpt_agent_stats():
    """获取智能体使用统计"""
    try:
        from metagpt_questionnaire.persistent_agent_manager import get_agent_session_stats
        stats = get_agent_session_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========= 智能动态问卷 API =========
@app.route("/api/intelligent_questionnaire/start", methods=["POST"])
def intelligent_questionnaire_start():
    """
    启动智能动态问卷
    - 基础问题预生成
    - 支持动态问题生成
    - 智能跳转和依赖关系
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", str(int(time.time() * 1000)))

        # 清理上次音频
        clear_tts_dir(keep_names=["warmup.wav", "beep.wav"])

        # 初始化智能问卷管理器
        if not hasattr(app, 'intelligent_sessions'):
            app.intelligent_sessions = {}
        
        manager = IntelligentQuestionnaireManager()
        app.intelligent_sessions[session_id] = {
            "manager": manager,
            "start_time": time.time()
        }

        # 获取第一个问题
        result = manager.get_next_question()
        
        if result["status"] != "next_question":
            return jsonify({"error": "无法获取首个问题"}), 500
        
        question_text = result["question"]
        
        # 生成TTS和视频
        video_url = "/static/video/human.mp4"
        video_stream_url = "/static/video/human.mp4"
        tts_url = generate_tts_audio(shorten_for_avatar(question_text), session_id)

        return jsonify({
            "session_id": session_id,
            "question": question_text,
            "question_id": result["question_id"],
            "category": result["category"],
            "question_type": result["question_type"],
            "progress": result["progress"],
            "total_questions": result["total_questions"],
            "tts_url": tts_url,
            "video_url": video_url,
            "video_stream_url": video_stream_url,
            "is_complete": False
        })
    except Exception as e:
        logger.error(f"智能问卷启动失败: {e}")
        return jsonify({"error": f"启动失败: {str(e)}"}), 500

@app.route("/api/intelligent_questionnaire/reply", methods=["POST"])
def intelligent_questionnaire_reply():
    """
    处理智能动态问卷回复
    - 根据回答动态生成相关问题
    - 智能跳转和依赖处理
    - 自动完成问卷并生成报告
    """
    try:
        data = request.get_json(force=True)
        session_id = data["session_id"]
        answer_text = data.get("answer", "").strip()

        if not hasattr(app, 'intelligent_sessions') or session_id not in app.intelligent_sessions:
            return jsonify({"error": "会话不存在"}), 400

        sess = app.intelligent_sessions[session_id]
        manager = sess["manager"]
        
        if not manager:
            return jsonify({"error": "问卷管理器未找到"}), 400
        
        # 处理用户回答并获取下一个问题
        result = manager.get_next_question(answer_text)
        
        # 更新会话状态
        sess["current_index"] = manager.current_question_index

        if result.get("status") == "completed":
            # 问卷完成
            report_text = result["report"]
            
            # 保存报告
            try:
                # 构建答案映射
                answers_map = {}
                for response in manager.user_responses:
                    question_text = manager._get_question_text(response.question_id)
                    answers_map[question_text] = str(response.answer)
                
                # 保存多种格式的报告
                _ = report_manager.save_report(report_text, answers_map, session_id)
                _ = report_manager.save_report_json(report_text, answers_map, session_id)
                _ = report_manager.save_report_pdf(report_text, answers_map, session_id)
                logger.info(f"✅ 智能问卷报告保存成功: {session_id}")
            except Exception as e:
                logger.warning(f"保存智能问卷报告失败: {e}")
            
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(report_text), session_id)
            
            return jsonify({
                "session_id": session_id,
                "question": report_text,
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": True,
                "progress": f"{result['total_questions']}/{result['total_questions']}",
                "total_questions": result["total_questions"],
                "basic_questions": result["basic_questions"],
                "dynamic_questions": result["dynamic_questions"],
                "answered_questions": result["answered_questions"]
            })
        
        elif result.get("status") == "next_question":
            # 继续下一个问题
            question_text = result["question"]
            video_url = "/static/video/human.mp4"
            video_stream_url = "/static/video/human.mp4"
            tts_url = generate_tts_audio(shorten_for_avatar(question_text), session_id)
            
            return jsonify({
                "session_id": session_id,
                "question": question_text,
                "question_id": result["question_id"],
                "category": result["category"],
                "question_type": result["question_type"],
                "progress": result["progress"],
                "total_questions": result["total_questions"],
                "tts_url": tts_url,
                "video_url": video_url,
                "video_stream_url": video_stream_url,
                "is_complete": False
            })
        
        else:
            return jsonify({"error": result.get("error", "未知错误")}), 500

    except Exception as e:
        logger.error(f"智能问卷回复失败: {e}")
        return jsonify({"error": f"提交失败: {str(e)}"}), 500

@app.route("/api/intelligent_questionnaire/stats/<session_id>", methods=["GET"])
def get_intelligent_questionnaire_stats(session_id):
    """获取智能问卷统计信息"""
    try:
        if not hasattr(app, 'intelligent_sessions') or session_id not in app.intelligent_sessions:
            return jsonify({"error": "会话不存在"}), 404

        sess = app.intelligent_sessions[session_id]
        manager = sess["manager"]
        
        if not manager:
            return jsonify({"error": "问卷管理器未找到"}), 400
        
        stats = manager.get_questionnaire_stats()
        return jsonify({
            "session_id": session_id,
            "stats": stats,
            "start_time": sess["start_time"]
        })
    except Exception as e:
        logger.error(f"获取智能问卷统计失败: {e}")
        return jsonify({"error": f"获取统计失败: {str(e)}"}), 500

