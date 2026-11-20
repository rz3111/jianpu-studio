# -*- coding: utf-8 -*-
"""
Patch index.html and jianpu_studio.html with comprehensive upgrades:
Part 1: Multi-candidate YIN + Viterbi pitch tracking + Multi-feature Onsets + Beat Grid Quantization + Confidence
Part 2: OMR Symbol Classification (Clef, KeySig, TimeSig, Barline, Stem, Beam, Notehead) + Header Detection +
        Geometric Notehead Scoring + Beam/Clef separation + Per-staff Clef + Layered Duration + Memory Optimization
"""

import sys

def patch_file(filepath):
    print(f"Patching {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # =========================================================================
    # 1. Replace detectPitchYIN with detectPitchYINCandidates + Viterbi + detectPitchYIN
    # =========================================================================
    yin_start_marker = "    function detectPitchYIN(buffer, sampleRate, prevMidi = -1) {"
    if yin_start_marker not in content:
        print(f"Error: Could not find '{yin_start_marker}' in {filepath}")
        return False

    # Find start of snapPitchToScale
    snap_marker = "    function snapPitchToScale(rawMidi, key, mode = 'major') {"
    if snap_marker not in content:
        print(f"Error: Could not find '{snap_marker}' in {filepath}")
        return False

    yin_block = """    /**
     * 高精度多候选音高检测算法 (Multi-Candidate YIN + Parabolic Interpolation)
     * 每帧保留 3~5 个候选音高，为后续全局动态规划/Viterbi 算法提供充分的候选状态空间
     */
    function detectPitchYINCandidates(buffer, sampleRate, energy = 0.1) {
      const halfLen = Math.floor(buffer.length / 2);
      const minTau = Math.max(2, Math.floor(sampleRate / 1050)); // ~C6 (1046Hz)
      const maxTau = Math.min(halfLen - 2, Math.floor(sampleRate / 68));  // ~C2 (65Hz)
      const yinBuffer = new Float32Array(maxTau + 2);

      // 1. 平方差函数 (步长为 2 采样，降低 50% 计算量，避免 O(N^2) 耗时)
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

      // 3. 多候选局部谷底检索
      const candidates = [];
      for (let tau = minTau; tau <= maxTau; tau++) {
        if (yinBuffer[tau] < 0.65 && 
            (tau === minTau || yinBuffer[tau] <= yinBuffer[tau - 1]) && 
            (tau === maxTau || yinBuffer[tau] <= yinBuffer[tau + 1])) {
          
          let betterTau = tau;
          if (tau > minTau && tau < maxTau) {
            const s0 = yinBuffer[tau - 1];
            const s1 = yinBuffer[tau];
            const s2 = yinBuffer[tau + 1];
            const denom = 2 * (2 * s1 - s2 - s0);
            if (denom !== 0) {
              betterTau = tau + (s2 - s0) / denom;
            }
          }
          const freq = sampleRate / betterTau;
          const midi = 69 + 12 * Math.log2(freq / 440);
          const cmndf = Math.max(0, Math.min(1, yinBuffer[tau]));
          const clarity = Math.max(0, Math.min(1, 1 - cmndf));
          candidates.push({ tau: betterTau, freq, midi, cmndf, clarity, energy });
        }
      }

      // 补充可能的高八度 / 次谐波候选
      if (candidates.length > 0) {
        const bestTau = candidates[0].tau;
        const halfTau = Math.round(bestTau / 2);
        if (halfTau >= minTau && halfTau <= maxTau) {
          const fHalf = sampleRate / halfTau;
          candidates.push({
            tau: halfTau,
            freq: fHalf,
            midi: 69 + 12 * Math.log2(fHalf / 440),
            cmndf: yinBuffer[halfTau] || 0.5,
            clarity: Math.max(0, 1 - (yinBuffer[halfTau] || 0.5)),
            energy
          });
        }
      }

      candidates.sort((a, b) => a.cmndf - b.cmndf);
      return candidates.slice(0, 5);
    }

    /**
     * 单帧兼容版本 (供即时试听与回退使用)
     */
    function detectPitchYIN(buffer, sampleRate, prevMidi = -1) {
      let sumSq = 0;
      for (let j = 0; j < buffer.length; j += 2) sumSq += buffer[j] * buffer[j];
      const energy = Math.sqrt((sumSq * 2) / buffer.length);
      const candidates = detectPitchYINCandidates(buffer, sampleRate, energy);
      if (candidates.length === 0) return { freq: -1, clarity: 0, rawMidi: -1, candidates: [] };

      let best = candidates[0];
      if (prevMidi > 0) {
        for (const cand of candidates) {
          if (Math.abs(cand.midi - prevMidi) <= 2.2 && cand.cmndf < 0.35) {
            best = cand;
            break;
          }
        }
      }
      return { freq: best.freq, clarity: best.clarity, rawMidi: best.midi, candidates };
    }

    /**
     * 全局动态规划 / Viterbi 音高路径追踪器
     * 解决八度跳跃、瞬时锁死、发声/静音切换等全局最优化问题
     */
    function viterbiPitchTracking(framesData, silenceThreshold = 0.01) {
      const T = framesData.length;
      if (T === 0) return [];

      const dp = [];
      const bp = [];

      for (let t = 0; t < T; t++) {
        const frame = framesData[t];
        const cands = frame.candidates || [];
        const numStates = 1 + cands.length; // State 0 is unvoiced (-1)
        dp[t] = new Float32Array(numStates);
        bp[t] = new Int32Array(numStates);

        const energy = frame.energy || 0;
        const isSilent = energy < silenceThreshold;

        for (let s = 0; s < numStates; s++) {
          // 发射代价
          let emissionCost = 0;
          if (s === 0) {
            emissionCost = isSilent ? (energy / silenceThreshold) * 0.15 : 2.6 + (energy / silenceThreshold) * 1.5;
          } else {
            const cand = cands[s - 1];
            emissionCost = (1 - cand.clarity) * 1.8 + cand.cmndf * 1.2;
            if (isSilent) emissionCost += 3.5;
          }

          if (t === 0) {
            dp[t][s] = emissionCost;
          } else {
            const prevCands = framesData[t - 1].candidates || [];
            const prevStates = 1 + prevCands.length;
            let minTotalCost = Infinity;
            let bestPrevState = 0;

            for (let p = 0; p < prevStates; p++) {
              let transCost = 0;
              if (p === 0 && s === 0) {
                transCost = 0;
              } else if (p === 0 || s === 0) {
                transCost = 1.15; // 静音/有声切换惩罚
              } else {
                const prevCand = prevCands[p - 1];
                const currCand = cands[s - 1];
                const deltaMidi = Math.abs(currCand.midi - prevCand.midi);

                // 平滑过渡代价
                transCost = deltaMidi * 0.12;

                // 八度跳变惩罚 (抑制谐波共振峰引起的虚假八度)
                if (Math.abs(deltaMidi - 12) < 1.2 || Math.abs(deltaMidi - 24) < 1.2) {
                  transCost += 2.8;
                } else if (deltaMidi > 12) {
                  // 超过 12 半音连续跳跃增加惩罚，但不绝对禁止
                  transCost += (deltaMidi - 12) * 0.35;
                } else if (deltaMidi <= 0.8) {
                  // 颤音正常波动极低代价
                  transCost = deltaMidi * 0.02;
                }
              }

              const totalCost = dp[t - 1][p] + transCost;
              if (totalCost < minTotalCost) {
                minTotalCost = totalCost;
                bestPrevState = p;
              }
            }

            dp[t][s] = minTotalCost + emissionCost;
            bp[t][s] = bestPrevState;
          }
        }
      }

      // 回溯最佳全局路径
      let bestFinalState = 0;
      let minFinalCost = Infinity;
      for (let s = 0; s < dp[T - 1].length; s++) {
        if (dp[T - 1][s] < minFinalCost) {
          minFinalCost = dp[T - 1][s];
          bestFinalState = s;
        }
      }

      const path = new Array(T);
      let curState = bestFinalState;
      for (let t = T - 1; t >= 0; t--) {
        if (curState === 0) {
          path[t] = { midi: -1, rawMidi: -1, freq: -1, clarity: 0 };
        } else {
          const cand = framesData[t].candidates[curState - 1];
          path[t] = {
            midi: Math.round(cand.midi),
            rawMidi: cand.midi,
            freq: cand.freq,
            clarity: cand.clarity
          };
        }
        curState = bp[t][curState];
      }
      return path;
    }\n\n"""

    p1 = content.find(yin_start_marker)
    p2 = content.find(snap_marker)
    content = content[:p1] + yin_block + content[p2:]

    # =========================================================================
    # 2. Replace runAudioTranscription with new multi-feature onsets + viterbi + beat grid
    # =========================================================================
    trans_start_marker = "    async function runAudioTranscription() {"
    draw_pitch_marker = "    // 绘制现代艺术音高与音符时序画布 (Piano Roll)"
    
    p_trans1 = content.find(trans_start_marker)
    p_trans2 = content.find(draw_pitch_marker)
    if p_trans1 == -1 or p_trans2 == -1:
        print(f"Error: Could not find runAudioTranscription bounds in {filepath}")
        return False

    trans_block = """    async function runAudioTranscription() {
      const audioBuffer = STATE.currentAudioBuffer;
      if (!audioBuffer) return;
      const runId = ++STATE.analysisRunId;

      const sampleRate = audioBuffer.sampleRate;
      // 立体声统一混音为单声道
      const left = audioBuffer.getChannelData(0);
      const right = audioBuffer.numberOfChannels > 1 ? audioBuffer.getChannelData(1) : null;
      const channelData = right
        ? Float32Array.from(left, (v, i) => (v + right[i]) * 0.5)
        : left;

      // 支持解析完整音频时长（无截断，最大支持 10 分钟）
      const maxSamples = Math.min(channelData.length, sampleRate * 600);
      const totalDurationSec = (maxSamples / sampleRate).toFixed(1);
      const frameSize = 2048;
      const hopSize = 512; // ~11.6ms，高时间分辨率兼具高速分析

      const statusEl = document.getElementById('engineStatusIndicator');
      if (statusEl) statusEl.textContent = `全曲分析中 (0/${Math.round(totalDurationSec)}s)...`;

      // 1. 前置滤波预处理 (Pre-emphasis 预加重高通滤波，消除低频喷麦底噪与麦克风直流偏置)
      const filteredData = new Float32Array(maxSamples);
      filteredData[0] = channelData[0];
      for (let i = 1; i < maxSamples; i++) {
        filteredData[i] = channelData[i] - 0.95 * channelData[i - 1];
      }

      // 2. 自适应噪声门限与分位底噪测算 (借鉴 Spotify Basic Pitch 噪声能量门控)
      const frameEnergies = [];
      for (let i = 0; i + frameSize < maxSamples; i += hopSize * 2) {
        let sumSq = 0;
        for (let j = 0; j < frameSize; j += 2) sumSq += channelData[i + j] * channelData[i + j];
        frameEnergies.push(Math.sqrt((sumSq * 2) / frameSize));
      }
      frameEnergies.sort((a, b) => a - b);
      const noiseFloor = frameEnergies[Math.floor(frameEnergies.length * 0.15)] || 0.002;
      const medianEnergy = frameEnergies[Math.floor(frameEnergies.length * 0.5)] || 0.02;
      const silenceThreshold = Math.max(0.006, noiseFloor * 2.6, medianEnergy * 0.14);

      const onsetSensVal = document.getElementById('selectOnsetSens')?.value || 'medium';
      const onsetFactor = onsetSensVal === 'high' ? 1.18 : (onsetSensVal === 'low' ? 1.42 : 1.28);

      // 3. 逐帧异步提取多候选音高、能量与复合起音特征
      let prevRms = 0;
      let prevHfRms = 0;
      let lastOnsetTime = -1;
      let lastProgressUpdate = Date.now();
      const rawFrames = [];

      for (let i = 0; i + frameSize < maxSamples; i += hopSize) {
        if (runId !== STATE.analysisRunId) return;

        const slice = channelData.subarray(i, i + frameSize);
        const filtSlice = filteredData.subarray(i, i + frameSize);
        let sumSq = 0;
        let filtSumSq = 0;
        for (let j = 0; j < frameSize; j += 2) {
          sumSq += slice[j] * slice[j];
          filtSumSq += filtSlice[j] * filtSlice[j];
        }
        const rms = Math.sqrt((sumSq * 2) / frameSize);
        const hfRms = Math.sqrt((filtSumSq * 2) / frameSize);
        const time = i / sampleRate;

        // 提取每帧 3~5 个候选音高
        const candidates = rms >= silenceThreshold ? detectPitchYINCandidates(filtSlice, sampleRate, rms) : [];

        // 复合起音特征：能量骤升 + 频谱高频通量 (Spectral Flux)
        const energyDelta = Math.max(0, rms - prevRms);
        const hfDelta = Math.max(0, hfRms - prevHfRms);
        const isEnergyOnset = rms > silenceThreshold && rms > prevRms * onsetFactor && prevRms > 0.001;
        const isFluxOnset = hfRms > prevHfRms * (onsetFactor * 1.08) && rms > silenceThreshold * 1.2;
        
        // 起音冷却保护 (至少 80ms)
        const cooldownOk = (time - lastOnsetTime) >= 0.08;
        const candidateOnset = cooldownOk && (isEnergyOnset || isFluxOnset);

        rawFrames.push({
          time,
          rms,
          energy: rms,
          hfRms,
          energyDelta,
          hfDelta,
          candidateOnset,
          candidates
        });

        prevRms = rms;
        prevHfRms = hfRms;

        // 节流进度刷新 (每 120ms 一次，避免高频 DOM 回流与卡顿)
        const now = Date.now();
        if (now - lastProgressUpdate >= 120) {
          lastProgressUpdate = now;
          const curSec = Math.round(time);
          const pct = Math.round((time / (maxSamples / sampleRate)) * 100);
          if (statusEl) statusEl.textContent = `全曲识别中 ${pct}% (${curSec}s/${Math.round(totalDurationSec)}s)...`;
          await new Promise(resolve => setTimeout(resolve, 0));
        }
      }

      if (statusEl) statusEl.textContent = 'AI 音律分析引擎已就绪';

      // 4. 全局动态规划 / Viterbi 最优音高路径解码
      const decodedPath = viterbiPitchTracking(rawFrames, silenceThreshold);

      // 5. 2~3 帧确认与音高突变起音加固 (过滤辅音、呼吸声与瞬时爆破杂音)
      const onsetTimes = [];
      const confirmedFrames = [];

      for (let idx = 0; idx < rawFrames.length; idx++) {
        const rf = rawFrames[idx];
        const dec = decodedPath[idx];
        let isOnset = false;

        if (rf.candidateOnset) {
          // 连续 2~3 帧持续发声确认
          const hasSustain = (idx + 1 < rawFrames.length && rawFrames[idx + 1].rms >= silenceThreshold * 0.8) &&
                             (idx + 2 < rawFrames.length && rawFrames[idx + 2].rms >= silenceThreshold * 0.7);
          if (hasSustain) {
            isOnset = true;
            lastOnsetTime = rf.time;
            onsetTimes.push(rf.time);
          }
        }

        // 音高突变触发起音 (跨度 >= 1.75 个半音，即使连音也能精准拆解为新音符)
        if (!isOnset && idx > 0 && dec.midi > 0 && decodedPath[idx - 1].midi > 0) {
          const pitchDiff = Math.abs(dec.midi - decodedPath[idx - 1].midi);
          if (pitchDiff >= 1.75 && (rf.time - lastOnsetTime) >= 0.08) {
            isOnset = true;
            lastOnsetTime = rf.time;
            onsetTimes.push(rf.time);
          }
        }

        confirmedFrames.push({
          time: rf.time,
          midi: dec.midi,
          rawMidi: dec.rawMidi,
          clarity: dec.clarity,
          isOnset
        });
      }

      // 6. 音高平滑 (静音帧 -1 绝不参与中值滤波，有声/无声状态独立维护)
      const smoothed = confirmedFrames.map((f, idx) => {
        if (f.midi <= 0 || idx < 2 || idx >= confirmedFrames.length - 2) return { ...f };
        const window = [
          confirmedFrames[idx - 2].midi,
          confirmedFrames[idx - 1].midi,
          f.midi,
          confirmedFrames[idx + 1].midi,
          confirmedFrames[idx + 2].midi
        ].filter(m => m > 0).sort((a, b) => a - b);
        if (window.length < 3) return { ...f };
        return { ...f, midi: window[Math.floor(window.length / 2)] };
      });

      // 短暂微小静音填补 (限制 <= 3 帧约 35ms，且前后音高一致；前后音不同则不合并)
      for (let i = 1; i < smoothed.length - 1; i++) {
        if (smoothed[i].midi === -1 && smoothed[i - 1].midi > 0 && smoothed[i + 1].midi > 0) {
          if (Math.abs(smoothed[i - 1].midi - smoothed[i + 1].midi) <= 0.8) {
            smoothed[i].midi = smoothed[i - 1].midi;
            smoothed[i].rawMidi = smoothed[i - 1].rawMidi;
            smoothed[i].clarity = (smoothed[i - 1].clarity + smoothed[i + 1].clarity) * 0.5;
          }
        }
      }

      // 7. 统一节拍网格量化 (Beat Grid Quantization)
      // 估计 BPM: 从相邻起音间隔 IOI 测算
      if (onsetTimes.length >= 4 && document.getElementById('selectKey')?.value === 'AUTO') {
        const iois = [];
        for (let i = 1; i < onsetTimes.length; i++) {
          const dt = onsetTimes[i] - onsetTimes[i - 1];
          if (dt >= 0.18 && dt <= 1.8) iois.push(dt);
        }
        if (iois.length >= 3) {
          iois.sort((a, b) => a - b);
          const medianIoi = iois[Math.floor(iois.length / 2)];
          let estBpm = Math.round(60 / medianIoi);
          while (estBpm < 68) estBpm *= 2;
          while (estBpm > 165) estBpm = Math.round(estBpm / 2);
          if (estBpm >= 60 && estBpm <= 180) {
            STATE.bpm = estBpm;
            const bpmInput = document.getElementById('inputBpm');
            if (bpmInput) bpmInput.value = estBpm;
          }
        }
      }

      const secPerBeat = 60 / STATE.bpm;
      const gridStepSec = secPerBeat * STATE.quantGrid;

      // 提取音符段 (以 Onset 和发声/静音切换为界)
      const segments = [];
      let curSeg = null;

      for (let i = 0; i < smoothed.length; i++) {
        const f = smoothed[i];
        if (!curSeg) {
          curSeg = {
            midi: f.midi,
            rawMidi: f.rawMidi,
            startTime: f.time,
            endTime: f.time + (hopSize / sampleRate),
            clarities: [f.clarity],
            hasOnset: f.isOnset
          };
        } else {
          const isSameState = (curSeg.midi === -1 && f.midi === -1) ||
                              (curSeg.midi > 0 && f.midi > 0 && Math.abs(curSeg.midi - f.midi) <= 1 && !f.isOnset);
          if (isSameState) {
            curSeg.endTime = f.time + (hopSize / sampleRate);
            curSeg.clarities.push(f.clarity);
          } else {
            segments.push(curSeg);
            curSeg = {
              midi: f.midi,
              rawMidi: f.rawMidi,
              startTime: f.time,
              endTime: f.time + (hopSize / sampleRate),
              clarities: [f.clarity],
              hasOnset: f.isOnset
            };
          }
        }
      }
      if (curSeg) segments.push(curSeg);

      // 量化到绝对节拍网格，消除累积时值漂移
      const quantizedNotes = [];
      let lastEndTick = 0;

      for (const seg of segments) {
        const dur = seg.endTime - seg.startTime;
        if (dur < 0.06) continue;

        const startTick = Math.round(seg.startTime / gridStepSec);
        const endTick = Math.max(startTick + 1, Math.round(seg.endTime / gridStepSec));
        const durationBeats = (endTick - startTick) * STATE.quantGrid;

        // 自动补齐节拍间隙休止符
        if (quantizedNotes.length > 0 && startTick > lastEndTick) {
          const restBeats = (startTick - lastEndTick) * STATE.quantGrid;
          if (restBeats >= STATE.quantGrid) {
            quantizedNotes.push({
              midi: 0,
              duration: restBeats,
              isRest: true,
              confidence: 0.95,
              startTime: lastEndTick * gridStepSec,
              endTime: startTick * gridStepSec,
              pitchConfidence: 1.0,
              onsetConfidence: 1.0
            });
          }
        }

        const avgClarity = seg.clarities.reduce((a, b) => a + b, 0) / Math.max(1, seg.clarities.length);
        const pitchConfidence = Math.round(Math.max(0.2, Math.min(1.0, avgClarity)) * 100) / 100;
        const onsetConfidence = seg.hasOnset ? 0.95 : 0.75;
        const noteConfidence = Math.round((pitchConfidence * 0.65 + onsetConfidence * 0.35) * 100) / 100;

        if (seg.midi === -1) {
          if (quantizedNotes.length > 0 && durationBeats >= 0.5) {
            const lastNote = quantizedNotes[quantizedNotes.length - 1];
            if (lastNote.isRest) {
              lastNote.duration = Math.min(4, lastNote.duration + durationBeats);
              lastNote.endTime = seg.endTime;
            } else {
              quantizedNotes.push({
                midi: 0,
                duration: durationBeats,
                isRest: true,
                confidence: 0.92,
                startTime: seg.startTime,
                endTime: seg.endTime,
                pitchConfidence: 1.0,
                onsetConfidence: 1.0
              });
            }
          }
        } else {
          // 调式吸附
          const activeScaleMode = document.getElementById('selectKey')?.value === 'AUTO' ? 'chromatic' : STATE.scaleMode;
          const snappedMidi = snapPitchToScale(seg.rawMidi > 0 ? seg.rawMidi : seg.midi, STATE.key, activeScaleMode);

          quantizedNotes.push({
            midi: snappedMidi,
            duration: durationBeats,
            isRest: false,
            confidence: noteConfidence,
            startTime: seg.startTime,
            endTime: seg.endTime,
            pitchConfidence,
            onsetConfidence
          });
        }
        lastEndTick = endTick;
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

      if (document.getElementById('selectKey')?.value === 'AUTO') {
        STATE.key = detectBestKey(STATE.notes);
      }

      updateHeaderLabels();
      renderJianpuScore();
      syncRawTextFromNotes();
      showToast(`全曲识别完成！共解析 ${STATE.notes.length} 个音符 (${totalDurationSec}s，调性: 1=${STATE.key})`, 'success');
    }\n\n"""

    content = content[:p_trans1] + trans_block + content[p_trans2:]

    # =========================================================================
    # 3. Update drawPitchContourCanvas to display confidence colors
    # =========================================================================
    old_capsule_color = """          const y = toY(n.midi) - 5;
          ctx.fillStyle = 'rgba(168, 85, 247, 0.45)';
          ctx.strokeStyle = '#a855f7';"""

    new_capsule_color = """          const y = toY(n.midi) - 5;
          const conf = n.confidence !== undefined ? n.confidence : 0.85;
          const isHigh = conf >= 0.80;
          const isMid = conf >= 0.65;
          ctx.fillStyle = isHigh ? 'rgba(34, 197, 94, 0.45)' : (isMid ? 'rgba(234, 179, 8, 0.45)' : 'rgba(239, 68, 68, 0.45)');
          ctx.strokeStyle = isHigh ? '#22c55e' : (isMid ? '#eab308' : '#ef4444');"""

    if old_capsule_color in content:
        content = content.replace(old_capsule_color, new_capsule_color)
    else:
        print(f"Notice: old_capsule_color not found exactly in {filepath}")

    # =========================================================================
    # 4. Replace processSheetImage and extractNotesFromSelectedRegion with OMR Upgrades
    # =========================================================================
    sheet_start_marker = "    function processSheetImage(img) {"
    render_canvas_marker = "    function renderOmrCanvas() {"

    p_sheet1 = content.find(sheet_start_marker)
    p_sheet2 = content.find(render_canvas_marker)
    if p_sheet1 == -1 or p_sheet2 == -1:
        print(f"Error: Could not find processSheetImage bounds in {filepath}")
        return False

    omr_block = """    function processSheetImage(img) {
      lastLoadedSheetImg = img;
      const offCanvas = document.createElement('canvas');
      const maxWidth = 1400;
      const scale = img.width > maxWidth ? maxWidth / img.width : 1;
      offCanvas.width = Math.round(img.width * scale);
      offCanvas.height = Math.round(img.height * scale);

      const ctx = offCanvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, offCanvas.width, offCanvas.height);
      ctx.drawImage(img, 0, 0, offCanvas.width, offCanvas.height);

      let w = offCanvas.width;
      let h = offCanvas.height;
      let imgData = ctx.getImageData(0, 0, w, h).data;
      let gray = new Uint8Array(w * h);

      for (let i = 0; i < w * h; i++) {
        const idx = i * 4;
        gray[i] = Math.round(0.299 * imgData[idx] + 0.587 * imgData[idx + 1] + 0.114 * imgData[idx + 2]);
      }

      // 局部自适应二值化 (Bradley Adaptive Binarization)
      const sensitivityEl = document.getElementById('selectOmrSensitivity');
      const sens = sensitivityEl ? sensitivityEl.value : 'medium';
      const threshRatio = sens === 'high' ? 0.09 : (sens === 'strict' ? 0.18 : 0.13);
      const winSize = Math.max(16, Math.min(48, Math.round(w / 30)));
      let binary = bradleyAdaptiveBinarize(gray, w, h, winSize, threshRatio);

      // RLE 分析提取标准谱线尺寸 (t = 谱线粗细, d = 线间距)
      const rle = estimateStaffDimensionsRle(binary, w, h);
      const estT = rle.t;
      const estD = rle.d;

      // 旋转校正 (Deskew)
      let detectedTiltAngle = 0;
      const cx = w / 2, cy = h / 2;
      const samplePoints = [];
      const stepX = 5, stepY = 2;
      for (let y = 0; y < h; y += stepY) {
        for (let x = 0; x < w; x += stepX) {
          if (binary[y * w + x] === 1) samplePoints.push(x, y);
        }
      }

      if (samplePoints.length > 200) {
        let maxProjVar = -1;
        for (let candDeg = -5.0; candDeg <= 5.0; candDeg += 0.5) {
          const tanT = Math.tan(candDeg * Math.PI / 180);
          const profile = new Int32Array(h);
          for (let p = 0; p < samplePoints.length; p += 2) {
            const px = samplePoints[p];
            const py = samplePoints[p + 1];
            const yp = Math.round(py - (px - cx) * tanT);
            if (yp >= 0 && yp < h) profile[yp]++;
          }

          let pSum = 0, pSumSq = 0;
          for (let y = 0; y < h; y++) {
            const v = profile[y];
            pSum += v;
            pSumSq += v * v;
          }
          const pVar = pSumSq - (pSum * pSum) / h;
          if (pVar > maxProjVar) {
            maxProjVar = pVar;
            detectedTiltAngle = candDeg;
          }
        }
      }

      if (Math.abs(detectedTiltAngle) >= 0.4) {
        const rotCanvas = document.createElement('canvas');
        rotCanvas.width = w;
        rotCanvas.height = h;
        const rctx = rotCanvas.getContext('2d');
        rctx.fillStyle = '#ffffff';
        rctx.fillRect(0, 0, w, h);
        rctx.translate(cx, cy);
        rctx.rotate(-detectedTiltAngle * Math.PI / 180);
        rctx.translate(-cx, -cy);
        rctx.drawImage(offCanvas, 0, 0);

        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(rotCanvas, 0, 0);

        imgData = ctx.getImageData(0, 0, w, h).data;
        for (let i = 0; i < w * h; i++) {
          const idx = i * 4;
          gray[i] = Math.round(0.299 * imgData[idx] + 0.587 * imgData[idx + 1] + 0.114 * imgData[idx + 2]);
        }
        binary = bradleyAdaptiveBinarize(gray, w, h, winSize, threshRatio);
      }

      // 统计五线谱水平线
      const rowHist = new Int32Array(h);
      for (let y = 0; y < h; y++) {
        let count = 0;
        for (let x = 0; x < w; x++) {
          if (binary[y * w + x] === 1) count++;
        }
        rowHist[y] = count;
      }

      // 避免 Math.max(...largeTypedArray) 参数栈溢出
      let maxRowDark = 0;
      for (let y = 0; y < h; y++) maxRowDark = Math.max(maxRowDark, rowHist[y]);
      const lineThreshold = Math.max(w * 0.10, maxRowDark * 0.20);
      const candidateYs = [];
      const peakCandidates = [];
      for (let y = 2; y < h - 2; y++) {
        if (rowHist[y] >= lineThreshold && rowHist[y] >= rowHist[y - 1] && rowHist[y] >= rowHist[y + 1]) {
          peakCandidates.push(y);
        }
      }
      for (const y of peakCandidates) {
        const last = candidateYs[candidateYs.length - 1];
        if (last === undefined || y - last >= Math.max(2, Math.round(estD * 0.48))) {
          candidateYs.push(y);
        } else if (rowHist[y] > rowHist[last]) {
          candidateYs[candidateYs.length - 1] = y;
        }
      }

      // 聚合五线谱组 (Staff Systems)
      const staffSystems = [];
      for (let i = 0; i + 4 < candidateYs.length; ) {
        const group = candidateYs.slice(i, i + 5);
        const spacings = [
          group[1] - group[0],
          group[2] - group[1],
          group[3] - group[2],
          group[4] - group[3]
        ];
        const avgD = spacings.reduce((a, b) => a + b, 0) / 4;
        const isRegular = spacings.every(s => Math.abs(s - avgD) <= Math.max(3.0, avgD * 0.24));
        if (isRegular && avgD >= 6) {
          staffSystems.push({
            lines: group,
            d: avgD,
            t: estT,
            topY: Math.max(0, Math.round(group[0] - avgD * 3.5)),
            bottomY: Math.min(h - 1, Math.round(group[4] + avgD * 3.5))
          });
          i += 5;
        } else {
          i += 1;
        }
      }

      if (staffSystems.length === 0) {
        showToast('未能自动检测到标准五线谱横线，请确认图片平整或使用高灵敏模式', 'warning');
        STATE.omrData = { img: offCanvas, systems: [], notes: [], selectedNoteIndex: null, selectedNoteIndices: [], binary, binaryW: w, binaryH: h };
        renderOmrCanvas();
        return;
      }

      // 每组谱表独立检测有效横向范围与谱号 (Treble vs Bass)
      const userClefMode = document.querySelector('input[name="clefType"]:checked')?.value || 'auto';

      staffSystems.forEach((sys, sysIdx) => {
        let firstInk = w - 1;
        let lastInk = 0;
        for (const ly of sys.lines) {
          const y0 = Math.max(0, ly - Math.max(1, Math.round(sys.t)));
          const y1 = Math.min(h - 1, ly + Math.max(1, Math.round(sys.t)));
          for (let yy = y0; yy <= y1; yy++) {
            const row = yy * w;
            for (let x = 0; x < w; x++) {
              if (binary[row + x]) { firstInk = Math.min(firstInk, x); break; }
            }
            for (let x = w - 1; x >= 0; x--) {
              if (binary[row + x]) { lastInk = Math.max(lastInk, x); break; }
            }
          }
        }
        sys.firstInk = firstInk;
        sys.lastInk = lastInk;
        sys.leftX = Math.max(0, firstInk + Math.round(sys.d * 3.4));
        sys.rightX = Math.min(w - 1, lastInk - Math.round(sys.d * 0.35));

        // 谱号特征识别 (Treble vs Bass)
        let headerDarkAbove = 0, headerDarkBelow = 0;
        const hx0 = Math.max(0, firstInk);
        const hx1 = Math.min(w - 1, firstInk + Math.round(sys.d * 2.8));
        for (let y = Math.max(0, sys.lines[0] - Math.round(sys.d * 1.5)); y <= Math.min(h - 1, sys.lines[4] + Math.round(sys.d * 1.5)); y++) {
          const r = y * w;
          for (let x = hx0; x <= hx1; x++) {
            if (binary[r + x]) {
              if (y < sys.lines[0]) headerDarkAbove++;
              if (y > sys.lines[4]) headerDarkBelow++;
            }
          }
        }

        if (userClefMode === 'treble') {
          sys.clef = 'treble';
        } else if (userClefMode === 'bass') {
          sys.clef = 'bass';
        } else if (userClefMode === 'grand') {
          sys.clef = (sysIdx % 2 === 0) ? 'treble' : 'bass';
        } else {
          // 自动模式：高音谱号向上突破第 5 线、向下突破第 1 线，墨迹显著
          sys.clef = (headerDarkAbove > sys.d * 1.8 && headerDarkBelow > sys.d * 1.8) ? 'treble' : ((sysIdx % 2 === 1) ? 'bass' : 'treble');
        }
      });

      // 形态学开运算剥离细符干、连音横梁与孤立谱线
      const globalD = staffSystems.reduce((acc, s) => acc + s.d, 0) / staffSystems.length;
      const rx = Math.max(2, Math.round(globalD * 0.24));
      const ry = Math.max(2, Math.round(globalD * 0.18));

      const offsets = [];
      for (let dy = -ry; dy <= ry; dy++) {
        for (let dx = -rx; dx <= rx; dx++) {
          if ((dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.05) offsets.push([dx, dy]);
        }
      }

      // 腐蚀 (Erosion)
      const eroded = new Uint8Array(w * h);
      for (let y = ry; y < h - ry; y++) {
        const yW = y * w;
        for (let x = rx; x < w - rx; x++) {
          if (binary[yW + x] === 0) continue;
          let allBlack = true;
          for (let i = 0; i < offsets.length; i++) {
            if (binary[(y + offsets[i][1]) * w + (x + offsets[i][0])] !== 1) {
              allBlack = false;
              break;
            }
          }
          if (allBlack) eroded[yW + x] = 1;
        }
      }

      // 膨胀 (Dilation) -> 得到纯净符头掩模 (Opened Noteheads)
      const opened = new Uint8Array(w * h);
      for (let y = 0; y < h; y++) {
        const yW = y * w;
        for (let x = 0; x < w; x++) {
          if (eroded[yW + x] === 1) {
            for (let i = 0; i < offsets.length; i++) {
              const nx = x + offsets[i][0];
              const ny = y + offsets[i][1];
              if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
                opened[ny * w + nx] = 1;
              }
            }
          }
        }
      }

      // 提取全部连通域候选组件
      const visited = new Uint8Array(w * h);
      const rawComps = [];

      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const idx = y * w + x;
          if (opened[idx] === 1 && !visited[idx]) {
            let q = [[x, y]], area = 0, sumX = 0, sumY = 0;
            let cMinX = x, cMaxX = x, cMinY = y, cMaxY = y;
            visited[idx] = 1;

            while (q.length > 0) {
              const [qx, qy] = q.pop();
              area++;
              sumX += qx;
              sumY += qy;
              if (qx < cMinX) cMinX = qx;
              if (qx > cMaxX) cMaxX = qx;
              if (qy < cMinY) cMinY = qy;
              if (qy > cMaxY) cMaxY = qy;

              for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
                const nx = qx + dx, ny = qy + dy;
                if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
                  const nIdx = ny * w + nx;
                  if (opened[nIdx] === 1 && !visited[nIdx]) {
                    visited[nIdx] = 1;
                    q.push([nx, ny]);
                  }
                }
              }
            }

            const bw = cMaxX - cMinX + 1;
            const bh = cMaxY - cMinY + 1;
            const cx = Math.round(sumX / area);
            const cy = Math.round(sumY / area);
            const aspect = bw / Math.max(1, bh);

            if (area >= globalD * globalD * 0.12 && area <= globalD * globalD * 8.0) {
              rawComps.push({ cx, cy, cMinX, cMaxX, cMinY, cMaxY, bw, bh, area, aspect });
            }
          }
        }
      }

      // 符号分类器 (Symbol Classification Engine)
      function classifyOmrComponent(comp, sys, d) {
        const aspect = comp.aspect;
        const isHeader = comp.cx < (sys.leftX || (sys.firstInk + d * 3.4));

        // 1. 小节线检测 (Barline)
        if (comp.bh >= d * 3.2 && comp.bw <= d * 0.55 && aspect <= 0.18) {
          return { symbolType: 'barline', isNote: false, penalty: 1.0 };
        }

        // 2. 符杠横梁 (Beam) - 坚决禁止将符杠当成音符生成几十个假音！
        if (comp.bw >= d * 1.8 && (aspect >= 2.0 || comp.bh <= d * 1.1)) {
          return { symbolType: 'beam', isNote: false, penalty: 1.0 };
        }

        // 3. 符干 (Stem)
        if (comp.bh >= d * 1.8 && comp.bw <= d * 0.45 && aspect <= 0.25) {
          return { symbolType: 'stem', isNote: false, penalty: 1.0 };
        }

        // 4. Header 区域符号 (Clef / KeySignature / TimeSignature)
        if (isHeader) {
          if (comp.bh >= d * 2.5) {
            return { symbolType: 'clef', isNote: false, penalty: 1.0 };
          }
          if (comp.bh >= d * 1.5 && comp.bw >= d * 0.6) {
            return { symbolType: 'timeSignature', isNote: false, penalty: 1.0 };
          }
          return { symbolType: 'keySignature', isNote: false, penalty: 0.95 };
        }

        // 5. 符头候选 (Notehead)
        if (comp.bw >= d * 0.60 && comp.bw <= d * 1.75 &&
            comp.bh >= d * 0.50 && comp.bh <= d * 1.55 &&
            aspect >= 0.65 && aspect <= 1.85 &&
            comp.area >= d * d * 0.18 && comp.area <= d * d * 2.4) {
          return { symbolType: 'notehead', isNote: true, penalty: 0.0 };
        }

        return { symbolType: 'unknown', isNote: false, penalty: 0.85 };
      }

      // 符头几何置信度评分 (Notehead Geometric Scoring)
      function computeNoteheadScore(comp, sys, d, stemSupport = true) {
        const aspect = comp.aspect;
        const area = comp.area;
        const classification = classifyOmrComponent(comp, sys, d);

        if (!classification.isNote) {
          return {
            confidence: 0.1,
            symbolType: classification.symbolType,
            isNote: false,
            scores: {
              geometry: 0.1,
              staffPosition: 0.1,
              stemSupport: 0,
              headerPenalty: classification.symbolType.includes('Signature') || classification.symbolType === 'clef' ? 1 : 0,
              beamPenalty: classification.symbolType === 'beam' ? 1 : 0,
              clefPenalty: classification.symbolType === 'clef' ? 1 : 0
            }
          };
        }

        // 几何评分
        const geomAspect = 1 - Math.min(1, Math.abs(aspect - 1.25) / 0.75);
        const geomArea = 1 - Math.min(1, Math.abs(area - 0.75 * d * d) / (0.75 * d * d));
        const geometryScore = Math.max(0, geomAspect * 0.55 + geomArea * 0.45);

        // 谱表网格线/间吸附评分
        const bottomLineY = sys.lines[4];
        const step = Math.round((bottomLineY - comp.cy) / (d / 2));
        const targetY = bottomLineY - step * (d / 2);
        const distY = Math.abs(comp.cy - targetY);
        const staffPositionScore = Math.max(0, 1 - Math.min(1, distY / (d * 0.4)));

        const stemScore = stemSupport ? 1.0 : 0.45;
        const confidence = Math.max(0.1, Math.min(0.99,
          geometryScore * 0.40 + staffPositionScore * 0.35 + stemScore * 0.25 - classification.penalty * 0.8
        ));

        return {
          confidence: Math.round(confidence * 100) / 100,
          symbolType: 'notehead',
          isNote: true,
          step,
          scores: {
            geometry: Math.round(geometryScore * 100) / 100,
            staffPosition: Math.round(staffPositionScore * 100) / 100,
            stemSupport: stemSupport ? 1 : 0,
            headerPenalty: 0,
            beamPenalty: 0,
            clefPenalty: 0
          }
        };
      }

      const diatonicSemitones = [0, 2, 4, 5, 7, 9, 11];
      let globalNoteId = 1;
      const detectedNotes = [];

      staffSystems.forEach((sys, sysIdx) => {
        const d = sys.d;
        const bottomLineY = sys.lines[4];
        const isTreble = sys.clef === 'treble';
        const bottomDiatonic = isTreble ? 2 : 4; // E4 (treble) vs G2 (bass)
        const baseOct = isTreble ? 4 : 2;

        const leftBound = Number.isFinite(sys.leftX) ? sys.leftX : Math.round(d * 3.4);
        const rightBound = Number.isFinite(sys.rightX) ? sys.rightX : w - Math.round(d * 0.5);

        const sysComps = rawComps.filter(c => {
          return c.cx >= leftBound && c.cx <= rightBound && c.cy >= sys.topY && c.cy <= sys.bottomY;
        });

        const sysNotes = [];
        for (const comp of sysComps) {
          // 符干垂直支撑检查
          let stemSupport = false;
          const sx = comp.cx;
          for (let sy = comp.cy - Math.round(d * 3.0); sy <= comp.cy + Math.round(d * 3.0); sy++) {
            if (sy >= 0 && sy < h && binary[sy * w + sx] === 1 && Math.abs(sy - comp.cy) > d * 0.6) {
              stemSupport = true;
              break;
            }
          }

          const scoreObj = computeNoteheadScore(comp, sys, d, stemSupport);
          if (!scoreObj.isNote || scoreObj.confidence < 0.40) {
            continue; // 彻底排除符杠、谱号、小节线与无效噪点！
          }

          const step = scoreObj.step;
          const totalDiatonic = bottomDiatonic + step;
          const octOffset = Math.floor(totalDiatonic / 7);
          const deg = ((totalDiatonic % 7) + 7) % 7;
          const midi = (baseOct + octOffset + 1) * 12 + diatonicSemitones[deg];

          // 第一层：判断实心/空心
          let coreDark = 0, coreTotal = 0;
          const crx = Math.max(2, Math.round(d * 0.25));
          const cry = Math.max(2, Math.round(d * 0.20));
          for (let dy = -cry; dy <= cry; dy++) {
            for (let dx = -crx; dx <= crx; dx++) {
              const px = comp.cx + dx, py = comp.cy + dy;
              if (px >= 0 && px < w && py >= 0 && py < h) {
                coreTotal++;
                if (binary[py * w + px] === 1) coreDark++;
              }
            }
          }
          const isHollow = (coreDark / Math.max(1, coreTotal)) < 0.45;

          // 第二层：符干与横梁时值检测
          let duration = isHollow ? (stemSupport ? 2 : 4) : 1;
          if (!isHollow && stemSupport) {
            let beamCount = 0;
            const topCheckY = comp.cy - Math.round(d * 3.0);
            if (topCheckY >= 0) {
              let darkH = 0;
              for (let bx = comp.cx - Math.round(d * 0.8); bx <= comp.cx + Math.round(d * 0.8); bx++) {
                if (bx >= 0 && bx < w && binary[topCheckY * w + bx]) darkH++;
              }
              if (darkH >= d * 1.0) beamCount = 1;
            }
            if (beamCount === 1) duration = 0.5; // 八分音符
          }

          // 第三层：附点检测
          let hasDot = false;
          let dotDark = 0;
          const dotX0 = comp.cx + Math.round(d * 0.8);
          const dotX1 = comp.cx + Math.round(d * 1.5);
          for (let dy = -Math.round(d * 0.25); dy <= Math.round(d * 0.25); dy++) {
            for (let dx = dotX0; dx <= dotX1; dx++) {
              const py = comp.cy + dy;
              if (dx >= 0 && dx < w && py >= 0 && py < h && binary[py * w + dx]) {
                dotDark++;
              }
            }
          }
          if (dotDark >= 2 && dotDark <= d * d * 0.35) {
            hasDot = true;
            duration *= 1.5;
          }

          sysNotes.push({
            id: globalNoteId++,
            x: comp.cx,
            y: comp.cy,
            midi,
            duration,
            isRest: false,
            step,
            sysIdx,
            clef: sys.clef,
            staffIndex: sysIdx,
            staffPosition: step,
            symbolType: 'notehead',
            confidence: scoreObj.confidence,
            scores: scoreObj.scores,
            hasDot,
            box: {
              x: Math.round(comp.cx - d * 0.6),
              y: Math.round(bottomLineY - step * (d / 2) - d * 0.55),
              w: Math.round(d * 1.2),
              h: Math.round(d * 1.1)
            }
          });
        }

        // 去除过于重叠的冗余音符
        sysNotes.sort((a, b) => a.x - b.x);
        const filteredSysNotes = [];
        for (const n of sysNotes) {
          if (filteredSysNotes.length > 0) {
            const prev = filteredSysNotes[filteredSysNotes.length - 1];
            if (Math.abs(n.x - prev.x) < d * 0.45 && Math.abs(n.y - prev.y) < d * 0.45) continue;
          }
          filteredSysNotes.push(n);
        }

        detectedNotes.push(...filteredSysNotes);
      });

      STATE.omrData = {
        img: offCanvas,
        systems: staffSystems,
        notes: detectedNotes,
        selectedNoteIndex: detectedNotes.length > 0 ? 0 : null,
        selectedNoteIndices: [],
        binary,
        binaryW: w,
        binaryH: h,
        selectionBox: null
      };

      // 更新顶部徽章与左侧状态卡
      const badgeCountEl = document.getElementById('centerOmrBadgeCount');
      if (badgeCountEl) {
        badgeCountEl.textContent = `${detectedNotes.length}音`;
      }
      updateOmrStatusCard(staffSystems.length, detectedNotes.length);

      // 同步全局主乐谱简谱
      STATE.notes = detectedNotes.map(n => ({ midi: n.midi, duration: n.duration, isRest: false, confidence: n.confidence }));
      renderJianpuScore();
      syncRawTextFromNotes();

      renderOmrCanvas();
      showToast(`五线谱识别成功！已精确定位 ${detectedNotes.length} 个音符并过滤非音符符号`, 'success');
    }\n\n"""

    content = content[:p_sheet1] + omr_block + content[p_sheet2:]

    # =========================================================================
    # 5. Replace extractNotesFromSelectedRegion with memory-optimized & symbol-checked version
    # =========================================================================
    extract_start_marker = "    function extractNotesFromSelectedRegion(minX, maxX, minY, maxY) {"
    sort_sync_marker = "    // 音符数组排序与全局简谱同步"

    p_ext1 = content.find(extract_start_marker)
    p_ext2 = content.find(sort_sync_marker)
    if p_ext1 == -1 or p_ext2 == -1:
        print(f"Error: Could not find extractNotesFromSelectedRegion bounds in {filepath}")
        return False

    extract_block = """    function extractNotesFromSelectedRegion(minX, maxX, minY, maxY) {
      if (!STATE.omrData || !STATE.omrData.binary || !STATE.omrData.systems) return;

      const w = STATE.omrData.binaryW;
      const h = STATE.omrData.binaryH;
      const bin = STATE.omrData.binary;
      const systems = STATE.omrData.systems;
      const clefMode = document.querySelector('input[name="clefType"]:checked')?.value || 'auto';

      // 确定框选重叠的谱表
      const matchedSystems = [];
      systems.forEach((sys, sIdx) => {
        if (maxY >= sys.topY - sys.d && minY <= sys.bottomY + sys.d) {
          matchedSystems.push({ sys, sIdx });
        }
      });
      if (matchedSystems.length === 0) {
        showToast('框选区域未覆盖五线谱表，请在乐谱范围内拉框', 'info');
        return;
      }

      const avgD = matchedSystems[0].sys.d;
      const rx = Math.max(2, Math.round(avgD * 0.24));
      const ry = Math.max(2, Math.round(avgD * 0.18));

      // 仅对框选选区分配紧凑内存，避免全图 W*H 数组造成的 GC 停顿与卡顿
      const bx1 = Math.max(0, Math.floor(minX));
      const bx2 = Math.min(w - 1, Math.ceil(maxX));
      const by1 = Math.max(0, Math.floor(minY));
      const by2 = Math.min(h - 1, Math.ceil(maxY));
      const bw = bx2 - bx1 + 1;
      const bh = by2 - by1 + 1;

      const offsets = [];
      for (let dy = -ry; dy <= ry; dy++) {
        for (let dx = -rx; dx <= rx; dx++) {
          if ((dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.05) offsets.push([dx, dy]);
        }
      }

      // 局部腐蚀
      const localEroded = new Uint8Array(bw * bh);
      for (let y = Math.max(ry, by1); y <= Math.min(h - 1 - ry, by2); y++) {
        const localY = y - by1;
        for (let x = Math.max(rx, bx1); x <= Math.min(w - 1 - rx, bx2); x++) {
          const localX = x - bx1;
          if (bin[y * w + x] === 0) continue;
          let ok = true;
          for (let i = 0; i < offsets.length; i++) {
            if (bin[(y + offsets[i][1]) * w + (x + offsets[i][0])] !== 1) {
              ok = false;
              break;
            }
          }
          if (ok) localEroded[localY * bw + localX] = 1;
        }
      }

      // 局部膨胀
      const localOpened = new Uint8Array(bw * bh);
      for (let y = by1; y <= by2; y++) {
        const localY = y - by1;
        for (let x = bx1; x <= bx2; x++) {
          const localX = x - bx1;
          if (localEroded[localY * bw + localX] === 1) {
            for (let i = 0; i < offsets.length; i++) {
              const nx = x + offsets[i][0];
              const ny = y + offsets[i][1];
              if (nx >= bx1 && nx <= bx2 && ny >= by1 && ny <= by2) {
                localOpened[(ny - by1) * bw + (nx - bx1)] = 1;
              }
            }
          }
        }
      }

      // 提取框内连通域
      const visited = new Uint8Array(bw * bh);
      const candidates = [];

      for (let y = by1; y <= by2; y++) {
        const localY = y - by1;
        for (let x = bx1; x <= bx2; x++) {
          const localX = x - bx1;
          const idx = localY * bw + localX;
          if (localOpened[idx] === 1 && !visited[idx]) {
            let q = [[x, y]], area = 0, sumX = 0, sumY = 0;
            let cMinX = x, cMaxX = x, cMinY = y, cMaxY = y;
            visited[idx] = 1;

            while (q.length > 0) {
              const [qx, qy] = q.pop();
              area++;
              sumX += qx;
              sumY += qy;
              if (qx < cMinX) cMinX = qx;
              if (qx > cMaxX) cMaxX = qx;
              if (qy < cMinY) cMinY = qy;
              if (qy > cMaxY) cMaxY = qy;

              for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
                const nx = qx + dx, ny = qy + dy;
                if (nx >= bx1 && nx <= bx2 && ny >= by1 && ny <= by2) {
                  const nIdx = (ny - by1) * bw + (nx - bx1);
                  if (localOpened[nIdx] === 1 && !visited[nIdx]) {
                    visited[nIdx] = 1;
                    q.push([nx, ny]);
                  }
                }
              }
            }

            const compW = cMaxX - cMinX + 1;
            const compH = cMaxY - cMinY + 1;
            const cx = Math.round(sumX / area);
            const cy = Math.round(sumY / area);
            const aspect = compW / Math.max(1, compH);

            // 过滤符杠横梁与细长谱线，保留正常符头
            if (compW >= avgD * 0.60 && compW <= avgD * 1.8 &&
                compH >= avgD * 0.50 && compH <= avgD * 1.6 &&
                aspect >= 0.65 && aspect <= 1.85 &&
                area >= avgD * avgD * 0.18 && area <= avgD * avgD * 2.5) {
              candidates.push({ cx, cy, bw: compW, bh: compH, area, aspect });
            }
          }
        }
      }

      let addedCount = 0;
      const diatonicSemitones = [0, 2, 4, 5, 7, 9, 11];

      candidates.forEach(cand => {
        let targetSys = null, targetSIdx = 0;
        for (const m of matchedSystems) {
          if (cand.cy >= m.sys.topY - m.sys.d && cand.cy <= m.sys.bottomY + m.sys.d) {
            targetSys = m.sys;
            targetSIdx = m.sIdx;
            break;
          }
        }
        if (!targetSys) targetSys = matchedSystems[0].sys, targetSIdx = matchedSystems[0].sIdx;

        const d = targetSys.d;
        // 避开已有音符
        const exists = STATE.omrData.notes.some(n => Math.hypot(n.x - cand.cx, n.y - cand.cy) < d * 0.55);
        if (exists) return;

        const bottomLineY = targetSys.lines[4];
        const step = Math.round((bottomLineY - cand.cy) / (d / 2));
        const isTreble = targetSys.clef === 'treble';
        const bottomDiatonic = isTreble ? 2 : 4;
        const baseOct = isTreble ? 4 : 2;

        const totalDiatonic = bottomDiatonic + step;
        const octOffset = Math.floor(totalDiatonic / 7);
        const deg = ((totalDiatonic % 7) + 7) % 7;
        const midi = (baseOct + octOffset + 1) * 12 + diatonicSemitones[deg];

        // 判别空心
        let coreDark = 0, coreTotal = 0;
        const crx = Math.max(2, Math.round(d * 0.25));
        const cry = Math.max(2, Math.round(d * 0.20));
        for (let dy = -cry; dy <= cry; dy++) {
          for (let dx = -crx; dx <= crx; dx++) {
            const px = cand.cx + dx, py = cand.cy + dy;
            if (px >= 0 && px < w && py >= 0 && py < h) {
              coreTotal++;
              if (bin[py * w + px] === 1) coreDark++;
            }
          }
        }
        const isHollow = (coreDark / Math.max(1, coreTotal)) < 0.45;

        const newNote = {
          id: Date.now() + Math.floor(Math.random() * 10000),
          x: cand.cx,
          y: Math.round(bottomLineY - step * (d / 2)),
          midi,
          duration: isHollow ? 2 : 1,
          isRest: false,
          step,
          sysIdx: targetSIdx,
          clef: targetSys.clef,
          staffIndex: targetSIdx,
          staffPosition: step,
          symbolType: 'notehead',
          confidence: 0.90,
          scores: {
            geometry: 0.90,
            staffPosition: 0.95,
            stemSupport: 1,
            headerPenalty: 0,
            beamPenalty: 0,
            clefPenalty: 0
          },
          box: {
            x: Math.round(cand.cx - d * 0.6),
            y: Math.round(bottomLineY - step * (d / 2) - d * 0.55),
            w: Math.round(d * 1.2),
            h: Math.round(d * 1.1)
          }
        };

        STATE.omrData.notes.push(newNote);
        addedCount++;
      });

      if (addedCount > 0) {
        sortAndSyncOmrNotes();
        playOmrPreviewTone(60, 0.25);
        showToast(`🎯 框选提取成功！已在选区内识别并添加 ${addedCount} 个音符`, 'success');
      } else {
        const inBoxIdx = STATE.omrData.notes.findIndex(n => n.x >= minX && n.x <= maxX && n.y >= minY && n.y <= maxY);
        if (inBoxIdx !== -1) {
          STATE.omrData.selectedNoteIndex = inBoxIdx;
          updateOmrToolbarBadge();
          showToast(`已选中框内第 #${inBoxIdx + 1} 个音符`, 'info');
        } else {
          showToast('选区内未检测到标准符头，可尝试缩小选区或单点补音', 'info');
        }
      }
    }\n\n"""

    content = content[:p_ext1] + extract_block + content[p_ext2:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Successfully patched {filepath}!")
    return True

if __name__ == '__main__':
    ok1 = patch_file('index.html')
    ok2 = patch_file('jianpu_studio.html')
    download_copy = '/Users/oneriver/Downloads/jianpu_studio.html'
    import os
    if os.path.exists(download_copy):
        ok3 = patch_file(download_copy)
    else:
        ok3 = True
    if ok1 and ok2 and ok3:
        print("All target files patched successfully!")
        sys.exit(0)
    else:
        print("Patching failed on some targets!")
        sys.exit(1)
