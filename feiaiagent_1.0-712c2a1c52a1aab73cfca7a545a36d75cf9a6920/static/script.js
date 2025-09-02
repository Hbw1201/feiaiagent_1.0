let sessionId = null;
let mediaRecorder = null;
let chunks = [];
let audioContext = null;
let analyser = null;
let microphone = null;
let dataArray = null;
let animationId = null;
let isLocalQuestionnaire = false;
let isAgentMode = false;
let currentQuestionInfo = null;

const statusEl = document.getElementById("status");
const qEl = document.getElementById("questionText");
const aEl = document.getElementById("answerText");
const audioEl = document.getElementById("ttsAudio");
const debugEl = document.getElementById("debugText");

// [ADD] 尝试获取或动态创建数字人视频元素
let videoEl = document.getElementById("digitalHumanVideo"); // [ADD]
if (!videoEl) { // [ADD]
  videoEl = document.createElement("video"); // [ADD]
  videoEl.id = "digitalHumanVideo"; // [ADD]
  videoEl.controls = true; // [ADD]
  videoEl.playsInline = true; // [ADD]
  videoEl.style.display = "none"; // [ADD]
  videoEl.style.maxWidth = "100%"; // [ADD]
  // 将视频元素插到音频元素后面，保持布局紧邻（可按需调整）
  if (audioEl && audioEl.parentNode) { // [ADD]
    audioEl.parentNode.insertBefore(videoEl, audioEl.nextSibling); // [ADD]
  } else { // [ADD]
    document.body.appendChild(videoEl); // [ADD]
  } // [ADD]
}

const assessmentReportEl = document.getElementById("assessmentReport");
const reportContentEl = document.getElementById("reportContent");
const reportAudioEl = document.getElementById("reportAudio");

const recordingIndicator = document.getElementById("recordingIndicator");
const volumeVisualizer = document.getElementById("volumeVisualizer");
const historyList = document.getElementById("historyList");
const historyContainer = document.getElementById("historyContainer");
const btnExpandHistory = document.getElementById("btnExpandHistory");
const btnCollapseHistory = document.getElementById("btnCollapseHistory");
const btnRestart = document.getElementById("btnRestart");
const ttsIndicator = document.getElementById("ttsIndicator");
const ttsStatus = document.getElementById("ttsStatus");

// 报告DOM
const btnRefreshReports = document.getElementById('btnRefreshReports');
const reportsListEl = document.getElementById('reportsList');
const reportsStatsEl = document.getElementById('reportsStats');

let conversationHistory = [];

function log(message) {
  const timestamp = new Date().toLocaleTimeString();
  debugEl.textContent = `[${timestamp}] ${message}`;
  console.log(message);
}

function showAssessmentReport() {
  assessmentReportEl.style.display = "block";
  log("显示评估报告区域");
}

function hideAssessmentReport() {
  assessmentReportEl.style.display = "none";
  log("隐藏评估报告区域");
}

// 显示TTS播放指示器
function showTTSIndicator(status) {
  ttsStatus.textContent = status;
  ttsIndicator.style.display = "flex";
  log(`显示TTS指示器: ${status}`);
}

// 隐藏TTS播放指示器
function hideTTSIndicator() {
  ttsIndicator.style.display = "none";
  log("隐藏TTS指示器");
}

function addToHistory(type, content) {
  const timestamp = new Date().toLocaleTimeString();
  const historyItem = {
    type: type,
    content: content,
    timestamp: timestamp
  };

  conversationHistory.push(historyItem);
  updateHistoryDisplay();
}

function updateHistoryDisplay() {
  historyList.innerHTML = '';

  conversationHistory.forEach(item => {
    const historyItem = document.createElement('div');
    historyItem.className = `history-item ${item.type}`;

    if (item.type === 'summary') {
      historyItem.style.backgroundColor = '#d4edda';
      historyItem.style.borderColor = '#c3e6cb';
      historyItem.style.color = '#155724';
    } else if (item.type === 'warning') {
      historyItem.style.backgroundColor = '#fff3cd';
      historyItem.style.borderColor = '#ffeaa7';
      historyItem.style.color = '#856404';
    }

    historyItem.innerHTML = `
      <div class="timestamp">${item.timestamp}</div>
      <div class="content">${item.content}</div>
    `;

    historyList.appendChild(historyItem);
  });

  if (historyList.scrollHeight > historyList.clientHeight) {
    historyList.scrollTop = historyList.scrollHeight;
  }
}



// [ADD] 统一设置媒体资源（视频和TTS音频同时播放），并控制显示/隐藏
function setTTSAndVideo(ttsUrl, videoUrl, playLabel) {
  // 重置显示
  if (videoEl) {
    videoEl.pause();
    videoEl.currentTime = 0;
    videoEl.style.display = "none";
    videoEl.removeAttribute("src");
  }
  if (audioEl) {
    audioEl.pause();
    audioEl.currentTime = 0;
    audioEl.removeAttribute("src");
  }

  // 设置视频（静音播放，用于视觉效果）
  if (videoUrl) {
    videoEl.src = videoUrl;
    videoEl.muted = true; // 视频静音，只播放TTS音频
    videoEl.style.display = "block";
    log(`设置视频: ${videoUrl}`);
  }

  // 设置TTS音频（有声音）
  if (ttsUrl) {
    audioEl.src = ttsUrl;
    // 设置音频属性以确保可以播放
    audioEl.muted = false;
    audioEl.volume = 1.0;
    audioEl.preload = "auto";
    log(`设置TTS音频: ${ttsUrl}`);
    
    // 添加音频加载事件监听器
    audioEl.onloadstart = () => log('TTS音频开始加载');
    audioEl.oncanplay = () => log('TTS音频可以播放');
    audioEl.oncanplaythrough = () => log('TTS音频可以流畅播放');
    audioEl.onerror = (e) => log(`TTS音频加载错误: ${e.message || '未知错误'}`);
    audioEl.onabort = () => log('TTS音频加载被中断');
    audioEl.onstalled = () => log('TTS音频加载停滞');
    audioEl.onwaiting = () => log('TTS音频等待数据');
    audioEl.onplay = () => log('TTS音频开始播放');
    audioEl.onpause = () => log('TTS音频暂停');
    audioEl.onended = () => log('TTS音频播放结束');
  }

  // 显示播放指示器
  if (videoUrl || ttsUrl) {
    showTTSIndicator(playLabel || "正在播放数字人视频和语音...");
  } else {
    hideTTSIndicator();
  }

  // 返回音频元素作为主要控制元素（因为TTS音频决定播放时长）
  return ttsUrl ? audioEl : (videoUrl ? videoEl : null);
}

// [ADD] 播放并在结束后自动开始录音（视频和TTS音频同步播放）
async function playWithAutoRecord(mediaEl, afterLabel = "语音播放完成，自动开始录音...") {
  if (!mediaEl) return;
  
  // 添加调试信息
  log(`开始播放媒体: ${mediaEl.tagName}, src: ${mediaEl.src}`);
  
  try {
    // 同时播放视频和音频
    const playPromises = [];
    
    // 播放主要媒体元素（通常是音频）
    if (mediaEl) {
      const playPromise = mediaEl.play();
      if (playPromise !== undefined) {
        playPromises.push(playPromise);
      }
    }
    
    // 同时播放视频（如果存在且不是主要元素）
    if (videoEl && videoEl.src && videoEl !== mediaEl) {
      const videoPlayPromise = videoEl.play();
      if (videoPlayPromise !== undefined) {
        playPromises.push(videoPlayPromise);
      }
    }
    
    // 等待所有播放开始
    if (playPromises.length > 0) {
      await Promise.all(playPromises);
      log('所有媒体播放开始');
    }
    
    // 添加音频事件监听器
    if (mediaEl && mediaEl.tagName === 'AUDIO') {
      mediaEl.onloadstart = () => log('音频开始加载');
      mediaEl.oncanplay = () => log('音频可以播放');
      mediaEl.oncanplaythrough = () => log('音频可以流畅播放');
      mediaEl.onerror = (e) => log(`音频加载错误: ${e.message || '未知错误'}`);
      mediaEl.onabort = () => log('音频加载被中断');
      mediaEl.onstalled = () => log('音频加载停滞');
      mediaEl.onwaiting = () => log('音频等待数据');
      mediaEl.onplay = () => log('音频开始播放');
      mediaEl.onpause = () => log('音频暂停');
      mediaEl.onended = () => log('音频播放结束');
    }
    
    // 当TTS音频结束时，停止视频并开始录音
    if (mediaEl && mediaEl.tagName === 'AUDIO') {
      mediaEl.onended = () => {
        // 停止视频
        if (videoEl && videoEl.src) {
          videoEl.pause();
          videoEl.currentTime = 0;
          log('视频已停止');
        }
        
        hideTTSIndicator();
        statusEl.textContent = `状态：${afterLabel}`;
        log(`TTS音频播放完成，视频已停止，准备开始录音`);

        setTimeout(() => {
          if (isAgentMode || isLocalQuestionnaire) {
            startRecording();
          }
        }, 500);
      };
    } else if (mediaEl && mediaEl.tagName === 'VIDEO') {
      // 如果是视频，当视频结束时开始录音
      mediaEl.onended = () => {
        hideTTSIndicator();
        statusEl.textContent = `状态：${afterLabel}`;
        log(`视频播放完成，准备开始录音`);

        setTimeout(() => {
          if (isAgentMode || isLocalQuestionnaire) {
            startRecording();
          }
        }, 500);
      };
    }
    
  } catch (e) {
    hideTTSIndicator();
    log(`媒体播放失败: ${e.message}`);
    statusEl.textContent = "状态：媒体播放失败，但内容已显示";
    
    // 如果是自动播放策略错误，提示用户手动播放
    if (e.name === 'NotAllowedError') {
      log('浏览器阻止了自动播放，请手动点击播放按钮');
      statusEl.textContent = "状态：请手动点击播放按钮开始播放";
    }
  }
}



function restartConversation() {
  log("🔄 重新开始对话");

  // 重置状态
  sessionId = null;
  isLocalQuestionnaire = false;
  isAgentMode = false;
  currentQuestionInfo = null;
  statusEl.textContent = "状态：未开始";
  statusEl.style.color = "#1976d2";
  statusEl.style.backgroundColor = "#e3f2fd";

  // 重置问题显示
  qEl.textContent = "（等待开始）";
  qEl.style.color = "#333";
  qEl.style.fontWeight = "normal";

  // 重置回答显示
  aEl.textContent = "（等待录音）";

  // 隐藏问题信息和进度
  document.getElementById("questionInfo").style.display = "none";
  document.getElementById("progressInfo").style.display = "none";

      // 重置按钮状态
    document.getElementById("btnStart").disabled = false;
    document.getElementById("btnStartLocal").disabled = false;
    // 录音按钮现在是自动的，不需要手动设置

  // 隐藏重新开始按钮
  btnRestart.style.display = "none";

  // 隐藏评估报告
  hideAssessmentReport();

  // 清空音频
  audioEl.src = "";
  // [ADD] 清空视频
  if (videoEl) {
    videoEl.pause();
    videoEl.removeAttribute("src");
    videoEl.style.display = "none";
  }

  // 清空对话历史
  conversationHistory = [];
  updateHistoryDisplay();
  hideAssessmentReport();

  // 重置本地问卷状态
  isLocalQuestionnaire = false;
  isAgentMode = false;
  currentQuestionInfo = null;

  // 隐藏问题信息和进度
  document.getElementById("questionInfo").style.display = "none";
  document.getElementById("progressInfo").style.display = "none";

  log("对话已重置，可以重新开始");
}



function toggleHistory() {
  const isCollapsed = historyContainer.classList.contains('collapsed');

  if (isCollapsed) {
    historyContainer.classList.remove('collapsed');
    btnExpandHistory.style.display = 'none';
    btnCollapseHistory.style.display = 'inline-block';
  } else {
    historyContainer.classList.add('collapsed');
    btnExpandHistory.style.display = 'inline-block';
    btnCollapseHistory.style.display = 'none';
  }
}

btnExpandHistory.addEventListener("click", toggleHistory);
btnCollapseHistory.addEventListener("click", toggleHistory);
  btnRestart.addEventListener("click", restartConversation);

function updateVolumeVisualizer(volume) {
  const bars = volumeVisualizer.querySelectorAll('.volume-bar');
  const normalizedVolume = Math.min(volume / 100, 1);

  bars.forEach((bar, index) => {
    const maxHeight = 30;
    const minHeight = 4;
    const height = minHeight + (maxHeight - minHeight) * normalizedVolume * (index + 1) / bars.length;
    bar.style.height = `${height}px`;
  });
}

function startVolumeVisualization(stream) {
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    microphone = audioContext.createMediaStreamSource(stream);

    analyser.fftSize = 256;
    const bufferLength = analyser.frequencyBinCount;
    dataArray = new Uint8Array(bufferLength);

    microphone.connect(analyser);

    function animate() {
      animationId = requestAnimationFrame(animate);
      analyser.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      const average = sum / bufferLength;

      updateVolumeVisualizer(average);
    }

    animate();
  } catch (error) {
    log(`音量可视化启动失败: ${error.message}`);
  }
}

function stopVolumeVisualization() {
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }

  // 停止静音检测
  if (window.silenceTimer) {
    cancelAnimationFrame(window.silenceTimer);
    window.silenceTimer = null;
    log("静音检测已停止");
  }

  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }

  const bars = volumeVisualizer.querySelectorAll('.volume-bar');
  bars.forEach(bar => {
    bar.style.height = '4px';
  });
}

async function fetchSystemStatus() {
    try {
        const response = await fetch('/api/questionnaire_status');
        const data = await response.json();
        log(`当前使用智谱AI系统`);
    } catch (error) {
        log(`获取系统状态失败: ${error.message}`);
        log("默认使用智谱AI系统");
    }
}

document.addEventListener("DOMContentLoaded", function() {
  fetchSystemStatus();
  
  // 解锁音频播放
  unlockAudio();
});

// 解锁音频播放功能
function unlockAudio() {
  // 创建一个静音的音频元素来解锁播放权限
  const unlockAudio = document.createElement('audio');
  unlockAudio.muted = true;
  unlockAudio.volume = 0;
  
  // 添加一个点击事件监听器到整个页面
  document.addEventListener('click', function unlockAudioOnClick() {
    unlockAudio.play().then(() => {
      log('音频播放权限已解锁');
      document.removeEventListener('click', unlockAudioOnClick);
    }).catch(e => {
      log(`音频解锁失败: ${e.message}`);
    });
  }, { once: true });
  
  log('音频解锁功能已准备就绪，点击页面任意位置即可解锁音频播放');
}

async function startConversation() {
  try {
    log("开始启动智谱AI对话...");
    statusEl.textContent = "状态：正在启动智谱AI对话...";

    hideAssessmentReport();
    isLocalQuestionnaire = false;
    isAgentMode = true;

    // 更新按钮状态
    updateButtonStates();

    sessionId = Date.now().toString();

    const res = await fetch("/api/agent/start", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: sessionId})});

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();

    if (data.error) {
      throw new Error(data.error);
    }

    sessionId = data.session_id;
    const question = data.question || "(无)";
    qEl.textContent = question;

    // [MOD] 优先使用视频，其次音频
    const mediaEl = setTTSAndVideo(data.tts_url, data.video_url, "正在播放问题..."); // [MOD]

    addToHistory('question', question);

    log(`智谱AI对话启动成功，会话ID: ${sessionId}`);
    log(`获取到问题: ${question}`);

    // [MOD] 统一播放并在结束后自动录音
    if (mediaEl) {
      statusEl.textContent = "状态：正在播放问题...";
      // 尝试播放，如果失败则提示用户手动播放
      try {
        await playWithAutoRecord(mediaEl); // [MOD]
      } catch (e) {
        log(`自动播放失败: ${e.message}`);
        statusEl.textContent = "状态：请手动点击播放按钮开始播放";
      }
    } else {
      statusEl.textContent = "状态：已开始，等待你的回答";
    }
  } catch (error) {
    log(`启动智谱AI对话失败: ${error.message}`);
    statusEl.textContent = "状态：启动失败，请重试";
  }
}

async function startLocalQuestionnaire() {
  try {
    log("开始启动本地问卷...");
    statusEl.textContent = "状态：正在启动本地问卷...";

    hideAssessmentReport();
    isLocalQuestionnaire = true;
    isAgentMode = false;

    // 更新按钮状态
    updateButtonStates();

    sessionId = Date.now().toString();

    const res = await fetch("/api/local_questionnaire/start", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: sessionId})});

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${res.status}: ${res.statusText}`); // [MOD] 修复 data 未定义
    }

    const data = await res.json();

    if (data.error) {
      throw new Error(data.error);
    }

    sessionId = data.session_id;
    const question = data.question || "(无)";
    qEl.textContent = question;

    // [MOD] 优先使用视频，其次音频
    const mediaEl = setTTSAndVideo(data.tts_url, data.video_url, "正在播放问题..."); // [MOD]

    // 显示问题信息和进度
    if (data.question_info) {
      currentQuestionInfo = data.question_info;
      document.getElementById("questionInfo").style.display = "block";
      document.getElementById("questionInfoText").textContent = `${currentQuestionInfo.category} - ${currentQuestionInfo.format}`;
    }

    if (data.progress) {
      document.getElementById("progressInfo").style.display = "block";
      document.getElementById("progressText").textContent = data.progress;
    }

    addToHistory('question', `[本地问卷] ${question}`);

    log(`本地问卷启动成功，会话ID: ${sessionId}`);
    log(`获取到问题: ${question}`);
    log(`问题分类: ${currentQuestionInfo?.category}, 格式要求: ${currentQuestionInfo?.format}`);

    // [MOD] 统一播放并在结束后自动录音
    if (mediaEl) {
      statusEl.textContent = "状态：正在播放问题...";
      // 尝试播放，如果失败则提示用户手动播放
      try {
        await playWithAutoRecord(mediaEl); // [MOD]
      } catch (e) {
        log(`自动播放失败: ${e.message}`);
        statusEl.textContent = "状态：请手动点击播放按钮开始播放";
      }
    } else {
      statusEl.textContent = "状态：本地问卷已开始，等待你的回答";
    }
  } catch (error) {
    log(`启动本地问卷失败: ${error.message}`);
    statusEl.textContent = "状态：启动失败，请重试";
  }
}

async function switchToAgent() {
  try {
    log("🤖 切换到智谱Agent模式...");
    statusEl.textContent = "状态：正在切换到智谱Agent模式...";

    hideAssessmentReport();
    isLocalQuestionnaire = false;
    isAgentMode = true;

    // 更新按钮状态
    updateButtonStates();

    // 隐藏本地问卷特有的显示元素
    document.getElementById("questionInfo").style.display = "none";
    document.getElementById("progressInfo").style.display = "none";

    // 重置状态
    sessionId = null;
    currentQuestionInfo = null;

    // 清空当前显示
    qEl.textContent = "（等待开始）";
    qEl.style.color = "#333";
    qEl.style.fontWeight = "normal";
    aEl.textContent = "（等待录音）";
    audioEl.src = "";
    // [ADD] 清空视频
    if (videoEl) {
      videoEl.pause();
      videoEl.removeAttribute("src");
      videoEl.style.display = "none";
    }

    // 录音按钮现在是自动的，不需要手动设置

    // 清空对话历史
    conversationHistory = [];
    updateHistoryDisplay();
    hideAssessmentReport();

    // 重置本地问卷状态
    isLocalQuestionnaire = false;
    isAgentMode = false;
    currentQuestionInfo = null;

    // 隐藏问题信息和进度
    document.getElementById("questionInfo").style.display = "none";
    document.getElementById("progressInfo").style.display = "none";

    statusEl.textContent = "状态：已切换到智谱Agent模式，点击'开始对话'开始";
    log("✅ 成功切换到智谱Agent模式");

  } catch (error) {
    log(`切换到智谱Agent模式失败: ${error.message}`);
    statusEl.textContent = "状态：切换失败，请重试";
  }
}

function updateButtonStates() {
  const btnStart = document.getElementById("btnStart");
  const btnStartLocal = document.getElementById("btnStartLocal");
  const btnSwitchToAgent = document.getElementById("btnSwitchToAgent");

  if (isLocalQuestionnaire) {
    // 本地问卷模式
    btnStart.disabled = true;
    btnStartLocal.disabled = true;
    btnSwitchToAgent.disabled = false;
    btnSwitchToAgent.textContent = "🤖 切换到智谱Agent";
    log("📋 当前模式：本地问卷");
  } else if (isAgentMode) {
    // 智谱Agent模式
    btnStart.disabled = false;
    btnStartLocal.disabled = false;
    btnSwitchToAgent.disabled = true;
    btnSwitchToAgent.textContent = "📋 切换到本地问卷";
    log("🤖 当前模式：智谱Agent");
  } else {
    // 初始状态
    btnStart.disabled = false;
    btnStartLocal.disabled = false;
    btnSwitchToAgent.disabled = false;
    btnSwitchToAgent.textContent = "🤖 切换到智谱Agent";
    log("🔄 当前模式：未选择");
  }
}

async function submitAnswerText(text) {
  try {
    aEl.textContent = text;
    log(`提交回答: "${text}"`);

    addToHistory('answer', text);

    let res, data;

    if (isLocalQuestionnaire) {
      // 本地问卷
      res = await fetch("/api/local_questionnaire/reply", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ session_id: sessionId, answer: text })
      });
    } else {
      // 智谱AI对话
      res = await fetch("/api/agent/reply", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ session_id: sessionId, answer: text })
      });
    }

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${res.status}: ${res.statusText}`);
    }

    data = await res.json();

    if (data.error) {
      throw new Error(data.error);
    }

    // 添加调试日志
    log(`🔍 调试信息：`);
    log(`  - is_complete: ${data.is_complete}`);
    log(`  - question长度: ${data.question ? data.question.length : 0}`);
    log(`  - question内容预览: ${data.question ? data.question.substring(0, 100) + '...' : '无'}`);

    sessionId = data.session_id;
    const question = data.question || "(无)";
    qEl.textContent = question;

    // [MOD] 优先使用视频，其次音频
    const mediaEl = setTTSAndVideo(data.tts_url, data.video_url, data.is_complete ? "正在播放评估结果..." : "正在播放新问题..."); // [MOD]

    if (data.is_complete) {
      log("🎉 问卷已完成！");
      log(`✅ 后端返回is_complete=True，开始显示评估报告`);
      statusEl.textContent = "状态：问卷已完成，显示总结报告";

      addToHistory('summary', question);

      qEl.style.color = "#28a745";
      qEl.style.fontWeight = "bold";

      document.getElementById("btnRec").disabled = true;
      document.getElementById("btnStop").disabled = true;

      log(`📊 调用showAssessmentReport()显示评估报告区域`);
      showAssessmentReport();

      // 检查是否是评估报告（多种关键词匹配）
      const isReport = question.includes("肺癌早筛风险评估报告") ||
                      question.includes("评估报告") ||
                      question.includes("风险评估") ||
                      question.includes("报告") ||
                      question.length > 500;  // 长文本可能是报告

      log(`🔍 报告检测结果：`);
      log(`  - 包含"肺癌早筛风险评估报告": ${question.includes("肺癌早筛风险评估报告")}`);
      log(`  - 包含"评估报告": ${question.includes("评估报告")}`);
      log(`  - 包含"风险评估": ${question.includes("风险评估")}`);
      log(`  - 包含"报告": ${question.includes("报告")}`);
      log(`  - 文本长度>500: ${question.length > 500}`);
      log(`  - 最终判断: ${isReport ? '是评估报告' : '不是评估报告'}`);

      if (isReport) {
        // 尝试解析为Markdown格式
        let reportHtml;
        try {
          reportHtml = marked.parse(question);
          log(`✅ Markdown解析成功`);
        } catch (e) {
          // 如果Markdown解析失败，直接显示文本
          reportHtml = question.replace(/\n/g, '<br>');
          log(`⚠️ Markdown解析失败，使用HTML换行: ${e.message}`);
        }

        log(`📝 设置报告内容到reportContentEl`);
        reportContentEl.innerHTML = `<div class="report-text markdown-content">${reportHtml}</div>`;
        log("检测到评估报告，直接显示内容");
        log(`报告内容长度: ${question.length}`);
        log(`报告类型: ${isReport ? '评估报告' : '普通回复'}`);

        // [MOD] 统一播放（视频优先），结束后不再自动录音（完成态一般不再录）
        if (mediaEl) {
          showTTSIndicator("正在播放评估报告...");
          statusEl.textContent = "状态：正在播放评估报告...";
          try {
            await mediaEl.play();
            mediaEl.onended = () => {
              hideTTSIndicator();
              statusEl.textContent = "状态：播放完成";
              log("评估报告播放完成");
            };
          } catch (e) {
            hideTTSIndicator();
            log(`媒体播放失败: ${e.message}`);
            statusEl.textContent = "状态：媒体播放失败，但报告已显示";
          }
        }
      } else {
        // 虽然不是明确的评估报告，但可能是其他形式的完成结果
        log(`📝 设置完成结果内容到reportContentEl（非标准报告格式）`);
        reportContentEl.innerHTML = `
          <div class="info-message">
            <h4>问卷已完成</h4>
            <p>以下是智谱AI的回复：</p>
            <div class="completion-text">${question.replace(/\n/g, '<br>')}</div>
          </div>
        `;
        log("问卷已完成，显示完成结果内容");
        log(`完成结果长度: ${question.length}`);

        // [MOD] 同样仅播放一次（不再触发自动录音）
        if (mediaEl) {
          showTTSIndicator("正在播放完成结果...");
          statusEl.textContent = "状态：正在播放完成结果...";
          try {
            await mediaEl.play();
            mediaEl.onended = () => {
              hideTTSIndicator();
              statusEl.textContent = "状态：播放完成";
              log("完成结果播放完成");
            };
          } catch (e) {
            hideTTSIndicator();
            log(`媒体播放失败: ${e.message}`);
            statusEl.textContent = "状态：媒体播放失败，但结果已显示";
          }
        }
      }
    } else {
      log(`⏳ 问卷未完成，继续下一题`);
      // 检查是否是API调用失败
      if (question.includes("智谱AI暂时不可用") || question.includes("系统暂时不可用")) {
        log("⚠️ 智谱AI调用失败，请稍后重试");
        statusEl.textContent = "状态：智谱AI暂时不可用，请稍后重试";
        statusEl.style.color = "#dc3545";
        statusEl.style.backgroundColor = "#f8d7da";

        addToHistory('error', question);
        qEl.style.color = "#dc3545";

        // 显示重新开始按钮
        btnRestart.style.display = "inline-block";

        return; // 不继续处理
      }

      // 检查是否是Agent流程错误（需要重新询问）
      if (question.includes("Agent流程错误")) {
        log("⚠️ 检测到Agent流程错误，正在重新询问问题...");
        statusEl.textContent = "状态：正在重新询问问题...";
        statusEl.style.color = "#ffc107";
        statusEl.style.backgroundColor = "#fff3cd";

        addToHistory('warning', "刚才的问题出现了错误，正在重新询问...");
        qEl.style.color = "#ffc107";

        // [MOD] 统一播放（视频/音频），本分支不自动录音
        if (mediaEl) {
          showTTSIndicator("正在播放重新询问...");
          statusEl.textContent = "状态：正在播放重新询问...";
          try {
            await mediaEl.play();
            mediaEl.onended = () => {
              hideTTSIndicator();
              statusEl.textContent = "状态：语音播放完成，等待回答";
              log("媒体播放完成");
            };
          } catch (e) {
            hideTTSIndicator();
            log(`媒体播放失败: ${e.message}`);
            statusEl.textContent = "状态：媒体播放失败，但问题已显示";
          }
        }
        return;
      }

      if (isLocalQuestionnaire) {
        if (data.question_info) {
          currentQuestionInfo = data.question_info;
          document.getElementById("questionInfo").style.display = "block";
          document.getElementById("questionInfoText").textContent = `${currentQuestionInfo.category} - ${currentQuestionInfo.format}`;
        }

        if (data.progress) {
          document.getElementById("progressInfo").style.display = "block";
          document.getElementById("progressInfo").textContent = data.progress;
        }

        addToHistory('question', `[本地问卷] ${question}`);
        log(`本地问卷下一题: "${question}"`);
        log(`问题分类: ${currentQuestionInfo?.category}, 格式要求: ${currentQuestionInfo?.format}`);
      } else {
        // 智谱AI对话处理
        if (question.includes("智谱AI暂时不可用") || question.includes("系统暂时不可用")) {
          log("⚠️ 智谱AI调用失败，请稍后重试");
          statusEl.textContent = "状态：智谱AI暂时不可用，请稍后重试";
          statusEl.style.color = "#dc3545";
          statusEl.style.backgroundColor = "#f8d7da";

          addToHistory('error', question);
          qEl.style.color = "#dc3545";

          // 禁用录音按钮
          document.getElementById("btnRec").disabled = true;
          document.getElementById("btnStop").disabled = true;

          // 显示重新开始按钮
          btnRestart.style.display = "inline-block";

          return;
        }

        if (question.includes("Agent流程错误")) {
          log("⚠️ 检测到Agent流程错误，正在重新询问问题...");
          statusEl.textContent = "状态：正在重新询问问题...";
          statusEl.style.color = "#ffc107";
          statusEl.style.backgroundColor = "#fff3cd";

          addToHistory('warning', "刚才的问题出现了错误，正在重新询问...");
          qEl.style.color = "#ffc107";

          // [MOD] 统一播放（视频/音频），结束后自动录音
          if (mediaEl) {
            showTTSIndicator("正在播放重新询问...");
            statusEl.textContent = "状态：正在播放重新询问...";
            try {
              await mediaEl.play();
              mediaEl.onended = () => {
                hideTTSIndicator();
                statusEl.textContent = "状态：语音播放完成，自动开始录音...";
                log("媒体播放完成，自动开始录音");
                setTimeout(() => {
                  if (isAgentMode || isLocalQuestionnaire) {
                    startRecording();
                  }
                }, 500);
              };
            } catch (e) {
              hideTTSIndicator();
              log(`媒体播放失败: ${e.message}`);
              statusEl.textContent = "状态：媒体播放失败，但问题已显示";
            }
          }
          return;
        }

        addToHistory('question', question);
        log(`获取到下一题: "${question}"`);
      }

      // [MOD] 统一播放新问题（视频优先），播放后自动录音
      if (mediaEl) {
        statusEl.textContent = "状态：正在播放新问题语音/视频...";
        // 尝试播放，如果失败则提示用户手动播放
        try {
          await playWithAutoRecord(mediaEl); // [MOD]
        } catch (e) {
          log(`自动播放失败: ${e.message}`);
          statusEl.textContent = "状态：请手动点击播放按钮开始播放";
        }
      } else {
        statusEl.textContent = "状态：已获取下一题";
      }
    }
  } catch (error) {
    log(`提交回答失败: ${error.message}`);
    statusEl.textContent = "状态：提交失败，请重试";
  }
}

async function startRecording() {
  try {
    log("请求麦克风权限...");
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    log("麦克风权限获取成功");

    recordingIndicator.style.display = 'flex';

    startVolumeVisualization(stream);

    const options = {
      mimeType: 'audio/speex;rate=16000',
      audioBitsPerSecond: 16000
    };

    try {
      mediaRecorder = new MediaRecorder(stream, options);
      log("使用Speex-WB格式录音 (16kHz)");
    } catch (e) {
      log(`Speex格式不支持: ${e.message}`);

      const fallbackOptions = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4'
      ];

      let recorder = null;
      for (const mimeType of fallbackOptions) {
        try {
          if (MediaRecorder.isTypeSupported(mimeType)) {
            recorder = new MediaRecorder(stream, { mimeType });
            log(`回退到格式: ${mimeType}`);
            break;
          }
        } catch (e2) {
          continue;
        }
      }

      if (!recorder) {
        recorder = new MediaRecorder(stream);
        log("使用默认格式");
      }

      mediaRecorder = recorder;
    }

    chunks = [];
    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) {
        chunks.push(e.data);
        log(`录音数据块: ${e.data.size} bytes`);
      }
    };

    mediaRecorder.onstop = async () => {
      recordingIndicator.style.display = 'none';

      // 停止静音检测
      if (window.silenceTimer) {
        cancelAnimationFrame(window.silenceTimer);
        window.silenceTimer = null;
        log("静音检测已停止");
      }

      stopVolumeVisualization();

      const mimeType = mediaRecorder.mimeType || 'audio/speex';
      let fileExtension = 'webm';

      if (mimeType.includes('speex')) {
        fileExtension = 'spx';
      } else if (mimeType.includes('opus')) {
        fileExtension = 'opus';
      } else if (mimeType.includes('mp4')) {
        fileExtension = 'm4a';
      } else if (mimeType.includes('ogg')) {
        fileExtension = 'ogg';
      }

      log(`录音完成，格式: ${mimeType}, 扩展名: ${fileExtension}`);
      log(`录音数据大小: ${chunks.reduce((sum, chunk) => sum + chunk.size, 0)} bytes`);

      const blob = new Blob(chunks, { type: mimeType });
      const fd = new FormData();
      fd.append("audio", blob, `record.${fileExtension}`);

      statusEl.textContent = "状态：识别中…";
      log("开始语音识别...");

      const res = await fetch("/api/asr", { method: "POST", body: fd });
      const data = await res.json();
      const text = data.text || "";

      log(`语音识别结果: "${text}"`);
      statusEl.textContent = "状态：识别完成，提交给Agent…";

      await submitAnswerText(text);
    };

    mediaRecorder.start();
    statusEl.textContent = "状态：录音中…";
    statusEl.classList.add("recording");

    // 隐藏录音按钮（现在是自动录音）
    document.getElementById("btnRec").style.display = 'none';
    document.getElementById("btnStop").style.display = 'none';

    // 启动6秒无声音自动停止录音的定时器
    let lastVolume = 0;
    let silenceStartTime = null;

    // 音量检测函数
    const checkSilence = () => {
      if (analyser && dataArray) {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const currentVolume = sum / dataArray.length;

        // 每100次检测输出一次音量信息（避免日志过多）
        if (!window.volumeLogCounter) window.volumeLogCounter = 0;
        window.volumeLogCounter++;
        if (window.volumeLogCounter % 100 === 0) {
          log(`🔊 当前音量: ${currentVolume.toFixed(2)}, 静音阈值: 100, 静音计时: ${silenceStartTime ? ((Date.now() - silenceStartTime) / 1000).toFixed(1) + 's' : '未开始'}`);
        }

        // 如果音量很低（静音）
        if (currentVolume < 100) {
          if (silenceStartTime === null) {
            silenceStartTime = Date.now();
            log("🔇 检测到静音开始，开始计时...");
          } else {
            const silenceDuration = Date.now() - silenceStartTime;
            if (silenceDuration > 6000) { // 6秒静音
              log(`⏰ 检测到${(silenceDuration / 1000).toFixed(1)}秒静音，自动停止录音`);
              stopRecording();
              return;
            }
          }
        } else {
          // 有声音，重置静音计时
          if (silenceStartTime !== null) {
            log(`🔊 检测到声音(${currentVolume.toFixed(2)})，重置静音计时`);
            silenceStartTime = null;
          }
        }

        lastVolume = currentVolume;
      } else {
        log("⚠️ 音频分析器未就绪，无法检测音量");
      }

      // 继续检测
      window.silenceTimer = requestAnimationFrame(checkSilence);
    };

    // 开始音量检测
    window.silenceTimer = requestAnimationFrame(checkSilence);

    log("录音开始，已启动6秒静音自动停止功能");
  } catch (error) {
    log(`录音启动失败: ${error.message}`);
    statusEl.textContent = "状态：录音失败，请检查麦克风权限";

    recordingIndicator.style.display = 'none';
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    // 停止静音检测
    if (window.silenceTimer) {
      cancelAnimationFrame(window.silenceTimer);
      window.silenceTimer = null;
      log("静音检测已停止");
    }

    mediaRecorder.stop();
    statusEl.classList.remove("recording");

    // 隐藏录音按钮（现在是自动录音）
    document.getElementById("btnRec").style.display = 'none';
    document.getElementById("btnStop").style.display = 'none';

    log("录音停止");
  }
}

document.addEventListener('DOMContentLoaded', function() {
  log("页面加载完成，系统就绪");
  log("支持的音频格式检查中...");

  if (typeof MediaRecorder !== 'undefined') {
    const supportedTypes = MediaRecorder.isTypeSupported;
    if (supportedTypes('audio/speex;rate=16000')) {
      log("✅ 支持Speex-WB格式 (16kHz)");
    } else {
      log("⚠️ 不支持Speex-WB格式，将使用默认格式");
    }
  } else {
    log("❌ 浏览器不支持MediaRecorder API");
  }

  updateHistoryDisplay();

  // 设置按钮事件监听器
  document.getElementById("btnStart").addEventListener("click", startConversation);
  document.getElementById("btnStartLocal").addEventListener("click", startLocalQuestionnaire);
  document.getElementById("btnSwitchToAgent").addEventListener("click", switchToAgent);
  document.getElementById("btnRec").addEventListener("click", startRecording);
  document.getElementById("btnStop").addEventListener("click", stopRecording);
  document.getElementById("btnRestart").addEventListener("click", restartConversation);
  document.getElementById("btnExpandHistory").addEventListener("click", toggleHistory);
  document.getElementById("btnCollapseHistory").addEventListener("click", toggleHistory);



  // 初始化按钮状态
  updateButtonStates();

  // 显示当前模式状态
  log("🎯 系统初始化完成");
  log("📋 可用模式：本地问卷、智谱Agent");
  log("💡 点击相应按钮选择模式");

  log("所有按钮事件监听器已设置完成");

  // 初始化报告列表
  if (btnRefreshReports) {
    btnRefreshReports.addEventListener('click', loadReportsList);
    loadReportsList();
  }
});

async function loadReportsList() {
  try {
    reportsListEl.innerHTML = '<div class="loading">加载报告列表...</div>';
    reportsStatsEl.textContent = '统计加载中...';

    const res = await fetch('/api/reports');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const reports = data.reports || [];
    const stats = data.stats || {};

    reportsStatsEl.textContent = `数量: ${stats.total_reports || 0}，总大小: ${stats.total_size_mb || 0} MB，目录: ${stats.reports_dir || ''}`;

    if (reports.length === 0) {
      reportsListEl.innerHTML = '<div class="info-message">暂无报告</div>';
      return;
    }

    const frag = document.createDocumentFragment();
    reports.forEach(r => {
      const item = document.createElement('div');
      item.className = 'report-item';
      const name = document.createElement('div');
      name.className = 'report-name';
      name.textContent = `${r.filename} （${r.created}）`;

      const actions = document.createElement('div');
      actions.className = 'report-actions';

      const viewBtn = document.createElement('button');
      viewBtn.className = 'secondary-btn';
      viewBtn.textContent = '查看内容';
      viewBtn.onclick = () => viewReportContent(r.filename);

      const dlBtn = document.createElement('button');
      dlBtn.textContent = '下载';
      dlBtn.onclick = () => {
        window.open(`/api/reports/download/${encodeURIComponent(r.filename)}`, '_blank');
      };

      actions.appendChild(viewBtn);
      actions.appendChild(dlBtn);
      item.appendChild(name);
      item.appendChild(actions);
      frag.appendChild(item);
    });

    reportsListEl.innerHTML = '';
    reportsListEl.appendChild(frag);
  } catch (e) {
    reportsListEl.innerHTML = `<div class="error-message">加载失败: ${e.message}</div>`;
  }
}

async function viewReportContent(filename) {
  try {
    const res = await fetch(`/api/reports/content/${encodeURIComponent(filename)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const content = data.content || '';

    // 弹窗显示（简单实现）
    const preview = document.createElement('div');
    preview.style.position = 'fixed';
    preview.style.left = '0';
    preview.style.top = '0';
    preview.style.right = '0';
    preview.style.bottom = '0';
    preview.style.background = 'rgba(0,0,0,0.5)';
    preview.style.display = 'flex';
    preview.style.alignItems = 'center';
    preview.style.justifyContent = 'center';
    preview.style.zIndex = '9999';

    const box = document.createElement('div');
    box.style.width = '90%';
    box.style.maxWidth = '800px';
    box.style.maxHeight = '80%';
    box.style.overflow = 'auto';
    box.style.background = '#fff';
    box.style.borderRadius = '8px';
    box.style.padding = '16px';
    box.innerHTML = `<h3 style="margin-top:0;">${filename}</h3><pre style="white-space:pre-wrap;">${content.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}</pre>`;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'secondary-btn';
    closeBtn.textContent = '关闭';
    closeBtn.style.marginTop = '10px';
    closeBtn.onclick = () => document.body.removeChild(preview);
    box.appendChild(closeBtn);

    preview.appendChild(box);
    document.body.appendChild(preview);
  } catch (e) {
    alert(`读取失败: ${e.message}`);
  }
}

// 测试函数：测试评估报告显示
function testAssessmentReport() {
  log("🧪 开始测试评估报告显示功能");

  // 测试1：检查DOM元素是否存在
  log(`📋 DOM元素检查:`);
  log(`  - assessmentReportEl: ${assessmentReportEl ? '存在' : '不存在'}`);
  log(`  - reportContentEl: ${reportContentEl ? '存在' : '不存在'}`);
  log(`  - reportAudioEl: ${reportAudioEl ? '存在' : '不存在'}`);

  // 测试2：检查当前显示状态
  if (assessmentReportEl) {
    const currentDisplay = assessmentReportEl.style.display;
    log(`  - 当前评估报告显示状态: ${currentDisplay}`);
    log(`  - 当前评估报告可见性: ${assessmentReportEl.offsetParent !== null ? '可见' : '不可见'}`);
  }

  // 测试3：测试显示/隐藏功能
  log(`🔄 测试显示/隐藏功能`);
  showAssessmentReport();
  log(`✅ 调用showAssessmentReport()完成`);

  // 测试4：设置测试内容
  if (reportContentEl) {
    const testContent = `
      <div class="report-text markdown-content">
        <h1>🧪 测试评估报告</h1>
        <p>这是一个测试报告，用于验证评估报告显示功能是否正常工作。</p>
        <h2>测试内容</h2>
        <ul>
          <li>✅ 报告区域显示</li>
          <li>✅ 内容渲染</li>
          <li>✅ 样式应用</li>
        </ul>
        <p><strong>如果能看到这个测试报告，说明显示功能正常！</strong></p>
      </div>
    `;
    reportContentEl.innerHTML = testContent;
    log(`📝 设置测试内容完成`);
  }

  // 测试5：检查最终状态
  setTimeout(() => {
    if (assessmentReportEl) {
      const finalDisplay = assessmentReportEl.style.display;
      log(`📊 最终状态检查:`);
      log(`  - 显示状态: ${finalDisplay}`);
      log(`  - 可见性: ${assessmentReportEl.offsetParent !== null ? '可见' : '不可见'}`);
      log(`  - 内容长度: ${reportContentEl ? reportContentEl.innerHTML.length : 0}`);
    }
    log(`🧪 测试完成`);
  }, 100);
}

// 测试函数：测试完成状态
function testCompleteStatus() {
  log("🧪 开始测试完成状态功能");

  // 模拟一个完整的响应数据
  const mockCompleteData = {
    session_id: "test_session_" + Date.now(),
    question: "肺癌早筛风险评估报告\n\n【基本信息】\n姓名：测试用户\n性别：男\n年龄：35岁\n\n【风险评估】\n🟡 中风险：建议定期体检，关注症状变化\n\n【建议措施】\n1. 戒烟限酒，避免二手烟\n2. 保持室内通风，减少油烟接触\n3. 定期体检，关注肺部健康",
    tts_url: "/static/tts/test.wav",
    video_url: "", // [ADD] 可填入测试视频 URL 体验视频播放
    is_complete: true
  };

  log(`📋 模拟数据:`);
  log(`  - is_complete: ${mockCompleteData.is_complete}`);
  log(`  - question长度: ${mockCompleteData.question.length}`);
  log(`  - question内容预览: ${mockCompleteData.question.substring(0, 100)}...`);

  // 模拟处理完成状态
  log(`🔄 模拟处理完成状态...`);

  qEl.textContent = mockCompleteData.question;
  qEl.style.color = "#28a745";
  qEl.style.fontWeight = "bold";

  showAssessmentReport();

  if (reportContentEl) {
    const reportHtml = marked.parse(mockCompleteData.question);
    reportContentEl.innerHTML = `<div class="report-text markdown-content">${reportHtml}</div>`;
    log(`📝 设置模拟报告内容完成`);
  }

  statusEl.textContent = "状态：测试完成状态 - 问卷已完成，显示总结报告";
  statusEl.style.color = "#28a745";
  statusEl.style.backgroundColor = "#d4edda";

  // [ADD] 使用统一媒体播放
  const mediaEl = setTTSAndVideo(mockCompleteData.tts_url, mockCompleteData.video_url, "正在播放评估报告...");
  if (mediaEl) {
    mediaEl.play().then(() => {
      mediaEl.onended = () => {
        hideTTSIndicator();
        statusEl.textContent = "状态：播放完成";
      };
    }).catch(e => {
      hideTTSIndicator();
      log(`媒体播放失败: ${e.message}`);
    });
  }

  log(`✅ 模拟完成状态处理完成`);
  log(`🧪 测试完成`);
}

// 测试音频播放功能
function testAudioPlayback() {
  const testAudioUrl = "/static/tts/session_1962742694975586304_935e63251b9a4d5995e50c4419cac608.mp3";
  log(`开始测试音频播放: ${testAudioUrl}`);
  
  // 设置音频
  audioEl.src = testAudioUrl;
  audioEl.muted = false;
  audioEl.volume = 1.0;
  audioEl.preload = "auto";
  
  // 添加事件监听器
  audioEl.onloadstart = () => log('测试音频开始加载');
  audioEl.oncanplay = () => log('测试音频可以播放');
  audioEl.oncanplaythrough = () => log('测试音频可以流畅播放');
  audioEl.onerror = (e) => log(`测试音频加载错误: ${e.message || '未知错误'}`);
  audioEl.onplay = () => log('测试音频开始播放');
  audioEl.onended = () => log('测试音频播放结束');
  
  // 尝试播放
  audioEl.play().then(() => {
    log('测试音频播放成功');
  }).catch(e => {
    log(`测试音频播放失败: ${e.message}`);
  });
}

// 在页面加载完成后添加测试按钮
document.addEventListener('DOMContentLoaded', function() {
  // 添加测试按钮
  const testButton = document.createElement('button');
  testButton.textContent = '🧪 测试音频播放';
  testButton.className = 'secondary-btn';
  testButton.style.marginTop = '10px';
  testButton.onclick = testAudioPlayback;
  
  const debugSection = document.querySelector('.debug-info');
  if (debugSection) {
    debugSection.appendChild(testButton);
  }
});
