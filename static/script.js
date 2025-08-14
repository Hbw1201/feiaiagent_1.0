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

document.addEventListener("DOMContentLoaded", fetchSystemStatus);

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
    audioEl.src = data.tts_url;
    
    addToHistory('question', question);
    
    log(`智谱AI对话启动成功，会话ID: ${sessionId}`);
    log(`获取到问题: ${question}`);
    
        // 播放TTS音频
    try {
      showTTSIndicator("正在播放问题语音...");
      log("TTS播放开始 - 正在将问题读给用户听");
      statusEl.textContent = "状态：正在播放问题语音...";
      
      // 播放TTS音频
      await audioEl.play();
      
      // TTS播放完成后自动开始录音
      audioEl.onended = () => {
        hideTTSIndicator();
        statusEl.textContent = "状态：语音播放完成，自动开始录音...";
        log("TTS播放完成，自动开始录音");

        // 自动开始录音
        setTimeout(() => {
          if (isAgentMode) { // 确保智谱AI对话已开始
            startRecording();
          }
        }, 500); // 延迟500ms开始录音，给用户准备时间
      };
    } catch (e) {
      hideTTSIndicator();
      log(`TTS播放失败: ${e.message}`);
      statusEl.textContent = "状态：TTS播放失败，但问题已显示";
    }
    
    statusEl.textContent = "状态：已开始，等待你的回答";
    // 录音按钮现在是自动的，不需要手动启用
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
      throw new Error(data.error || `HTTP ${res.status}: ${res.statusText}`);
    }
    
    const data = await res.json();
    
    if (data.error) {
      throw new Error(data.error);
    }
    
    sessionId = data.session_id;
    const question = data.question || "(无)";
    qEl.textContent = question;
    audioEl.src = data.tts_url;
    
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
    
        // 播放TTS音频
    try {
      showTTSIndicator("正在播放问题语音...");
      log("TTS播放开始 - 正在将问题读给用户听");
      statusEl.textContent = "状态：正在播放问题语音...";
      
      // 播放TTS音频
      await audioEl.play();
      
      // TTS播放完成后自动开始录音
      audioEl.onended = () => {
        hideTTSIndicator();
        statusEl.textContent = "状态：语音播放完成，自动开始录音...";
        log("TTS播放完成，自动开始录音");

        // 自动开始录音
        setTimeout(() => {
          if (isLocalQuestionnaire) { // 确保本地问卷已开始
            startRecording();
          }
        }, 500); // 延迟500ms开始录音，给用户准备时间
      };
    } catch (e) {
      hideTTSIndicator();
      log(`TTS播放失败: ${e.message}`);
      statusEl.textContent = "状态：TTS播放失败，但问题已显示";
    }
    
    statusEl.textContent = "状态：本地问卷已开始，等待你的回答";
    // 录音按钮现在是自动的，不需要手动启用
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
    
    sessionId = data.session_id;
    const question = data.question || "(无)";
    qEl.textContent = question;
    audioEl.src = data.tts_url;
    
    if (data.is_complete) {
      log("🎉 问卷已完成！");
      statusEl.textContent = "状态：问卷已完成，显示总结报告";
      
      addToHistory('summary', question);
      
      qEl.style.color = "#28a745";
      qEl.style.fontWeight = "bold";
      
      document.getElementById("btnRec").disabled = true;
      document.getElementById("btnStop").disabled = true;
      
      showAssessmentReport();
      
      // 检查是否是评估报告（多种关键词匹配）
      const isReport = question.includes("肺癌早筛风险评估报告") || 
                      question.includes("评估报告") || 
                      question.includes("风险评估") || 
                      question.includes("报告") ||
                      question.length > 500;  // 长文本可能是报告
      
      if (isReport) {
        // 尝试解析为Markdown格式
        let reportHtml;
        try {
          reportHtml = marked.parse(question);
        } catch (e) {
          // 如果Markdown解析失败，直接显示文本
          reportHtml = question.replace(/\n/g, '<br>');
        }
        
        reportContentEl.innerHTML = `<div class="report-text markdown-content">${reportHtml}</div>`;
        log("检测到评估报告，直接显示内容");
        log(`报告内容长度: ${question.length}`);
        log(`报告类型: ${isReport ? '评估报告' : '普通回复'}`);
        
        // 播放评估报告TTS音频
        try {
          showTTSIndicator("正在播放评估报告语音...");
          log("TTS播放开始 - 正在将评估报告读给用户听");
          statusEl.textContent = "状态：正在播放评估报告语音...";
          
          // 播放TTS音频
          await audioEl.play();
          
          // TTS播放完成后自动开始录音
          audioEl.onended = () => {
            hideTTSIndicator();
            statusEl.textContent = "状态：语音播放完成，自动开始录音...";
            log("TTS播放完成，自动开始录音");
            
            // 自动开始录音
            setTimeout(() => {
              if (isAgentMode) { // 确保智谱AI对话已开始
                startRecording();
              }
            }, 500); // 延迟500ms开始录音，给用户准备时间
          };
        } catch (e) {
          hideTTSIndicator();
          log(`TTS播放失败: ${e.message}`);
          statusEl.textContent = "状态：TTS播放失败，但报告已显示";
        }
      } else {
        // 虽然不是明确的评估报告，但可能是其他形式的完成结果
        reportContentEl.innerHTML = `
          <div class="info-message">
            <h4>问卷已完成</h4>
            <p>以下是智谱AI的回复：</p>
            <div class="completion-text">${question.replace(/\n/g, '<br>')}</div>
          </div>
        `;
        log("问卷已完成，显示完成结果内容");
        log(`完成结果长度: ${question.length}`);
        
        // 播放问卷完成结果TTS音频
        try {
          showTTSIndicator("正在播放完成结果语音...");
          log("TTS播放开始 - 正在将完成结果读给用户听");
          statusEl.textContent = "状态：正在播放完成结果语音...";
          
          // 播放TTS音频
          await audioEl.play();
          
          // TTS播放完成后自动开始录音
          audioEl.onended = () => {
            hideTTSIndicator();
            statusEl.textContent = "状态：语音播放完成，自动开始录音...";
            log("TTS播放完成，自动开始录音");
            
            // 自动开始录音
            setTimeout(() => {
              if (isAgentMode) { // 确保智谱AI对话已开始
                startRecording();
              }
            }, 500); // 延迟500ms开始录音，给用户准备时间
          };
        } catch (e) {
          hideTTSIndicator();
          log(`TTS播放失败: ${e.message}`);
          statusEl.textContent = "状态：TTS播放失败，但结果已显示";
        }
      }
    } else {
      // 检查是否是API调用失败
      if (question.includes("智谱AI暂时不可用") || question.includes("系统暂时不可用")) {
        log("⚠️ 智谱AI调用失败，请稍后重试");
        statusEl.textContent = "状态：智谱AI暂时不可用，请稍后重试";
        statusEl.style.color = "#dc3545";
        statusEl.style.backgroundColor = "#f8d7da";
        
        addToHistory('error', question);
        qEl.style.color = "#dc3545";
        
        // 录音按钮现在是自动的，不需要手动禁用
        
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
        
        // 录音按钮现在是自动的，不需要手动设置
        
        // 播放重新询问问题的TTS音频
        try {
          showTTSIndicator("正在播放重新询问问题语音...");
          log("TTS播放开始 - 正在将重新询问的问题读给用户听");
          statusEl.textContent = "状态：正在播放重新询问问题语音...";
          
          // 播放TTS音频
          await audioEl.play();
          
          // TTS播放完成后
          audioEl.onended = () => {
            hideTTSIndicator();
            statusEl.textContent = "状态：语音播放完成，等待回答";
            log("TTS播放完成");
          };
        } catch (e) {
          hideTTSIndicator();
          log(`TTS播放失败: ${e.message}`);
          statusEl.textContent = "状态：TTS播放失败，但问题已显示";
        }
        
        return; // 不继续处理
      }
      
      if (isLocalQuestionnaire) {
        // 本地问卷继续下一题
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
        log(`本地问卷下一题: "${question}"`);
        log(`问题分类: ${currentQuestionInfo?.category}, 格式要求: ${currentQuestionInfo?.format}`);
      } else {
        // 智谱AI对话处理
        // 检查是否是API调用失败
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
          
                  // 录音按钮现在是自动的，不需要手动设置
          
          // 播放重新询问问题的TTS音频
          try {
            showTTSIndicator("正在播放重新询问问题语音...");
            log("TTS播放开始 - 正在将重新询问的问题读给用户听");
            statusEl.textContent = "状态：正在播放重新询问问题语音...";
            
            // 播放TTS音频
            await audioEl.play();
            
            // TTS播放完成后自动开始录音
            audioEl.onended = () => {
              hideTTSIndicator();
              statusEl.textContent = "状态：语音播放完成，自动开始录音...";
              log("TTS播放完成，自动开始录音");
              
              // 自动开始录音
              setTimeout(() => {
                if (isAgentMode || isLocalQuestionnaire) { // 确保对话已开始
                  startRecording();
                }
              }, 500); // 延迟500ms开始录音，给用户准备时间
            };
          } catch (e) {
            hideTTSIndicator();
            log(`TTS播放失败: ${e.message}`);
            statusEl.textContent = "状态：TTS播放失败，但问题已显示";
          }
          
          return; // 不继续处理
        }
        
        // 继续下一题
        addToHistory('question', question);
        log(`获取到下一题: "${question}"`);
      }
      
      // 播放新问题的TTS音频
      try {
        showTTSIndicator("正在播放新问题语音...");
        log("TTS播放开始 - 正在将新问题读给用户听");
        statusEl.textContent = "状态：正在播放新问题语音...";
        
        // 播放TTS音频
        await audioEl.play();
        
        // TTS播放完成后自动开始录音
        audioEl.onended = () => {
          hideTTSIndicator();
          statusEl.textContent = "状态：语音播放完成，自动开始录音...";
          log("TTS播放完成，自动开始录音");
          
          // 自动开始录音
          setTimeout(() => {
            if (isAgentMode || isLocalQuestionnaire) { // 确保对话已开始
              startRecording();
            }
          }, 500); // 延迟500ms开始录音，给用户准备时间
        };
      } catch (e) {
        hideTTSIndicator();
        log(`TTS播放失败: ${e.message}`);
        statusEl.textContent = "状态：TTS播放失败，但问题已显示";
      }
      
      statusEl.textContent = "状态：已获取下一题";
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
          log(`🔊 当前音量: ${currentVolume.toFixed(2)}, 静音阈值: 10, 静音计时: ${silenceStartTime ? ((Date.now() - silenceStartTime) / 1000).toFixed(1) + 's' : '未开始'}`);
        }
        
        // 如果音量很低（静音）
        if (currentVolume < 10) {
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
});


