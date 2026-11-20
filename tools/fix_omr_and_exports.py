# -*- coding: utf-8 -*-
"""
Fix OMR image drop and missing export & view switcher functions:
1. Restore switchCenterView(view) and confirmOmrAndSwitchToJianpu() right after processSheetImage
2. In processSheetImage, remove undefined updateOmrStatusCard, ensure switchCenterView('omr') is called,
   and make centerViewSwitcher visible.
3. Restore exportJianpuSvg, exportMusicXml, exportJianpuPng, exportMidiFile, copyJianpuText.
4. Ensure index.html, jianpu_studio.html, and /Users/oneriver/Downloads/jianpu_studio.html are identical and valid.
"""

import sys
import os

def fix_file(filepath):
    print(f"Fixing {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Fix the end of processSheetImage and restore switchCenterView & confirmOmrAndSwitchToJianpu
    target_end_marker = """      // 更新顶部徽章与左侧状态卡
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
    }"""

    replacement_end_block = """      // 更新顶部徽章与左侧状态卡
      const badgeCountEl = document.getElementById('centerOmrBadgeCount');
      if (badgeCountEl) {
        badgeCountEl.textContent = `${detectedNotes.length}音`;
        badgeCountEl.classList.remove('hidden');
      }
      const leftStatusCard = document.getElementById('omrLeftStatusCard');
      const leftStatusCount = document.getElementById('omrLeftStatusCount');
      if (leftStatusCard && leftStatusCount) {
        leftStatusCount.textContent = `${detectedNotes.length} 个音符`;
        leftStatusCard.classList.remove('hidden');
      }

      // 自动显示中间切换栏并切换至五线谱大图定位与校对工作台
      const centerSwitcher = document.getElementById('centerViewSwitcher');
      if (centerSwitcher) {
        centerSwitcher.classList.remove('hidden');
        centerSwitcher.classList.add('flex');
      }
      switchCenterView('omr');
      renderOmrCanvas();
      updateOmrToolbarBadge();

      const tiltInfo = Math.abs(detectedTiltAngle) >= 0.4
        ? `📐 倾斜校正: ${detectedTiltAngle > 0 ? '+' : ''}${detectedTiltAngle.toFixed(1)}°`
        : `📐 谱面水平度良好`;
      const statsBadgeEl = document.getElementById('omrStatsBadge');
      if (statsBadgeEl) {
        statsBadgeEl.innerHTML =
          `<span>✅ 识别成功：${tiltInfo} · 定位 ${staffSystems.length} 组谱表，提取 ${detectedNotes.length} 个音符（支持在大图上拉框智能框选补音）</span>`;
      }

      // 同步全局主乐谱简谱
      STATE.notes = detectedNotes.map(n => ({ midi: n.midi, duration: n.duration, isRest: false, confidence: n.confidence }));
      updateHeaderLabels();
      renderJianpuScore();
      syncRawTextFromNotes();
      showToast(`五线谱已展开！已高精提取 ${detectedNotes.length} 个音符，支持在大图交互微调`, 'success');
    }

    function switchCenterView(view) {
      const jianpuWs = document.getElementById('centerJianpuWorkspace');
      const omrWs = document.getElementById('centerOmrWorkspace');
      const btnJianpu = document.getElementById('btnViewJianpu');
      const btnOmr = document.getElementById('btnViewOmr');
      const omrBottomDock = document.getElementById('omrBottomDock');
      const playbackExportDock = document.getElementById('playbackExportDock');
      const noteEditorBar = document.getElementById('noteEditorBar');

      const activeClass = 'px-4 py-1.5 rounded-xl text-xs font-bold transition bg-indigo-600 text-white shadow-xs cursor-pointer';
      const inactiveClass = 'px-4 py-1.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition cursor-pointer flex items-center space-x-1';

      if (view === 'omr') {
        if (!STATE.omrData || !STATE.omrData.img) {
          showToast('请先在左侧上传五线谱图片或选择测试示例', 'info');
          return;
        }
        if (omrWs) omrWs.classList.remove('hidden');
        if (jianpuWs) jianpuWs.classList.add('hidden');
        if (btnOmr) btnOmr.className = activeClass;
        if (btnJianpu) btnJianpu.className = inactiveClass;

        // 底部悬浮控制台：切换为浅色修谱底栏，隐藏播放/导出栏与音符编辑栏
        if (omrBottomDock) omrBottomDock.classList.remove('hidden');
        if (playbackExportDock) playbackExportDock.classList.add('hidden');
        if (noteEditorBar) noteEditorBar.classList.add('hidden');

        renderOmrCanvas();
        updateOmrToolbarBadge();
      } else {
        if (jianpuWs) jianpuWs.classList.remove('hidden');
        if (omrWs) omrWs.classList.add('hidden');
        if (btnJianpu) btnJianpu.className = activeClass;
        if (btnOmr) btnOmr.className = inactiveClass;

        // 底部悬浮控制台：切换为播放/导出栏，隐藏修谱底栏
        if (omrBottomDock) omrBottomDock.classList.add('hidden');
        if (playbackExportDock) playbackExportDock.classList.remove('hidden');

        renderJianpuScore();
      }
    }

    // 确认五线谱校对完成，一键切换成简谱
    function confirmOmrAndSwitchToJianpu() {
      if (STATE.omrData && STATE.omrData.notes) {
        STATE.notes = STATE.omrData.notes.map(n => ({ midi: n.midi, duration: n.duration, isRest: false }));
      }
      updateHeaderLabels();
      renderJianpuScore();
      syncRawTextFromNotes();
      switchCenterView('jianpu');
      showToast('🎉 谱面已确认！已为您生成出版级简谱', 'success');
    }"""

    if target_end_marker in content:
        content = content.replace(target_end_marker, replacement_end_block)
    else:
        print(f"Warning: target_end_marker not found in {filepath}")

    # Also handle if staffSystems.length === 0 in processSheetImage, switch to OMR so canvas renders image
    zero_systems_old = """      if (staffSystems.length === 0) {
        showToast('未能自动检测到标准五线谱横线，请确认图片平整或使用高灵敏模式', 'warning');
        STATE.omrData = { img: offCanvas, systems: [], notes: [], selectedNoteIndex: null, selectedNoteIndices: [], binary, binaryW: w, binaryH: h };
        renderOmrCanvas();
        return;
      }"""

    zero_systems_new = """      if (staffSystems.length === 0) {
        showToast('未能自动检测到标准五线谱横线，请确认图片平整或使用高灵敏模式', 'warning');
        STATE.omrData = { img: offCanvas, systems: [], notes: [], selectedNoteIndex: null, selectedNoteIndices: [], binary, binaryW: w, binaryH: h };
        const centerSwitcher = document.getElementById('centerViewSwitcher');
        if (centerSwitcher) {
          centerSwitcher.classList.remove('hidden');
          centerSwitcher.classList.add('flex');
        }
        switchCenterView('omr');
        renderOmrCanvas();
        return;
      }"""

    if zero_systems_old in content:
        content = content.replace(zero_systems_old, zero_systems_new)

    # 2. Check if export functions exist. If not, add them right before openPreviewModal
    if "function exportJianpuSvg" not in content:
        export_block = """    /**
     * ============================================================================
     * 10. 高保真导出 (PNG 高清图 / 矢量 SVG / 标准 MIDI / MusicXML / 纯文本代码)
     * ============================================================================
     */
    function exportJianpuSvg() {
      const svgEl = document.getElementById('jianpuScoreSvg');
      if (!svgEl) {
        showToast('没有可导出的简谱', 'warning');
        return;
      }
      const title = document.getElementById('scoreTitleInput')?.value || '简谱乐谱';
      const keyStr = document.getElementById('headerKeyDisplay')?.textContent || `1=${STATE.key}`;
      const timeStr = document.getElementById('headerTimeDisplay')?.textContent || STATE.timeSig;
      const bpmStr = `♩ = ${STATE.bpm}`;

      const svgClone = svgEl.cloneNode(true);
      const vb = svgEl.viewBox?.baseVal || { width: 680, height: 400 };
      const headerH = 110;
      const totalW = vb.width || 680;
      const totalH = (vb.height || 400) + headerH;

      let fullSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + totalW + ' ' + totalH + '" width="100%" height="100%">\\n';
      fullSvg += '  <style>\\n';
      fullSvg += '    text { font-family: "JetBrains Mono", "Noto Sans SC", sans-serif; }\\n';
      fullSvg += '    .score-title { font-family: "Noto Serif SC", serif; font-size: 26px; font-weight: bold; fill: #0f172a; text-anchor: middle; }\\n';
      fullSvg += '    .score-meta { font-size: 14px; font-weight: 600; fill: #334155; }\\n';
      fullSvg += '  </style>\\n';
      fullSvg += '  <rect width="100%" height="100%" fill="#ffffff"/>\\n';
      fullSvg += '  <text x="' + (totalW / 2) + '" y="48" class="score-title">' + title + '</text>\\n';
      fullSvg += '  <text x="40" y="86" class="score-meta" text-anchor="start">' + keyStr + '   ' + timeStr + '</text>\\n';
      fullSvg += '  <text x="' + (totalW - 40) + '" y="86" class="score-meta" text-anchor="end">' + bpmStr + '</text>\\n';
      fullSvg += '  <line x1="40" y1="102" x2="' + (totalW - 40) + '" y2="102" stroke="#cbd5e1" stroke-width="1"/>\\n';
      fullSvg += '  <g transform="translate(0, ' + headerH + ')">\\n';
      fullSvg += svgClone.innerHTML;
      fullSvg += '\\n  </g>\\n</svg>';

      const blob = new Blob([fullSvg], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.download = `${title}_简谱.svg`;
      link.href = url;
      link.click();
      URL.revokeObjectURL(url);
      showToast('已导出矢量 SVG 乐谱文件！', 'success');
    }

    function exportMusicXml() {
      if (!STATE.notes || STATE.notes.length === 0) {
        showToast('没有可导出的乐谱音符', 'warning');
        return;
      }
      const title = document.getElementById('scoreTitleInput')?.value || '简谱乐谱';
      const [beats, beatType] = STATE.timeSig.split('/').map(Number);
      const divisions = 4;

      const fifthsMap = {
        'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6,
        'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5
      };
      const fifths = fifthsMap[STATE.key] || 0;

      const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
      function midiToXmlPitch(midi) {
        const octave = Math.floor(midi / 12) - 1;
        const noteIdx = midi % 12;
        const rawName = noteNames[noteIdx];
        const step = rawName.charAt(0);
        const alter = rawName.includes('#') ? 1 : 0;
        return { step, alter, octave };
      }

      function getXmlNoteType(duration) {
        if (duration >= 4) return 'whole';
        if (duration >= 2) return 'half';
        if (duration >= 1) return 'quarter';
        if (duration >= 0.5) return 'eighth';
        return '16th';
      }

      let xml = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\\n';
      xml += '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\\n';
      xml += '<score-partwise version="3.1">\\n';
      xml += '  <work><work-title>' + title + '</work-title></work>\\n';
      xml += '  <part-list>\\n';
      xml += '    <score-part id="P1">\\n';
      xml += '      <part-name>简谱主旋律</part-name>\\n';
      xml += '    </score-part>\\n';
      xml += '  </part-list>\\n';
      xml += '  <part id="P1">\\n';

      let measureNum = 1;
      let measureBeatSum = 0;
      let currentMeasureNotes = [];
      const measureCapacity = beats * (4 / beatType);

      function flushMeasure() {
        xml += '    <measure number="' + measureNum + '">\\n';
        if (measureNum === 1) {
          xml += '      <attributes>\\n';
          xml += '        <divisions>' + divisions + '</divisions>\\n';
          xml += '        <key><fifths>' + fifths + '</fifths></key>\\n';
          xml += '        <time><beats>' + beats + '</beats><beat-type>' + beatType + '</beat-type></time>\\n';
          xml += '        <clef><sign>G</sign><line>2</line></clef>\\n';
          xml += '      </attributes>\\n';
          xml += '      <direction placement="above">\\n';
          xml += '        <sound tempo="' + STATE.bpm + '"/>\\n';
          xml += '      </direction>\\n';
        }

        for (const n of currentMeasureNotes) {
          xml += '      <note>\\n';
          if (n.isRest || n.midi <= 0) {
            xml += '        <rest/>\\n';
          } else {
            const p = midiToXmlPitch(n.midi);
            xml += '        <pitch>\\n';
            xml += '          <step>' + p.step + '</step>\\n';
            if (p.alter !== 0) xml += '          <alter>' + p.alter + '</alter>\\n';
            xml += '          <octave>' + p.octave + '</octave>\\n';
            xml += '        </pitch>\\n';
          }
          const durDiv = Math.max(1, Math.round(n.duration * divisions));
          xml += '        <duration>' + durDiv + '</duration>\\n';
          xml += '        <type>' + getXmlNoteType(n.duration) + '</type>\\n';
          if (n.lyric && n.lyric.trim()) {
            xml += '        <lyric><text>' + n.lyric.trim() + '</text></lyric>\\n';
          }
          xml += '      </note>\\n';
        }
        xml += '    </measure>\\n';
        measureNum++;
        measureBeatSum = 0;
        currentMeasureNotes = [];
      }

      for (const note of STATE.notes) {
        currentMeasureNotes.push(note);
        measureBeatSum += note.duration;
        if (measureBeatSum >= measureCapacity - 0.05) {
          flushMeasure();
        }
      }
      if (currentMeasureNotes.length > 0) {
        flushMeasure();
      }

      xml += '  </part>\\n';
      xml += '</score-partwise>\\n';

      const blob = new Blob([xml], { type: 'application/vnd.recordare.musicxml+xml' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.download = `${title}.musicxml`;
      link.href = url;
      link.click();
      URL.revokeObjectURL(url);
      showToast('已导出标准 MusicXML 乐谱文件！', 'success');
    }

    function exportJianpuPng() {
      const svgEl = document.getElementById('jianpuScoreSvg');
      if (!svgEl) {
        showToast('没有可导出的简谱', 'warning');
        return;
      }
      const title = document.getElementById('scoreTitleInput')?.value || '简谱乐谱';
      const keyStr = document.getElementById('headerKeyDisplay')?.textContent || `1=${STATE.key}`;
      const timeStr = document.getElementById('headerTimeDisplay')?.textContent || STATE.timeSig;
      const bpmStr = `♩ = ${STATE.bpm}`;

      const svgClone = svgEl.cloneNode(true);
      const vb = svgEl.viewBox?.baseVal || { width: 680, height: 400 };
      const headerHeight = 100;
      const totalW = vb.width || 680;
      const totalH = (vb.height || 400) + headerHeight;

      const canvas = document.createElement('canvas');
      canvas.width = totalW * 2;
      canvas.height = totalH * 2;
      const ctx = canvas.getContext('2d');
      ctx.scale(2, 2);

      // 背景与标题
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, totalW, totalH);
      ctx.fillStyle = '#0f172a';
      ctx.font = 'bold 24px "Noto Serif SC", serif';
      ctx.textAlign = 'center';
      ctx.fillText(title, totalW / 2, 44);

      ctx.font = 'bold 13px "JetBrains Mono", sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(`${keyStr}   ${timeStr}`, 32, 78);
      ctx.textAlign = 'right';
      ctx.fillText(bpmStr, totalW - 32, 78);

      const svgData = new XMLSerializer().serializeToString(svgClone);
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, headerHeight, vb.width || 680, vb.height || 400);
        const link = document.createElement('a');
        link.download = `${title}_简谱.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        showToast('已导出高清出版级简谱图片！', 'success');
      };
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgData);
    }

    function exportMidiFile() {
      if (STATE.notes.length === 0) return;
      const tpq = 480;
      const tempoMicrosec = Math.round(60000000 / STATE.bpm);

      const trackEvents = [];
      trackEvents.push(0x00, 0xFF, 0x51, 0x03, (tempoMicrosec >> 16) & 0xFF, (tempoMicrosec >> 8) & 0xFF, tempoMicrosec & 0xFF);

      function writeVarLen(val) {
        let buffer = val & 0x7F;
        const bytes = [];
        while ((val >>= 7) > 0) {
          buffer <<= 8;
          buffer |= ((val & 0x7F) | 0x80);
        }
        while (true) {
          bytes.push(buffer & 0xFF);
          if (buffer & 0x80) buffer >>= 8;
          else break;
        }
        return bytes;
      }

      let pendingRestTicks = 0;
      for (const n of STATE.notes) {
        const ticks = Math.round(n.duration * tpq);
        if (n.isRest || n.midi <= 0) {
          pendingRestTicks += ticks;
        } else {
          trackEvents.push(...writeVarLen(pendingRestTicks), 0x90, n.midi & 0x7F, 0x64);
          trackEvents.push(...writeVarLen(ticks), 0x80, n.midi & 0x7F, 0x00);
          pendingRestTicks = 0;
        }
      }
      trackEvents.push(0x00, 0xFF, 0x2F, 0x00);

      const header = [
        0x4D, 0x54, 0x68, 0x64,
        0x00, 0x00, 0x00, 0x06,
        0x00, 0x00,
        0x00, 0x01,
        (tpq >> 8) & 0xFF, tpq & 0xFF
      ];

      const tLen = trackEvents.length;
      const trackHeader = [
        0x4D, 0x54, 0x72, 0x6B,
        (tLen >> 24) & 0xFF, (tLen >> 16) & 0xFF, (tLen >> 8) & 0xFF, tLen & 0xFF
      ];

      const midiBytes = new Uint8Array([...header, ...trackHeader, ...trackEvents]);
      const blob = new Blob([midiBytes], { type: 'audio/midi' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${document.getElementById('scoreTitleInput')?.value || 'jianpu'}.mid`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('标准 MIDI 乐谱文件已导出！', 'success');
    }

    function copyJianpuText() {
      const title = document.getElementById('scoreTitleInput')?.value || '未命名简谱';
      const header = `《${title}》 | 1=${STATE.key} | ${STATE.timeSig} | ♩=${STATE.bpm}`;
      const body = generateJianpuTextString();
      const fullText = `${header}\\n${body}`;

      const textarea = document.createElement('textarea');
      textarea.value = fullText;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast('简谱文本代码已成功复制到剪贴板！', 'success');
    }\n\n"""

        preview_marker = "    function openPreviewModal(type) {"
        if preview_marker in content:
            content = content.replace(preview_marker, export_block + preview_marker)
        else:
            print(f"Warning: preview_marker not found in {filepath}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Successfully fixed {filepath}!")
    return True

if __name__ == '__main__':
    targets = ['index.html', 'jianpu_studio.html']
    download_copy = '/Users/oneriver/Downloads/jianpu_studio.html'
    if os.path.exists(download_copy):
        targets.append(download_copy)

    success = True
    for t in targets:
        if not fix_file(t):
            success = False

    if success:
        print("All targets successfully fixed!")
        sys.exit(0)
    else:
        sys.exit(1)
