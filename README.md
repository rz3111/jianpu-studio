# 简谱工坊 · Jianpu Studio

> 现代艺术智能转谱工坊 · 浏览器开箱即用的“哼唱转简谱 + 五线谱图片光学识谱 (OMR) + 简谱排版试听一体化引擎”

[![Online Demo](https://img.shields.io/badge/Online%20Demo-Live%20Preview-brightgreen.svg)](https://rz3111.github.io/jianpu-studio/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Pure Frontend](https://img.shields.io/badge/Stack-Pure%20HTML%2FJS%2FCSS-emerald.svg)](index.html)
[![Web Audio API](https://img.shields.io/badge/Web%20Audio-Powered-indigo.svg)](index.html)

**简谱工坊 (Jianpu Studio)** 是一款专为中国音乐爱好者、民乐演奏者、流行弹唱歌手与音乐教师打造的现代开源音乐转谱工作站。无需安装复杂环境、无需后端服务器，一个 HTML 单文件在浏览器中即可运行。

---

## ✨ 核心特性

- 🎙️ **音频 / 哼唱转简谱 (Audio to Jianpu)**
  - 支持麦克风实时清唱录音或上传 MP3 / WAV / M4A / FLAC 音频。
  - **前置预加重滤波与自适应底噪门限 (借鉴 Spotify Basic Pitch 噪声能量控制)**：自动滤除麦克风直流偏置、低频喷麦爆音与环境底噪，避免微弱杂音产生虚假碎音符。
  - 动态全景音频波形（Waveform）与音高水流谱（Pitch Contour / Piano-Roll）。
  - 内置基于改进型 **YIN / pYIN** 差分算法的高精度单音检测与八度跳变抑制。
  - **标准乐理分级量化 (Adaptive Quantization)**：智能匹配四分音符、八分音符、十六分音符、附点音符与整洁休止符合并，旋律更规整地道。
  - **智能调式吸附（Scale Snapping）**：自动将歌唱微弱偏音吸附到自然大调或中国五声音阶，消除跑调带来的杂音。
  - **智能 BPM 速度测算**：根据起音间隔自动估算合理曲速。

- 🎼 **五线谱图片光学识谱 (Sheet Music OMR to Jianpu)**
  - 支持上传五线谱照片、扫描件或截图（PNG / JPG / WEBP）。
  - **手机拍照自动倾斜矫正 (Deskewing 借鉴 Audiveris)**：基于剪切投影方差极大值法，自动探测乐谱旋转角度（-6° ~ +6°）并在 Canvas 中精准无损扶正，彻底解决拍照倾斜导致谱线识别失败的痛点。
  - 支持高音谱号（Treble 𝄞）与低音谱号（Bass 𝄢）自动映射。
  - 采用 **Otsu 动态大津二值化 + 谱线直方图提取 + 垂直去线 + 椭圆符头形态学识别**。
  - 提供可视化的 OMR 识别标注叠加层，支持放大查看与校准。

- 🎨 **出版级现代简谱排版与编辑器**
  - 超感现代毛玻璃与纸张质感乐谱排版。
  - 完整呈现简谱记谱语法：调号（1=C 等）、拍号（4/4、3/4、2/4、6/8）、音符、高低音点、减时线（八分/十六分音符）、延音线、休止符与小节线。
  - 支持填入歌词，与简谱音符一一对齐。
  - 支持单音选中高亮与实时微调修改。

- 🔊 **Web Audio 实时试听合成**
  - 内置柔和音色合成器，支持连音、休止符精确播放。
  - 播放过程光标平滑跟随高亮正在发声的音符。
  - 支持实时速度调节（BPM）与播放/暂停控制。

- 💾 **多格式导出与互通**
  - 导出高清乐谱图片（PNG / SVG）。
  - 导出通用数字格式（MIDI / MusicXML / 文本谱），可直接导入 MuseScore、Dolce、Finale 等专业编曲软件。

---

## 🚀 快速上手

本项目为纯前端单页面应用（Single-page HTML App），零外部环境依赖。

### 方式一：直接浏览器打开
直接在浏览器中双击打开 `index.html`（或 `jianpu_studio.html`）即可直接体验全部功能。

### 方式二：本地静态服务器
```bash
# 进入项目目录
cd jianpu-studio

# 使用 Python 启动静态文件服务器
python3 -m http.server 8080

# 打开浏览器访问 http://localhost:8080
```

---

## 🛠️ 技术架构

```
jianpu-studio/
├── index.html            # 主工程文件（包含 UI、音高识别引擎、OMR 识别器、简谱排版与 Web Audio 合成器）
├── jianpu_studio.html    # 独立备份分发文件
├── README.md             # 项目说明文档
└── LICENSE               # MIT 开源协议
```

### 核心算法与技术栈
- **UI & 动效**：Tailwind CSS + 现代艺术渐变流体光晕设计
- **音频分析**：Web Audio API + YIN 差分算法 + 抛物线插值 + 连续帧上下文平滑
- **图像识别 (OMR)**：HTML5 Canvas 图像分析 + Otsu 二值化 + 游程统计 + 椭圆形态学
- **声音合成**：Web Audio API `OscillatorNode` + `GainNode` 包络合成

---

## 🤝 致谢与开源生态

本项目在算法设计和功能规划上参考并致敬了以下优秀的开源项目：
- [Audiveris](https://github.com/Audiveris/audiveris) - 经典光学音乐识别 (OMR) 系统
- [oemer](https://github.com/BreezeWhite/oemer) - 基于深度学习的端到端 OMR
- [basic-pitch](https://github.com/spotify/basic-pitch) - Spotify 轻量级音频转谱引擎
- [pitchfinder](https://github.com/peterkhayes/pitchfinder) - Web 音高检测算法合集
- [dolce (悦谱)](https://github.com/lodebar2026/dolce) - 优秀的开源简谱排版与本地 OMR 工具
- [jianpu-ly](https://github.com/ssb22/jianpu-ly) - GNU LilyPond 简谱排版生成器

---

## 📄 开源许可

本项目采用 [MIT License](LICENSE) 授权开源，欢迎自由使用、学习与二次开发。
