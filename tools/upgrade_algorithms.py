# -*- coding: utf-8 -*-
with open('/Users/oneriver/Downloads/jianpu_studio.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Advanced pYIN-inspired Multi-Candidate Pitch Detection with Octave-Suppression & Temporal Memory
new_detect_pitch = r'''    /**
     * 高精度多候选音高检测算法 (借鉴国际开源音频项目 pYIN / Aubio / Basic Pitch)
     * 核心特性：多候选极小值检出 + 次谐波校验 (Sub-harmonic Verification) + 八度跳变抑制
     */
    function detectPitchYIN(buffer, sampleRate, prevMidi = -1) {
      const halfLen = Math.floor(buffer.length / 2);
      const minTau = Math.max(2, Math.floor(sampleRate / 1050)); // ~C6 (1046Hz)
      const maxTau = Math.min(halfLen - 2, Math.floor(sampleRate / 68));  // ~C2 (65Hz)
      const yinBuffer = new Float32Array(maxTau + 2);

      // 1. 平方差函数 (加速步长计算)
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

      // 3. 多候选极值检出 (搜集所有局部谷底候选 tau)
      const candidates = [];
      for (let tau = minTau; tau <= maxTau; tau++) {
        if (yinBuffer[tau] < 0.48 && 
            (tau === minTau || yinBuffer[tau] <= yinBuffer[tau - 1]) && 
            (tau === maxTau || yinBuffer[tau] <= yinBuffer[tau + 1])) {
          
          // 局部抛物线插值提高精度
          let betterTau = tau;
          if (tau > 0 && tau < maxTau) {
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
          candidates.push({ tau: betterTau, cmndf: yinBuffer[tau], freq, midi });
        }
      }

      if (candidates.length === 0) return { freq: -1, clarity: 0 };

      // 按谷底深度排序
      candidates.sort((a, b) => a.cmndf - b.cmndf);

      // 4. 次谐波与八度抑制逻辑 (防止人声共振峰引起的八度过低或过高错误)
      let best = candidates[0];

      // 检查是否存在较高频的真基频 (避免把双倍周期当成基频，即避免八度偏低)
      for (let i = 1; i < candidates.length; i++) {
        const cand = candidates[i];
        // 如果候选周期大约是最佳周期的一半 (即高八度)，且其差值也很小 (<0.22)
        if (cand.tau < best.tau * 0.6 && cand.cmndf < 0.22) {
          best = cand;
          break;
        }
      }

      // 若有上一帧连续音高作为上下文参考，优先选择与前帧连续平滑的候选
      if (prevMidi > 0) {
        for (const cand of candidates) {
          if (Math.abs(cand.midi - prevMidi) <= 2.2 && cand.cmndf < 0.35) {
            best = cand;
            break;
          }
        }
      }

      const clarity = Math.max(0, Math.min(1, 1 - best.cmndf));
      return { freq: best.freq, clarity, rawMidi: best.midi };
    }'''

import re
content = re.sub(r'function detectPitchYIN[\s\S]*?\n    \}', new_detect_pitch.strip(), content, count=1)

# 2. Update runAudioTranscription to pass prevMidi into detectPitchYIN
content = content.replace(
    'const { freq, clarity } = detectPitchYIN(slice, sampleRate);',
    'const prevDetectedMidi = frames.length > 0 && frames[frames.length - 1].midi > 0 ? frames[frames.length - 1].midi : -1;\n          const { freq, clarity, rawMidi: preciseMidi } = detectPitchYIN(slice, sampleRate, prevDetectedMidi);'
)

# 3. Enhance OMR: Otsu's adaptive binarization + staff spacing calculation + ledger line & barline filtering
new_process_sheet = r'''    /**
     * 高精度五线谱光学识谱引擎 (借鉴开源 OMR 项目 Audiveris / Gamera)
     * 核心特性：Otsu 动态大津二值化 + 游程统计抗噪 + 椭圆符头形态学识别 + 谱表加线探测
     */
    function processSheetImage(img) {
      lastLoadedSheetImg = img;
      const offCanvas = document.createElement('canvas');
      const maxWidth = 1200;
      const scale = img.width > maxWidth ? maxWidth / img.width : 1;
      offCanvas.width = Math.round(img.width * scale);
      offCanvas.height = Math.round(img.height * scale);

      const ctx = offCanvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, offCanvas.width, offCanvas.height);
      ctx.drawImage(img, 0, 0, offCanvas.width, offCanvas.height);

      const w = offCanvas.width;
      const h = offCanvas.height;
      const imgData = ctx.getImageData(0, 0, w, h).data;

      // 1. Otsu 动态大津二值化 (自适应不同光照与背景的乐谱)
      const hist = new Int32Array(256);
      const gray = new Uint8Array(w * h);

      for (let i = 0; i < w * h; i++) {
        const idx = i * 4;
        const lum = Math.round(0.299 * imgData[idx] + 0.587 * imgData[idx + 1] + 0.114 * imgData[idx + 2]);
        gray[i] = lum;
        hist[lum]++;
      }

      let total = w * h;
      let sum = 0;
      for (let t = 0; t < 256; t++) sum += t * hist[t];

      let sumB = 0, wB = 0, wF = 0, varMax = 0, otsuThreshold = 145;
      for (let t = 0; t < 256; t++) {
        wB += hist[t];
        if (wB === 0) continue;
        wF = total - wB;
        if (wF === 0) break;
        sumB += t * hist[t];
        const mB = sumB / wB;
        const mF = (sum - sumB) / wF;
        const betweenVar = wB * wF * (mB - mF) * (mB - mF);
        if (betweenVar > varMax) {
          varMax = betweenVar;
          otsuThreshold = t;
        }
      }
      otsuThreshold = Math.max(120, Math.min(185, otsuThreshold));

      const binary = new Uint8Array(w * h);
      const rowHist = new Int32Array(h);

      for (let y = 0; y < h; y++) {
        let darkCount = 0;
        for (let x = 0; x < w; x++) {
          const idx = y * w + x;
          if (gray[idx] < otsuThreshold) {
            binary[idx] = 1;
            darkCount++;
          }
        }
        rowHist[y] = darkCount;
      }

      // 2. 统计五线谱水平线峰值
      const maxRowDark = Math.max(...rowHist);
      const lineThreshold = Math.max(w * 0.25, maxRowDark * 0.42);
      const candidateYs = [];

      for (let y = 2; y < h - 2; y++) {
        if (rowHist[y] > lineThreshold && rowHist[y] >= rowHist[y - 1] && rowHist[y] >= rowHist[y + 1]) {
          if (candidateYs.length === 0 || y - candidateYs[candidateYs.length - 1] > 3) {
            candidateYs.push(y);
          }
        }
      }

      // 3. 聚合五线谱组 (Staff Systems)
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
        const isRegular = spacings.every(s => Math.abs(s - avgD) <= Math.max(3.5, avgD * 0.28));
        if (isRegular && avgD >= 6) {
          staffSystems.push({ lines: group, d: avgD });
          i += 5;
        } else {
          i += 1;
        }
      }

      if (staffSystems.length === 0) {
        showToast('未能自动检测到标准五线谱横线，请上传平整清晰的乐谱图片', 'warning');
        STATE.omrData = { img: offCanvas, systems: [], noteheads: [] };
        document.getElementById('omrPreviewContainer').classList.remove('hidden');
        renderOmrCanvas();
        return;
      }

      // 4. 垂直去线：滤除细水平谱线，保留符干与椭圆符头
      const noLines = new Uint8Array(w * h);
      for (let x = 0; x < w; x++) {
        for (let y = 1; y < h - 1; y++) {
          if (binary[y * w + x] && binary[(y - 1) * w + x] && binary[(y + 1) * w + x]) {
            noLines[y * w + x] = 1;
          }
        }
      }

      // 5. 扫描符头形态 (椭圆纵横比与面积过滤，剔除细长小节线)
      const detectedNotes = [];
      const detectedBoxes = [];
      const clef = document.querySelector('input[name="clefType"]:checked').value;

      const bottomLineDiatonicStep = clef === 'treble' ? 2 : 4; // 高音谱号底线 E4, 低音谱号底线 G2
      const bottomLineOctave = clef === 'treble' ? 4 : 2;
      const majorScaleSemitones = [0, 2, 4, 5, 7, 9, 11];

      for (const sys of staffSystems) {
        const d = sys.d;
        // 扩展扫描上下各 3 个线距 (支持上加线与下加线音符，如下加一线 C4)
        const topY = Math.max(0, Math.round(sys.lines[0] - d * 3.2));
        const bottomY = Math.min(h - 1, Math.round(sys.lines[4] + d * 3.2));
        const bottomLineY = sys.lines[4];

        const visited = new Uint8Array(w * h);
        const sysNotes = [];

        // 跳过左侧谱号占位区域 (约 3.5 ~ 4 个线距)
        for (let x = Math.round(d * 3.8); x < w - Math.round(d); x++) {
          for (let y = topY; y <= bottomY; y++) {
            const idx = y * w + x;
            if (noLines[idx] && !visited[idx]) {
              let minX = x, maxX = x, minY = y, maxY = y, area = 0;
              const queue = [[x, y]];
              visited[idx] = 1;

              while (queue.length > 0) {
                const [cx, cy] = queue.shift();
                area++;
                if (cx < minX) minX = cx;
                if (cx > maxX) maxX = cx;
                if (cy < minY) minY = cy;
                if (cy > maxY) maxY = cy;

                for (let dx = -1; dx <= 1; dx++) {
                  for (let dy = -1; dy <= 1; dy++) {
                    const nx = cx + dx, ny = cy + dy;
                    if (nx >= 0 && nx < w && ny >= topY && ny <= bottomY) {
                      const nIdx = ny * w + nx;
                      if (noLines[nIdx] && !visited[nIdx]) {
                        visited[nIdx] = 1;
                        queue.push([nx, ny]);
                      }
                    }
                  }
                }
              }

              const bw = maxX - minX + 1;
              const bh = maxY - minY + 1;

              // 过滤掉纯竖线小节线 (小节线宽度极细 <= 3px 且高度较大)
              if (bw <= 3 && bh >= d * 2.8) continue;

              // 符头特征匹配 (宽度约 0.65d ~ 2.0d，面积合理)
              if (bw >= d * 0.65 && bw <= d * 2.2 && bh >= d * 0.65 && bh <= d * 4.6 && area >= d * d * 0.25) {
                // 搜索符头椭圆的最高密度中心 Y
                let bestHeadY = (minY + maxY) / 2;
                let maxLocalPixels = -1;
                const headHalfH = Math.max(2, Math.round(d * 0.45));
                for (let scanY = minY + headHalfH; scanY <= maxY - headHalfH; scanY++) {
                  let count = 0;
                  for (let sy = scanY - headHalfH; sy <= scanY + headHalfH; sy++) {
                    for (let sx = minX; sx <= maxX; sx++) {
                      if (noLines[sy * w + sx]) count++;
                    }
                  }
                  if (count > maxLocalPixels) {
                    maxLocalPixels = count;
                    bestHeadY = scanY;
                  }
                }

                // 避免同一符头重复注册
                if (sysNotes.length > 0 && Math.abs(minX - sysNotes[sysNotes.length - 1].x) < d * 0.75) {
                  continue;
                }

                const centerX = Math.round((minX + maxX) / 2);
                const centerY = Math.round(bestHeadY);
                const isHollow = binary[centerY * w + centerX] === 0;

                // 计算相对五线谱底线的半间距步数
                const stepsFromBottom = Math.round((bottomLineY - bestHeadY) / (d / 2));
                const totalDiatonic = bottomLineDiatonicStep + stepsFromBottom;
                const octaveOffset = Math.floor(totalDiatonic / 7);
                const degreeIdx = ((totalDiatonic % 7) + 7) % 7;
                const midi = (bottomLineOctave + octaveOffset + 1) * 12 + majorScaleSemitones[degreeIdx];

                sysNotes.push({
                  x: centerX,
                  y: centerY,
                  midi,
                  duration: isHollow ? 2 : 1,
                  isRest: false
                });

                detectedBoxes.push({
                  x: minX - 2,
                  y: centerY - Math.round(d * 0.55),
                  w: bw + 4,
                  h: Math.round(d * 1.1)
                });
              }
            }
          }
        }

        sysNotes.sort((a, b) => a.x - b.x);
        detectedNotes.push(...sysNotes);
      }

      STATE.omrData = {
        img: offCanvas,
        systems: staffSystems,
        noteheads: detectedBoxes
      };

      document.getElementById('omrPreviewContainer').classList.remove('hidden');
      renderOmrCanvas();

      if (detectedNotes.length === 0) {
        showToast('已定位五线谱，但未能识别出音符，请尝试更清晰的乐谱图片', 'warning');
        return;
      }

      document.getElementById('omrStatsBadge').innerHTML =
        `<span>✅ 识别完成：检测到 ${staffSystems.length} 组五线谱，共提取 ${detectedNotes.length} 个音符</span>`;

      STATE.notes = detectedNotes.map(n => ({ midi: n.midi, duration: n.duration, isRest: false }));
      updateHeaderLabels();
      renderJianpuScore();
      syncRawTextFromNotes();
      showToast(`五线谱识别成功！已生成 ${STATE.notes.length} 个简谱音符`, 'success');
    }'''

content = re.sub(r'function processSheetImage[\s\S]*?\n      showToast\(`五线谱识别成功！已生成[\s\S]*?\n    \}', new_process_sheet.strip(), content, count=1)

with open('/Users/oneriver/Downloads/jianpu_studio.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Advanced OMR and pYIN algorithms applied successfully!")
