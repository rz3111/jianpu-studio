# -*- coding: utf-8 -*-
with open('/Users/oneriver/Downloads/jianpu_studio.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update STATE definition
old_state_def = """    const STATE = {
      notes: [],              // 当前简谱音符: [{ midi: 60, duration: 1, isRest: false }, ...]
      key: 'C',               // 调号 ('C', 'G', 'D', 'A', 'E', 'F', 'Bb', 'Eb')
      timeSig: '4/4',         // 拍号
      bpm: 108,               // 速度
      quantGrid: 0.5,         // 量化最小单位 (0.5 = 八分音符, 0.25 = 十六分音符)
      scaleMode: 'major',     // 调式吸附模式: 'major' | 'pentatonic' | 'chromatic'
      selectedNoteIdx: -1,    // 当前选中编辑的音符索引
      isPlaying: false,       // 是否正在播放
      playbackTimers: [],     // 播放定时器
      audioCtx: null,         // Web Audio 上下文
      currentAudioBuffer: null, // AudioBuffer
      mediaRecorder: null,    // 录音器
      recordedChunks: [],     // 录音数据
      recordStartTime: 0,
      recordTimerInterval: null,
      omrData: null,          // 五线谱分析结果
      pitchContourData: null  // 音高与音符时序，用于 Piano Roll 绘制
    };"""

new_state_def = """    const STATE = {
      notes: [],              // 当前简谱音符: [{ midi: 60, duration: 1, isRest: false }, ...]
      key: 'C',               // 调号 ('C', 'G', 'D', 'A', 'E', 'F', 'Bb', 'Eb')
      timeSig: '4/4',         // 拍号
      bpm: 108,               // 速度
      quantGrid: 0.5,         // 量化最小单位 (0.5 = 八分音符, 0.25 = 十六分音符)
      scaleMode: 'major',     // 调式吸附模式: 'major' | 'pentatonic' | 'chromatic'
      selectedNoteIdx: -1,    // 当前选中编辑的音符索引
      isPlaying: false,       // 是否正在播放
      playbackTimers: [],     // 播放定时器
      playbackMasterGain: null, // 播放总控音量节点 (用于点击停止时 0 毫秒绝对静音)
      activeOscillators: [],  // 当前正在发声/计划发声的所有振荡器节点
      audioCtx: null,         // Web Audio 上下文
      currentAudioBuffer: null, // AudioBuffer
      mediaRecorder: null,    // 录音器
      recordedChunks: [],     // 录音数据
      recordStartTime: 0,
      recordTimerInterval: null,
      omrData: null,          // 五线谱分析结果
      pitchContourData: null, // 音高与音符时序，用于 Piano Roll 绘制
      previewZoom: 1.0,       // 大图预览缩放倍率
      currentPreviewType: null // 当前大图预览类型: 'waveform' | 'pitch' | 'omr'
    };"""

content = content.replace(old_state_def, new_state_def)

# 2. Update Playback: Stop immediately using master gain + activeOscillators tracking
old_playback_block = r"""    function togglePlayback() {
      if (STATE.isPlaying) {
        stopPlayback();
        return;
      }
      if (STATE.notes.length === 0) {
        showToast('当前没有可播放的音符', 'warning');
        return;
      }

      STATE.isPlaying = true;
      document.getElementById('playBtnText').textContent = '停止播放';
      const btn = document.getElementById('btnPlayToggle');
      btn.classList.replace('play-glow-btn', 'bg-rose-600');

      const ctx = getAudioContext();
      const secPerBeat = 60 / STATE.bpm;
      let currentTime = ctx.currentTime + 0.05;

      STATE.notes.forEach((note, idx) => {
        const durSec = note.duration * secPerBeat;
        const delayMs = Math.max(0, (currentTime - ctx.currentTime) * 1000);

        const timerOn = setTimeout(() => {
          document.querySelectorAll(`[class*="note-bg-"]`).forEach(el => el.setAttribute('fill', 'transparent'));
          const activeBg = document.querySelectorAll(`.note-bg-${idx}`);
          activeBg.forEach(el => {
            el.setAttribute('fill', '#fde68a');
          });
        }, delayMs);
        STATE.playbackTimers.push(timerOn);

        if (!note.isRest && note.midi > 0) {
          const freq = 440 * Math.pow(2, (note.midi - 69) / 12);
          playSynthTone(ctx, freq, currentTime, durSec * 0.92);
        }

        currentTime += durSec;
      });

      const endDelayMs = Math.max(0, (currentTime - ctx.currentTime) * 1000);
      const timerEnd = setTimeout(() => stopPlayback(), endDelayMs + 100);
      STATE.playbackTimers.push(timerEnd);
    }

    function playSynthTone(ctx, freq, startTime, duration) {
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const osc3 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = 'triangle';
      osc2.type = 'sine';
      osc3.type = 'sine';
      osc1.frequency.setValueAtTime(freq, startTime);
      osc2.frequency.setValueAtTime(freq * 2, startTime);
      osc3.frequency.setValueAtTime(freq * 3, startTime);

      const subGain2 = ctx.createGain();
      subGain2.gain.value = 0.28;
      const subGain3 = ctx.createGain();
      subGain3.gain.value = 0.12;

      gain.gain.setValueAtTime(0.001, startTime);
      gain.gain.exponentialRampToValueAtTime(0.35, startTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + Math.max(0.08, duration));

      osc1.connect(gain);
      osc2.connect(subGain2);
      subGain2.connect(gain);
      osc3.connect(subGain3);
      subGain3.connect(gain);
      gain.connect(ctx.destination);

      osc1.start(startTime);
      osc2.start(startTime);
      osc3.start(startTime);
      osc1.stop(startTime + duration + 0.04);
      osc2.stop(startTime + duration + 0.04);
      osc3.stop(startTime + duration + 0.04);
    }

    function stopPlayback() {
      STATE.isPlaying = false;
      STATE.playbackTimers.forEach(t => clearTimeout(t));
      STATE.playbackTimers = [];
      document.querySelectorAll(`[class*="note-bg-"]`).forEach(el => el.setAttribute('fill', 'transparent'));

      const btn = document.getElementById('btnPlayToggle');
      document.getElementById('playBtnText').textContent = '试听简谱';
      btn.classList.replace('bg-rose-600', 'play-glow-btn');
    }"""

new_playback_block = r"""    function togglePlayback() {
      if (STATE.isPlaying) {
        stopPlayback();
        return;
      }
      if (STATE.notes.length === 0) {
        showToast('当前没有可播放的音符', 'warning');
        return;
      }

      // 先确保停止之前的所有发声
      stopPlayback();

      STATE.isPlaying = true;
      document.getElementById('playBtnText').textContent = '停止播放';
      const btn = document.getElementById('btnPlayToggle');
      btn.classList.replace('play-glow-btn', 'bg-rose-600');

      const ctx = getAudioContext();
      
      // 创建总控主增益节点 (连接到扬声器，停止时切断它即可瞬间彻底静音)
      STATE.playbackMasterGain = ctx.createGain();
      STATE.playbackMasterGain.gain.setValueAtTime(1.0, ctx.currentTime);
      STATE.playbackMasterGain.connect(ctx.destination);
      STATE.activeOscillators = [];

      const secPerBeat = 60 / STATE.bpm;
      let currentTime = ctx.currentTime + 0.05;

      STATE.notes.forEach((note, idx) => {
        const durSec = note.duration * secPerBeat;
        const delayMs = Math.max(0, (currentTime - ctx.currentTime) * 1000);

        const timerOn = setTimeout(() => {
          document.querySelectorAll(`[class*="note-bg-"]`).forEach(el => el.setAttribute('fill', 'transparent'));
          const activeBg = document.querySelectorAll(`.note-bg-${idx}`);
          activeBg.forEach(el => {
            el.setAttribute('fill', '#fde68a');
          });
        }, delayMs);
        STATE.playbackTimers.push(timerOn);

        if (!note.isRest && note.midi > 0) {
          const freq = 440 * Math.pow(2, (note.midi - 69) / 12);
          playSynthTone(ctx, freq, currentTime, durSec * 0.92);
        }

        currentTime += durSec;
      });

      const endDelayMs = Math.max(0, (currentTime - ctx.currentTime) * 1000);
      const timerEnd = setTimeout(() => stopPlayback(), endDelayMs + 100);
      STATE.playbackTimers.push(timerEnd);
    }

    function playSynthTone(ctx, freq, startTime, duration) {
      if (!STATE.playbackMasterGain) return;

      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const osc3 = ctx.createOscillator();
      const noteGain = ctx.createGain();

      osc1.type = 'triangle';
      osc2.type = 'sine';
      osc3.type = 'sine';
      osc1.frequency.setValueAtTime(freq, startTime);
      osc2.frequency.setValueAtTime(freq * 2, startTime);
      osc3.frequency.setValueAtTime(freq * 3, startTime);

      const subGain2 = ctx.createGain();
      subGain2.gain.value = 0.28;
      const subGain3 = ctx.createGain();
      subGain3.gain.value = 0.12;

      noteGain.gain.setValueAtTime(0.001, startTime);
      noteGain.gain.exponentialRampToValueAtTime(0.35, startTime + 0.02);
      noteGain.gain.exponentialRampToValueAtTime(0.001, startTime + Math.max(0.08, duration));

      osc1.connect(noteGain);
      osc2.connect(subGain2);
      subGain2.connect(noteGain);
      osc3.connect(subGain3);
      subGain3.connect(noteGain);
      
      // 所有单音连接到总控主增益节点，而非直接接扬声器
      noteGain.connect(STATE.playbackMasterGain);

      osc1.start(startTime);
      osc2.start(startTime);
      osc3.start(startTime);
      osc1.stop(startTime + duration + 0.04);
      osc2.stop(startTime + duration + 0.04);
      osc3.stop(startTime + duration + 0.04);

      // 跟踪振荡器节点以便立即调用 stop()
      STATE.activeOscillators.push(osc1, osc2, osc3);
    }

    function stopPlayback() {
      STATE.isPlaying = false;

      // 1. 立即清除所有 UI 高亮定时器
      STATE.playbackTimers.forEach(t => clearTimeout(t));
      STATE.playbackTimers = [];

      // 2. 0毫秒切断总控音频输出流并断开连接 (保证绝对静音)
      if (STATE.playbackMasterGain && STATE.audioCtx) {
        try {
          STATE.playbackMasterGain.gain.setValueAtTime(0, STATE.audioCtx.currentTime);
          STATE.playbackMasterGain.disconnect();
        } catch (e) {}
        STATE.playbackMasterGain = null;
      }

      // 3. 立即停止所有已调度或正在振荡的硬件声源
      if (STATE.activeOscillators && STATE.activeOscillators.length > 0) {
        STATE.activeOscillators.forEach(osc => {
          try {
            osc.stop();
            osc.disconnect();
          } catch (e) {}
        });
        STATE.activeOscillators = [];
      }

      // 4. 重置高亮与按钮视觉状态
      document.querySelectorAll(`[class*="note-bg-"]`).forEach(el => el.setAttribute('fill', 'transparent'));

      const btn = document.getElementById('btnPlayToggle');
      if (btn) {
        document.getElementById('playBtnText').textContent = '试听简谱';
        btn.classList.replace('bg-rose-600', 'play-glow-btn');
      }
    }"""

content = content.replace(old_playback_block, new_playback_block)

# 3. Update Audio Preview Canvases to be larger with click-to-zoom support
old_audio_canvases = r"""            <!-- 动态波形与音高水流谱 (现代艺术全景分析) -->
            <div id="waveformContainer" class="hidden space-y-2.5 pt-1">
              <div class="flex items-center justify-between text-xs text-slate-500 px-1">
                <div class="flex items-center space-x-2">
                  <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span id="audioFileName" class="font-medium text-slate-700 truncate max-w-[180px]">音频已解析</span>
                </div>
                <span id="audioDurationLabel" class="font-mono-score text-indigo-600 font-semibold">0.0s</span>
              </div>
              
              <!-- 现代艺术波形画布 -->
              <div class="relative w-full h-20 bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 shadow-inner">
                <canvas id="waveformCanvas" class="w-full h-full block"></canvas>
                <div class="absolute top-1.5 right-2 text-[9px] font-mono text-slate-400/80 bg-slate-900/80 px-1.5 py-0.5 rounded">
                  WAVEFORM & ENVELOPE
                </div>
              </div>

              <!-- 音高提取与切分时间线 (Piano Roll 预览窗，透明呈现识别细节) -->
              <div class="relative w-full h-24 bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 shadow-inner">
                <canvas id="pitchCanvas" class="w-full h-full block"></canvas>
                <div class="absolute top-1.5 right-2 text-[9px] font-mono text-indigo-400/80 bg-slate-900/80 px-1.5 py-0.5 rounded">
                  PITCH TRACKER & NOTE SLICES
                </div>
              </div>

              <!-- 重新分析按钮 -->
              <button onclick="runAudioTranscription()" class="art-glow-btn w-full py-2.5 rounded-xl text-xs sm:text-sm font-semibold flex items-center justify-center space-x-2 cursor-pointer">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                <span>重新执行精准音高提取 & 简谱生成</span>
              </button>
            </div>"""

new_audio_canvases = r"""            <!-- 动态波形与音高水流谱 (尺寸增大 + 悬浮点击看大图) -->
            <div id="waveformContainer" class="hidden space-y-3 pt-1">
              <div class="flex items-center justify-between text-xs text-slate-500 px-1">
                <div class="flex items-center space-x-2">
                  <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span id="audioFileName" class="font-semibold text-slate-800 truncate max-w-[200px]">音频已解析</span>
                </div>
                <div class="flex items-center space-x-2">
                  <span class="text-[10px] text-indigo-600 bg-indigo-50 border border-indigo-200/80 px-2 py-0.5 rounded-full font-medium">点击图表可放大查看</span>
                  <span id="audioDurationLabel" class="font-mono-score text-indigo-600 font-bold">0.0s</span>
                </div>
              </div>
              
              <!-- 现代艺术波形画布 (高度加大至 112px，支持点击看大图) -->
              <div class="relative w-full h-28 bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 shadow-md group cursor-pointer" onclick="openPreviewModal('waveform')" title="点击放大查看全景音频波形大图">
                <canvas id="waveformCanvas" class="w-full h-full block"></canvas>
                <div class="absolute top-2 right-2 text-[10px] font-mono text-slate-400 bg-slate-900/90 border border-slate-700/80 px-2 py-0.5 rounded-md flex items-center space-x-1">
                  <span>WAVEFORM & ENVELOPE</span>
                </div>
                <!-- 悬浮提示放大遮罩 -->
                <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-[1px] opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center text-white text-xs font-semibold space-x-1.5">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"/></svg>
                  <span>点击查看音频波形大图</span>
                </div>
              </div>

              <!-- 音高提取与切分时间线 (高度加大至 160px，支持点击看大图) -->
              <div class="relative w-full h-40 bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 shadow-md group cursor-pointer" onclick="openPreviewModal('pitch')" title="点击放大查看高精音高切分水流谱大图">
                <canvas id="pitchCanvas" class="w-full h-full block"></canvas>
                <div class="absolute top-2 right-2 text-[10px] font-mono text-indigo-300 bg-slate-900/90 border border-indigo-900/80 px-2 py-0.5 rounded-md flex items-center space-x-1">
                  <span>PITCH CONTOUR & NOTE PIANO-ROLL</span>
                </div>
                <!-- 悬浮提示放大遮罩 -->
                <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-[1px] opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center text-white text-xs font-semibold space-x-1.5">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"/></svg>
                  <span>点击放大查看高精音高切分水流谱大图</span>
                </div>
              </div>

              <!-- 重新分析按钮 -->
              <button onclick="runAudioTranscription()" class="art-glow-btn w-full py-2.5 rounded-xl text-xs sm:text-sm font-semibold flex items-center justify-center space-x-2 cursor-pointer shadow-sm">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                <span>重新执行精准音高提取 & 简谱生成</span>
              </button>
            </div>"""

content = content.replace(old_audio_canvases, new_audio_canvases)

# 4. Update OMR Canvas to fix squished aspect ratio and enable click-to-zoom
old_omr_canvas_block = r"""            <!-- OMR 视觉识别定位热区 -->
            <div id="omrPreviewContainer" class="hidden space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-600">光学识谱 (OMR) 定位与标注：</span>
                <label class="inline-flex items-center text-xs text-indigo-600 font-medium cursor-pointer">
                  <input type="checkbox" id="toggleOmrOverlay" checked onchange="renderOmrCanvas()" class="rounded text-indigo-600 mr-1">
                  <span>显示五线与符头框</span>
                </label>
              </div>
              <div class="w-full max-h-48 overflow-auto bg-white rounded-xl border border-slate-200 p-2 flex justify-center shadow-inner">
                <canvas id="omrCanvas" class="max-w-full h-auto rounded"></canvas>
              </div>
              <div id="omrStatsBadge" class="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-1.5 flex items-center space-x-1.5">
                <span>✅ 已识别到五线谱组与音符</span>
              </div>
            </div>"""

new_omr_canvas_block = r"""            <!-- OMR 视觉识别定位热区 (防变形保持真实比例 + 放大至高质展示 + 支持点击看大图) -->
            <div id="omrPreviewContainer" class="hidden space-y-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-1.5">
                  <span class="text-xs font-bold text-slate-700">光学识谱 (OMR) 定位与标注：</span>
                  <span class="text-[10px] text-violet-600 bg-violet-50 border border-violet-200/80 px-2 py-0.5 rounded-full font-medium">点击可看大图</span>
                </div>
                <label class="inline-flex items-center text-xs text-indigo-600 font-semibold cursor-pointer">
                  <input type="checkbox" id="toggleOmrOverlay" checked onchange="renderOmrCanvas()" class="rounded text-indigo-600 mr-1.5">
                  <span>显示识别标注框</span>
                </label>
              </div>
              
              <!-- 容器采用自适应居中，彻底消除 CSS flex 压缩变形问题，加大高度展示 -->
              <div class="w-full min-h-[220px] max-h-[460px] overflow-auto bg-slate-900/5 rounded-2xl border border-slate-200/90 p-3 flex items-center justify-center shadow-inner relative group cursor-pointer" onclick="openPreviewModal('omr')" title="点击查看超清大图">
                <canvas id="omrCanvas" style="max-width: 100%; height: auto; object-fit: contain; display: block; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);"></canvas>
                
                <!-- 悬浮放大提示层 -->
                <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-[1px] opacity-0 group-hover:opacity-100 transition-opacity duration-200 rounded-2xl flex items-center justify-center text-white text-xs font-semibold space-x-1.5">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"/></svg>
                  <span>点击放大查看五线谱超清大图与标注</span>
                </div>
              </div>
              <div id="omrStatsBadge" class="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-1.5 flex items-center space-x-1.5">
                <span>✅ 已识别到五线谱组与音符</span>
              </div>
            </div>"""

content = content.replace(old_omr_canvas_block, new_omr_canvas_block)

# 5. Add Ultra-Sleek High-Res Preview Lightbox Modal
lightbox_html = r"""  <!-- 超清大图与分析全景查看器 (Lightbox Modal) -->
  <div id="previewModal" class="fixed inset-0 bg-slate-950/75 backdrop-blur-md z-50 hidden items-center justify-center p-3 sm:p-6 transition-all duration-300">
    <div class="art-glass bg-slate-900/95 border border-white/20 rounded-3xl max-w-5xl w-full max-h-[92vh] flex flex-col shadow-2xl overflow-hidden text-slate-100">
      
      <!-- 模态框顶部工具条 -->
      <div class="px-5 py-3.5 border-b border-slate-700/80 flex items-center justify-between bg-slate-900/80">
        <div class="flex items-center space-x-3">
          <span id="previewModalBadge" class="text-[11px] font-bold px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">
            FULLVIEW
          </span>
          <h3 id="previewModalTitle" class="text-sm sm:text-base font-bold text-white tracking-tight">
            全景超清分析预览
          </h3>
        </div>

        <!-- 缩放与操作按钮 -->
        <div class="flex items-center space-x-2">
          <button onclick="zoomPreview(0.2)" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition cursor-pointer" title="放大">
            🔍+
          </button>
          <button onclick="zoomPreview(-0.2)" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition cursor-pointer" title="缩小">
            🔍-
          </button>
          <button onclick="resetPreviewZoom()" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition cursor-pointer" title="重置大小">
            100%
          </button>
          <button onclick="downloadPreviewImage()" class="px-2.5 py-1 text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition cursor-pointer flex items-center space-x-1" title="下载大图">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            <span class="hidden sm:inline">保存图片</span>
          </button>
          <button onclick="closePreviewModal()" class="w-8 h-8 rounded-full bg-slate-800 hover:bg-rose-600 text-slate-400 hover:text-white flex items-center justify-center transition cursor-pointer text-base font-bold ml-2">
            &times;
          </button>
        </div>
      </div>

      <!-- 模态框超清内容显示区 (支持滚轮与拖动平移) -->
      <div id="previewModalContent" class="flex-1 overflow-auto p-4 flex items-center justify-center bg-slate-950/80 min-h-[360px] relative select-none">
        <canvas id="modalCanvas" style="max-width: 100%; height: auto; transition: transform 0.2s ease; transform-origin: center center; display: block; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);"></canvas>
      </div>

      <!-- 底部快捷提示条 -->
      <div class="px-5 py-2.5 bg-slate-900 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
        <span>按 ESC 键或点击右上角关闭 · 支持点击上方按钮无损缩放</span>
        <span id="previewModalMeta" class="font-mono text-slate-500">100% 原始解析度</span>
      </div>

    </div>
  </div>
"""

# Insert lightbox modal right above footer
content = content.replace('  <!-- 艺术页脚 -->', lightbox_html + '\n  <!-- 艺术页脚 -->')

# 6. Add JS functions for Lightbox Modal
lightbox_js = r"""    /**
     * ============================================================================
     * 11. 超清大图查看器 (Lightbox Modal) 交互逻辑
     * ============================================================================
     */
    function openPreviewModal(type) {
      STATE.currentPreviewType = type;
      STATE.previewZoom = 1.0;
      const modal = document.getElementById('previewModal');
      const titleEl = document.getElementById('previewModalTitle');
      const badgeEl = document.getElementById('previewModalBadge');
      const modalCanvas = document.getElementById('modalCanvas');
      modalCanvas.style.transform = 'scale(1)';

      let sourceCanvas = null;
      if (type === 'waveform') {
        sourceCanvas = document.getElementById('waveformCanvas');
        titleEl.textContent = '全景高精度音频波形与能量包络大图';
        badgeEl.textContent = 'AUDIO WAVEFORM';
      } else if (type === 'pitch') {
        sourceCanvas = document.getElementById('pitchCanvas');
        titleEl.textContent = '全曲音高提取连续轨迹与简谱音符分段 (Piano Roll)';
        badgeEl.textContent = 'PITCH WATERFALL';
      } else if (type === 'omr') {
        sourceCanvas = document.getElementById('omrCanvas');
        titleEl.textContent = '五线谱光学识谱 (OMR) 谱线与符头定位大图';
        badgeEl.textContent = 'SHEET OMR OVERLAY';
      }

      if (!sourceCanvas) return;

      modalCanvas.width = sourceCanvas.width;
      modalCanvas.height = sourceCanvas.height;
      const mctx = modalCanvas.getContext('2d');
      mctx.drawImage(sourceCanvas, 0, 0);

      document.getElementById('previewModalMeta').textContent = `${sourceCanvas.width} × ${sourceCanvas.height} px · 缩放率: 100%`;
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }

    function closePreviewModal() {
      const modal = document.getElementById('previewModal');
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      STATE.currentPreviewType = null;
    }

    function zoomPreview(delta) {
      STATE.previewZoom = Math.max(0.4, Math.min(3.5, STATE.previewZoom + delta));
      const modalCanvas = document.getElementById('modalCanvas');
      modalCanvas.style.transform = `scale(${STATE.previewZoom})`;
      document.getElementById('previewModalMeta').textContent = `缩放率: ${Math.round(STATE.previewZoom * 100)}%`;
    }

    function resetPreviewZoom() {
      STATE.previewZoom = 1.0;
      const modalCanvas = document.getElementById('modalCanvas');
      modalCanvas.style.transform = 'scale(1)';
      document.getElementById('previewModalMeta').textContent = '缩放率: 100%';
    }

    function downloadPreviewImage() {
      const modalCanvas = document.getElementById('modalCanvas');
      const link = document.createElement('a');
      link.download = `${STATE.currentPreviewType || 'analysis'}_超清分析图.png`;
      link.href = modalCanvas.toDataURL('image/png');
      link.click();
      showToast('超清分析大图已下载！', 'success');
    }

    // 监听键盘 ESC 键关闭大图查看器
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closePreviewModal();
        closeHelpModal();
      }
    });"""

content = content.replace("    // 页面初始化完成加载", lightbox_js + "\n\n    // 页面初始化完成加载")

with open('/Users/oneriver/Downloads/jianpu_studio.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Comprehensive updates applied successfully!")
