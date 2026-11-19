# -*- coding: utf-8 -*-
with open('/Users/oneriver/Downloads/jianpu_studio.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update detectPitchYIN to compute tau up to maxTau + 1 and step by 2
new_detectPitchYIN = r'''    function detectPitchYIN(buffer, sampleRate) {
      const threshold = 0.12;
      const halfLen = Math.floor(buffer.length / 2);
      const minTau = Math.max(2, Math.floor(sampleRate / 1000));  // 最高 ~B5 (1000Hz)
      const maxTau = Math.min(halfLen - 2, Math.floor(sampleRate / 70)); // 最低 ~D2 (70Hz)
      const yinBuffer = new Float32Array(maxTau + 2);

      // 1. 平方差函数 (仅计算有效 tau 范围，并采用步长2加速计算)
      for (let tau = 0; tau <= maxTau + 1; tau++) {
        let sum = 0;
        for (let i = 0; i < halfLen; i += 2) {
          const delta = buffer[i] - buffer[i + tau];
          sum += delta * delta;
        }
        yinBuffer[tau] = sum * 2;
      }

      // 2. 累积均值归一化差 (CMNDF)
      yinBuffer[0] = 1;
      let runningSum = 0;
      for (let tau = 1; tau <= maxTau + 1; tau++) {
        runningSum += yinBuffer[tau];
        yinBuffer[tau] *= tau / (runningSum || 1);
      }

      // 3. 寻找低于阈值的局部极小值
      let tauEstimate = -1;
      let globalMinTau = -1;
      let globalMinVal = Infinity;

      for (let tau = minTau; tau <= maxTau; tau++) {
        if (yinBuffer[tau] < globalMinVal && 
            (tau === minTau || yinBuffer[tau] <= yinBuffer[tau - 1]) && 
            (tau === maxTau || yinBuffer[tau] <= yinBuffer[tau + 1])) {
          globalMinVal = yinBuffer[tau];
          globalMinTau = tau;
        }

        if (yinBuffer[tau] < threshold) {
          while (tau + 1 <= maxTau && yinBuffer[tau + 1] < yinBuffer[tau]) {
            tau++;
          }
          tauEstimate = tau;
          break;
        }
      }

      // 若未达到极严阈值，但在可信谷底范围 (<0.32)，允许作为候选音高
      if (tauEstimate === -1 && globalMinVal < 0.32) {
        tauEstimate = globalMinTau;
      }

      if (tauEstimate === -1) return { freq: -1, clarity: 0 };

      // 4. 抛物线高精度插值
      let betterTau = tauEstimate;
      if (tauEstimate > 0 && tauEstimate < maxTau) {
        const s0 = yinBuffer[tauEstimate - 1];
        const s1 = yinBuffer[tauEstimate];
        const s2 = yinBuffer[tauEstimate + 1];
        const denom = 2 * (2 * s1 - s2 - s0);
        if (denom !== 0) {
          betterTau = tauEstimate + (s2 - s0) / denom;
        }
      }

      const freq = sampleRate / betterTau;
      const clarity = Math.max(0, Math.min(1, 1 - (yinBuffer[tauEstimate] || 0)));
      return { freq, clarity };
    }'''

# 2. Update runAudioTranscription to process FULL AUDIO (no 45s cutoff!) with async progress
new_runAudioTranscription = r'''    async function runAudioTranscription() {
      const audioBuffer = STATE.currentAudioBuffer;
      if (!audioBuffer) return;

      const sampleRate = audioBuffer.sampleRate;
      const channelData = audioBuffer.getChannelData(0);

      // 支持解析完整音频时长（无截断，最大支持 10 分钟）
      const maxSamples = Math.min(channelData.length, sampleRate * 600);
      const totalDurationSec = (maxSamples / sampleRate).toFixed(1);
      const frameSize = 2048;
      const hopSize = 512; // ~11.6ms，高时间分辨率兼具高速分析
      const frames = [];

      const statusEl = document.getElementById('engineStatusIndicator');
      if (statusEl) statusEl.textContent = `全曲分析中 (0/${Math.round(totalDurationSec)}s)...`;

      // 全局平均能量计算 (采用步长采样优化)
      let totalRms = 0;
      let frameCount = 0;
      for (let i = 0; i + frameSize < maxSamples; i += hopSize * 2) {
        let sumSq = 0;
        for (let j = 0; j < frameSize; j += 2) sumSq += channelData[i + j] * channelData[i + j];
        totalRms += Math.sqrt((sumSq * 2) / frameSize);
        frameCount++;
      }
      const avgRms = totalRms / (frameCount || 1);
      const silenceThreshold = Math.max(0.005, avgRms * 0.16);

      const onsetSensVal = document.getElementById('selectOnsetSens').value;
      const onsetFactor = onsetSensVal === 'high' ? 1.18 : (onsetSensVal === 'low' ? 1.42 : 1.28);

      // 1. 逐帧异步提取音高、能量与可信度 (带进度反馈与防卡死出让)
      let prevRms = 0;
      const onsetTimes = [];
      let processedCount = 0;

      for (let i = 0; i + frameSize < maxSamples; i += hopSize) {
        const slice = channelData.subarray(i, i + frameSize);
        let sumSq = 0;
        for (let j = 0; j < frameSize; j += 2) sumSq += slice[j] * slice[j];
        const rms = Math.sqrt((sumSq * 2) / frameSize);
        const time = i / sampleRate;

        // 检测起音 (能量骤升即新音符触发)
        let isOnset = false;
        if (rms > silenceThreshold && rms > prevRms * onsetFactor && prevRms > 0.001) {
          isOnset = true;
          onsetTimes.push(time);
        }
        prevRms = rms;

        if (rms < silenceThreshold) {
          frames.push({ midi: -1, rawMidi: -1, time, clarity: 0, isOnset });
        } else {
          const { freq, clarity } = detectPitchYIN(slice, sampleRate);
          if (freq > 70 && freq < 1000 && clarity > 0.45) {
            const rawMidi = 69 + 12 * Math.log2(freq / 440);
            const snappedMidi = snapPitchToScale(rawMidi, STATE.key, STATE.scaleMode);
            frames.push({ midi: snappedMidi, rawMidi, time, clarity, isOnset });
          } else {
            frames.push({ midi: -1, rawMidi: -1, time, clarity: 0, isOnset });
          }
        }

        processedCount++;
        // 每 400 帧出让一次控制权，避免长时间任务卡顿主线程并实时更新进度
        if (processedCount % 400 === 0) {
          const curSec = Math.round(time);
          const pct = Math.round((time / (maxSamples / sampleRate)) * 100);
          if (statusEl) statusEl.textContent = `全曲识别中 ${pct}% (${curSec}s/${Math.round(totalDurationSec)}s)...`;
          await new Promise(resolve => setTimeout(resolve, 0));
        }
      }

      if (statusEl) statusEl.textContent = 'AI 音律分析引擎已就绪';

      // 2. 7-frame 窗口中值滤波 (消除瞬时偶发毛刺)
      const smoothed = frames.map((f, idx) => {
        if (idx < 3 || idx >= frames.length - 3) return { ...f };
        const window = [
          frames[idx - 3].midi, frames[idx - 2].midi, frames[idx - 1].midi,
          f.midi,
          frames[idx + 1].midi, frames[idx + 2].midi, frames[idx + 3].midi
        ].sort((a, b) => a - b);
        return { ...f, midi: window[3] };
      });

      // 3. 八度跳变自相关纠错 (Octave-error repair pass)
      for (let i = 1; i < smoothed.length - 1; i++) {
        const prev = smoothed[i - 1].midi;
        const curr = smoothed[i].midi;
        const next = smoothed[i + 1].midi;
        if (prev > 0 && curr > 0 && next > 0) {
          if (Math.abs(curr - prev) >= 11 && Math.abs(curr - prev) <= 13 && Math.abs(prev - next) <= 3) {
            smoothed[i].midi = prev;
          }
        }
      }

      // 4. 短暂静音空洞填补 (Gap-bridging: <60ms 的短暂微停顿合并为持续音)
      for (let i = 1; i < smoothed.length - 1; i++) {
        if (smoothed[i].midi === -1 && smoothed[i - 1].midi > 0 && smoothed[i + 1].midi === smoothed[i - 1].midi) {
          smoothed[i].midi = smoothed[i - 1].midi;
        }
      }

      // 5. 音符分段 (结合起音 Onset 与音高变化)
      const rawEvents = [];
      const frameDur = hopSize / sampleRate;

      for (let idx = 0; idx < smoothed.length; idx++) {
        const f = smoothed[idx];
        if (rawEvents.length === 0) {
          rawEvents.push({ midi: f.midi, durSec: frameDur });
        } else {
          const last = rawEvents[rawEvents.length - 1];
          if (last.midi === f.midi && !f.isOnset) {
            last.durSec += frameDur;
          } else if (last.midi === f.midi && f.isOnset && last.durSec >= 0.18) {
            rawEvents.push({ midi: f.midi, durSec: frameDur });
          } else {
            rawEvents.push({ midi: f.midi, durSec: frameDur });
          }
        }
      }

      // 6. 过滤超短杂音 (< 75ms) 并精准量化到节拍网格
      const secPerBeat = 60 / STATE.bpm;
      const quantizedNotes = [];

      for (const ev of rawEvents) {
        if (ev.durSec < 0.075) continue;
        let beats = ev.durSec / secPerBeat;
        beats = Math.max(STATE.quantGrid, Math.round(beats / STATE.quantGrid) * STATE.quantGrid);
        beats = Math.min(4, beats);

        if (ev.midi === -1) {
          if (quantizedNotes.length > 0 && beats >= 0.5) {
            quantizedNotes.push({ midi: 0, duration: beats, isRest: true });
          }
        } else {
          quantizedNotes.push({ midi: ev.midi, duration: beats, isRest: false });
        }
      }

      while (quantizedNotes.length > 0 && quantizedNotes[quantizedNotes.length - 1].isRest) {
        quantizedNotes.pop();
      }

      if (quantizedNotes.length === 0) {
        showToast('未能捕捉到清晰的单音旋律，请贴近麦克风或点击内置示例测试', 'warning');
        return;
      }

      STATE.notes = quantizedNotes;

      // 存储用于 Piano Roll 可视化绘制的完整全曲数据
      STATE.pitchContourData = {
        frames: smoothed,
        onsets: onsetTimes,
        notes: quantizedNotes,
        duration: maxSamples / sampleRate
      };
      drawPitchContourCanvas();

      if (document.getElementById('selectKey').value === 'AUTO') {
        STATE.key = detectBestKey(STATE.notes);
      }

      updateHeaderLabels();
      renderJianpuScore();
      syncRawTextFromNotes();
      showToast(`全曲识别完成！共解析 ${STATE.notes.length} 个音符 (${totalDurationSec}s，调性: 1=${STATE.key})`, 'success');
    }'''

import re

# Replace detectPitchYIN
content = re.sub(r'function detectPitchYIN[\s\S]*?\n    \}', new_detectPitchYIN.strip(), content, count=1)

# Replace runAudioTranscription
content = re.sub(r'function runAudioTranscription\(\)[\s\S]*?\n      showToast\(`识别完成！生成[\s\S]*?\n    \}', new_runAudioTranscription.strip(), content, count=1)

with open('/Users/oneriver/Downloads/jianpu_studio.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated /Users/oneriver/Downloads/jianpu_studio.html successfully!")
