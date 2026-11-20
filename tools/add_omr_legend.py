# -*- coding: utf-8 -*-
"""
Add color legend for OMR sheet recognition:
- Explains what different color boxes mean:
  1. Emerald Green: High confidence note (>= 84%)
  2. Amber Yellow: Medium confidence note (70% ~ 84%, check recommended)
  3. Coral Red: Low confidence note (< 70%, suspected noise / artifact)
  4. Indigo Blue: Currently selected / multi-selected note
"""

import sys
import os

def update_file(filepath):
    print(f"Updating {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update HTML in centerOmrWorkspace to add the color legend
    old_info_block = """          <!-- 交互修谱指南与识别状态提示 (各放一行，上下全宽展示) -->
          <div class="flex flex-col space-y-2.5 w-full">
            <!-- 第 1 行：操作指南 -->
            <div class="text-xs text-slate-600 bg-slate-50/90 border border-slate-200/80 rounded-xl px-3.5 py-2.5 leading-relaxed w-full">
              <span class="font-semibold text-indigo-700">💡 交互修谱指南：</span>
              点击绿框选中音符；按住音符上下拖动可直接变音并实时试听；点击空白区域直接补音；<span class="font-semibold text-violet-700">按住鼠标拖拽拉框可自动批量提取框内全部音符</span>；按键盘 Delete 键删除杂质。
            </div>
            <!-- 第 2 行：识别状态与统计 -->
            <div id="omrStatsBadge" class="text-xs text-emerald-800 bg-emerald-50/90 border border-emerald-200 rounded-xl px-3.5 py-2 flex items-center justify-between w-full">
              <span>✅ 已识别到五线谱组与音符（支持在大图上拉框智能框选补音）</span>
            </div>
          </div>"""

    new_info_block = """          <!-- 交互修谱指南、颜色图例与识别状态提示 (上下全宽展示) -->
          <div class="flex flex-col space-y-2.5 w-full">
            <!-- 第 1 行：操作指南 -->
            <div class="text-xs text-slate-600 bg-slate-50/90 border border-slate-200/80 rounded-xl px-3.5 py-2.5 leading-relaxed w-full">
              <span class="font-semibold text-indigo-700">💡 交互修谱指南：</span>
              点击音符选中；按住音符上下拖动可直接变音并实时试听；点击空白区域直接补音；<span class="font-semibold text-violet-700">按住鼠标拖拽拉框可批量框选或自动补提取音符</span>；按键盘 Delete 键删除杂质。
            </div>
            <!-- 第 2 行：标注框颜色图例说明 (清晰说明不同颜色框框代表的含义) -->
            <div class="flex flex-wrap items-center justify-between gap-2.5 text-xs bg-slate-50/90 border border-slate-200/80 rounded-xl px-3.5 py-2 w-full text-slate-700">
              <span class="font-semibold text-slate-800 flex items-center gap-1.5 flex-shrink-0">
                <svg class="w-3.5 h-3.5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"/></svg>
                <span>标注框颜色图例：</span>
              </span>
              <div class="flex flex-wrap items-center gap-2.5 sm:gap-4 text-[11px] sm:text-xs">
                <span class="inline-flex items-center gap-1.5" title="形态与五线谱高度吻合，极高置信度 (≥84%)">
                  <span class="w-3 h-3 rounded-xs border-2 border-emerald-500 bg-emerald-500/20 inline-block flex-shrink-0"></span>
                  <span class="font-medium text-emerald-800">绿框：高置信度音符</span>
                </span>
                <span class="inline-flex items-center gap-1.5" title="形态略微偏离或跨线模糊，中置信度 (70%~84%)，建议人工复核">
                  <span class="w-3 h-3 rounded-xs border-2 border-amber-500 bg-amber-500/20 inline-block flex-shrink-0"></span>
                  <span class="font-medium text-amber-800">黄框：中置信度 (建议核对)</span>
                </span>
                <span class="inline-flex items-center gap-1.5" title="疑似污渍、文字干扰或低置信度识别 (<70%)，可微调或按 Delete 删除">
                  <span class="w-3 h-3 rounded-xs border-2 border-rose-500 bg-rose-500/20 inline-block flex-shrink-0"></span>
                  <span class="font-medium text-rose-800">红框：低置信度/疑似杂质</span>
                </span>
                <span class="inline-flex items-center gap-1.5" title="当前选中的音符目标，支持上下拖拽变音、切换时值或批量删除">
                  <span class="w-3 h-3 rounded-xs border-2 border-indigo-600 bg-indigo-600/25 inline-block flex-shrink-0"></span>
                  <span class="font-medium text-indigo-800">蓝框：当前选中 / 框选</span>
                </span>
              </div>
            </div>
            <!-- 第 3 行：识别状态与统计 -->
            <div id="omrStatsBadge" class="text-xs text-emerald-800 bg-emerald-50/90 border border-emerald-200 rounded-xl px-3.5 py-2 flex items-center justify-between w-full">
              <span>✅ 已识别到五线谱组与音符（支持在大图上拉框智能框选补音）</span>
            </div>
          </div>"""

    if old_info_block in content:
        content = content.replace(old_info_block, new_info_block)
    else:
        print(f"Warning: old_info_block not found in {filepath}")

    # 2. Update renderOmrCanvas box drawing to make selected box indigo blue (#4f46e5)
    # and badge background consistent with confidence / selection
    old_canvas_render = """        if (isSel) {
          // 选中状态：明亮琥珀金发光框与拖拽手柄
          ctx.fillStyle = 'rgba(245, 158, 11, 0.22)';
          ctx.fillRect(box.x, box.y, box.w, box.h);
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 2.5;
          ctx.strokeRect(box.x, box.y, box.w, box.h);

          // 四角手柄
          ctx.fillStyle = '#f59e0b';
          ctx.fillRect(box.x - 3, box.y - 3, 6, 6);
          ctx.fillRect(box.x + box.w - 3, box.y - 3, 6, 6);
          ctx.fillRect(box.x - 3, box.y + box.h - 3, 6, 6);
          ctx.fillRect(box.x + box.w - 3, box.y + box.h - 3, 6, 6);
        } else {
          // 常规状态：清爽翡翠绿线框
          const confidence = n.confidence ?? 1;
          const lowConfidence = confidence < 0.70;
          const midConfidence = confidence < 0.84;
          ctx.fillStyle = lowConfidence ? 'rgba(239, 68, 68, 0.16)' : (midConfidence ? 'rgba(245, 158, 11, 0.14)' : 'rgba(16, 185, 129, 0.12)');
          ctx.fillRect(box.x, box.y, box.w, box.h);
          ctx.strokeStyle = lowConfidence ? '#ef4444' : (midConfidence ? '#f59e0b' : '#10b981');
          ctx.lineWidth = 1.6;
          ctx.strokeRect(box.x, box.y, box.w, box.h);
        }

        // 音符唱名小浮标 (例如 1, 3, 5̇, 7̣)
        const jianpuInfo = midiToJianpuInfo(n.midi, false);
        const durSymbol = n.duration >= 4 ? '𝅝' : (n.duration >= 2 ? '𝅗𝅥' : (n.duration <= 0.5 ? '♪' : '♩'));
        const labelText = `${jianpuInfo.accidental}${jianpuInfo.text}${durSymbol}`;

        const badgeY = box.y > 22 ? box.y - 5 : box.y + box.h + 14;
        ctx.font = 'bold 12px "JetBrains Mono", sans-serif';
        const txtWidth = ctx.measureText(labelText).width;
        
        ctx.fillStyle = isSel ? '#b45309' : '#047857';"""

    new_canvas_render = """        const confidence = n.confidence ?? 1;
        const lowConfidence = confidence < 0.70;
        const midConfidence = confidence < 0.84;

        if (isSel) {
          // 选中状态：明亮靛蓝发光框与拖拽手柄 (与图例中的蓝框对应)
          ctx.fillStyle = 'rgba(79, 70, 229, 0.22)';
          ctx.fillRect(box.x, box.y, box.w, box.h);
          ctx.strokeStyle = '#4f46e5';
          ctx.lineWidth = 2.5;
          ctx.strokeRect(box.x, box.y, box.w, box.h);

          // 四角手柄
          ctx.fillStyle = '#4f46e5';
          ctx.fillRect(box.x - 3, box.y - 3, 6, 6);
          ctx.fillRect(box.x + box.w - 3, box.y - 3, 6, 6);
          ctx.fillRect(box.x - 3, box.y + box.h - 3, 6, 6);
          ctx.fillRect(box.x + box.w - 3, box.y + box.h - 3, 6, 6);
        } else {
          // 常规状态：依据置信度呈现翡翠绿、琥珀黄、珊瑚红
          ctx.fillStyle = lowConfidence ? 'rgba(239, 68, 68, 0.16)' : (midConfidence ? 'rgba(245, 158, 11, 0.14)' : 'rgba(16, 185, 129, 0.12)');
          ctx.fillRect(box.x, box.y, box.w, box.h);
          ctx.strokeStyle = lowConfidence ? '#ef4444' : (midConfidence ? '#f59e0b' : '#10b981');
          ctx.lineWidth = 1.6;
          ctx.strokeRect(box.x, box.y, box.w, box.h);
        }

        // 音符唱名小浮标 (例如 1, 3, 5̇, 7̣)
        const jianpuInfo = midiToJianpuInfo(n.midi, false);
        const durSymbol = n.duration >= 4 ? '𝅝' : (n.duration >= 2 ? '𝅗𝅥' : (n.duration <= 0.5 ? '♪' : '♩'));
        const labelText = `${jianpuInfo.accidental}${jianpuInfo.text}${durSymbol}`;

        const badgeY = box.y > 22 ? box.y - 5 : box.y + box.h + 14;
        ctx.font = 'bold 12px "JetBrains Mono", sans-serif';
        const txtWidth = ctx.measureText(labelText).width;
        
        ctx.fillStyle = isSel ? '#4338ca' : (lowConfidence ? '#dc2626' : (midConfidence ? '#d97706' : '#047857'));"""

    if old_canvas_render in content:
        content = content.replace(old_canvas_render, new_canvas_render)
    else:
        print(f"Warning: old_canvas_render not found in {filepath}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Successfully updated {filepath}!")
    return True

if __name__ == '__main__':
    targets = ['index.html', 'jianpu_studio.html']
    download_copy = '/Users/oneriver/Downloads/jianpu_studio.html'
    if os.path.exists(download_copy):
        targets.append(download_copy)

    success = True
    for t in targets:
        if not update_file(t):
            success = False

    if success:
        print("All targets successfully updated with OMR color legend!")
        sys.exit(0)
    else:
        sys.exit(1)
