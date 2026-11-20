// Comprehensive Unit Test Suite for Audio Transcription and OMR upgrades
const assert = require('assert');

console.log('=== Running Unit Test Suite for Jianpu Studio Upgrades ===\n');

// -------------------------------------------------------------
// 1. Audio Algorithms: detectPitchYINCandidates & Viterbi
// -------------------------------------------------------------
function detectPitchYINCandidates(buffer, sampleRate, energy = 0.1) {
  const halfLen = Math.floor(buffer.length / 2);
  const minTau = Math.max(2, Math.floor(sampleRate / 1050)); // ~1046Hz
  const maxTau = Math.min(halfLen - 2, Math.floor(sampleRate / 68)); // ~65Hz
  const yinBuffer = new Float32Array(maxTau + 2);

  // 1. Difference function with stride 2 for efficiency
  for (let tau = 0; tau <= maxTau + 1; tau++) {
    let sum = 0;
    for (let i = 0; i < halfLen; i += 2) {
      const delta = buffer[i] - buffer[i + tau];
      sum += delta * delta;
    }
    yinBuffer[tau] = sum * 2;
  }

  // 2. CMNDF
  yinBuffer[0] = 1;
  let runningSum = 0;
  for (let tau = 1; tau <= maxTau + 1; tau++) {
    runningSum += yinBuffer[tau];
    yinBuffer[tau] *= tau / (runningSum || 1);
  }

  // 3. Collect local minima candidates
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

  // Sort by cmndf ascending
  candidates.sort((a, b) => a.cmndf - b.cmndf);
  // Keep top 3-5 candidates
  return candidates.slice(0, 5);
}

function viterbiPitchTracking(framesData, silenceThreshold = 0.01) {
  const T = framesData.length;
  if (T === 0) return [];

  // DP table: dp[t][s], backpointer[t][s]
  // State 0: Unvoiced (-1)
  // State 1..K: Candidates
  const dp = [];
  const bp = [];

  for (let t = 0; t < T; t++) {
    const frame = framesData[t];
    const cands = frame.candidates || [];
    const numStates = 1 + cands.length; // state 0 is unvoiced
    dp[t] = new Float32Array(numStates);
    bp[t] = new Int32Array(numStates);

    const energy = frame.energy || 0;
    const isSilent = energy < silenceThreshold;

    for (let s = 0; s < numStates; s++) {
      // 1. Emission cost
      let emissionCost = 0;
      if (s === 0) {
        // Unvoiced state
        emissionCost = isSilent ? (energy / silenceThreshold) * 0.1 : 2.5 + (energy / silenceThreshold) * 1.5;
      } else {
        const cand = cands[s - 1];
        emissionCost = (1 - cand.clarity) * 1.8 + cand.cmndf * 1.2;
        if (isSilent) emissionCost += 3.5;
      }

      // 2. Transition cost from t-1
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
            transCost = 1.1; // Voiced/Unvoiced switch penalty
          } else {
            const prevCand = prevCands[p - 1];
            const currCand = cands[s - 1];
            const deltaMidi = Math.abs(currCand.midi - prevCand.midi);

            // Small continuous step
            transCost = deltaMidi * 0.12;

            // Octave leap penalty (around 12 or 24 semitones)
            if (Math.abs(deltaMidi - 12) < 1.2 || Math.abs(deltaMidi - 24) < 1.2) {
              transCost += 2.8; // Penalize octave errors unless clarity is overwhelmingly higher
            } else if (deltaMidi > 12) {
              transCost += (deltaMidi - 12) * 0.35; // Heavy penalty for extreme jumps
            } else if (deltaMidi <= 0.8) {
              transCost = deltaMidi * 0.02; // Very low penalty for vibrato
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

  // Backtrack
  let bestFinalState = 0;
  let minFinalCost = Infinity;
  for (let s = 0; s < dp[T - 1].length; s++) {
    if (dp[T - 1][s] < minFinalCost) {
      minFinalCost = dp[T - 1][s];
      bestFinalState = s;
    }
  }

  const result = new Array(T);
  let curState = bestFinalState;
  for (let t = T - 1; t >= 0; t--) {
    if (curState === 0) {
      result[t] = { midi: -1, freq: -1, clarity: 0, rawMidi: -1 };
    } else {
      const cand = framesData[t].candidates[curState - 1];
      result[t] = {
        midi: Math.round(cand.midi),
        rawMidi: cand.midi,
        freq: cand.freq,
        clarity: cand.clarity
      };
    }
    curState = bp[t][curState];
  }

  return result;
}

// Test Audio Sine Wave Pitch Detection
console.log('Testing Audio Pitch Tracking with Multi-Candidate & Viterbi...');
const sampleRate = 44100;
const frameSize = 2048;
const hopSize = 512;
const testFreqs = [261.63, 329.63, 392.00]; // C4, E4, G4

const totalSamples = sampleRate * 1.5; // 1.5s
const testAudio = new Float32Array(totalSamples);
for (let i = 0; i < totalSamples; i++) {
  const t = i / sampleRate;
  let f = 0;
  if (t < 0.5) f = testFreqs[0];
  else if (t < 1.0) f = testFreqs[1];
  else f = testFreqs[2];

  // Add fundamental + slight 2nd harmonic
  testAudio[i] = 0.7 * Math.sin(2 * Math.PI * f * t) + 0.2 * Math.sin(4 * Math.PI * f * t);
}

const framesData = [];
for (let i = 0; i + frameSize < totalSamples; i += hopSize) {
  const slice = testAudio.subarray(i, i + frameSize);
  let sumSq = 0;
  for (let j = 0; j < frameSize; j += 2) sumSq += slice[j] * slice[j];
  const energy = Math.sqrt((sumSq * 2) / frameSize);
  const candidates = detectPitchYINCandidates(slice, sampleRate, energy);
  framesData.push({ time: i / sampleRate, energy, candidates });
}

const decodedPitches = viterbiPitchTracking(framesData, 0.05);
assert(decodedPitches.length > 0, 'Decoded pitches should not be empty');

// Check C4 (MIDI 60), E4 (MIDI 64), G4 (MIDI 67)
const midIndex1 = Math.floor(framesData.length * 0.15); // in first note
const midIndex2 = Math.floor(framesData.length * 0.50); // in second note
const midIndex3 = Math.floor(framesData.length * 0.85); // in third note

console.log(`Detected Note 1 MIDI: ${decodedPitches[midIndex1].midi} (Expected ~60 for C4)`);
console.log(`Detected Note 2 MIDI: ${decodedPitches[midIndex2].midi} (Expected ~64 for E4)`);
console.log(`Detected Note 3 MIDI: ${decodedPitches[midIndex3].midi} (Expected ~67 for G4)`);

assert.strictEqual(decodedPitches[midIndex1].midi, 60, 'Note 1 must be MIDI 60 (C4)');
assert.strictEqual(decodedPitches[midIndex2].midi, 64, 'Note 2 must be MIDI 64 (E4)');
assert.strictEqual(decodedPitches[midIndex3].midi, 67, 'Note 3 must be MIDI 67 (G4)');
console.log('✓ Audio Multi-Candidate + Viterbi Pitch Tracking: PASSED\n');


// -------------------------------------------------------------
// 2. OMR Symbol Classification & Scoring
// -------------------------------------------------------------
console.log('Testing OMR Symbol Classification & Notehead Scoring...');

function classifyOmrComponent(comp, sys, d) {
  const aspect = comp.bw / Math.max(1, comp.bh);
  const area = comp.area;
  const density = area / Math.max(1, comp.bw * comp.bh);
  const isHeader = comp.cx < (sys.leftX || (sys.firstInk + d * 3.5)) || (sys.firstBarlineX && comp.cx < sys.firstBarlineX);

  // 1. Barline test: tall vertical line crossing staff
  if (comp.bh >= d * 3.2 && comp.bw <= d * 0.45 && aspect <= 0.16) {
    return { symbolType: 'barline', isNote: false, penalty: 1.0 };
  }

  // 2. Beam test: long horizontal bar
  if (comp.bw >= d * 1.8 && (aspect >= 2.2 || comp.bh <= d * 1.1)) {
    return { symbolType: 'beam', isNote: false, penalty: 1.0 };
  }

  // 3. Clef test: tall symbol in header region
  if (isHeader && comp.bh >= d * 2.5) {
    return { symbolType: 'clef', isNote: false, penalty: 1.0 };
  }

  // 4. Header symbol test (time signature, key signature)
  if (isHeader) {
    if (comp.bh >= d * 1.6 && comp.bw >= d * 0.6) {
      return { symbolType: 'timeSignature', isNote: false, penalty: 1.0 };
    }
    return { symbolType: 'headerSymbol', isNote: false, penalty: 0.9 };
  }

  // 5. Notehead test
  if (comp.bw >= d * 0.65 && comp.bw <= d * 1.7 &&
      comp.bh >= d * 0.55 && comp.bh <= d * 1.5 &&
      aspect >= 0.75 && aspect <= 1.85 &&
      area >= d * d * 0.22 && area <= d * d * 2.2) {
    return { symbolType: 'notehead', isNote: true, penalty: 0 };
  }

  return { symbolType: 'unknown', isNote: false, penalty: 0.8 };
}

function computeNoteheadScore(comp, sys, d, stemSupport = true) {
  const aspect = comp.bw / Math.max(1, comp.bh);
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
        headerPenalty: classification.symbolType.includes('header') || classification.symbolType === 'clef' ? 1 : 0,
        beamPenalty: classification.symbolType === 'beam' ? 1 : 0,
        clefPenalty: classification.symbolType === 'clef' ? 1 : 0
      }
    };
  }

  // Aspect closeness to 1.25
  const geomAspect = 1 - Math.min(1, Math.abs(aspect - 1.25) / 0.8);
  const geomArea = 1 - Math.min(1, Math.abs(area - 0.75 * d * d) / (0.75 * d * d));
  const geometryScore = Math.max(0, geomAspect * 0.55 + geomArea * 0.45);

  // Position on half-line grid
  const step = Math.round((sys.lines[4] - comp.cy) / (d / 2));
  const targetY = sys.lines[4] - step * (d / 2);
  const distY = Math.abs(comp.cy - targetY);
  const staffPositionScore = Math.max(0, 1 - Math.min(1, distY / (d * 0.4)));

  const stemScore = stemSupport ? 1.0 : 0.4;
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

// Test cases
const d = 16;
const sys = {
  lines: [100, 116, 132, 148, 164],
  d: 16,
  firstInk: 40,
  leftX: 40 + 16 * 3.5, // 96
  firstBarlineX: 180
};

// 1. Treble Clef in header
const trebleClefComp = { cx: 60, cy: 132, bw: 24, bh: 96, area: 850 }; // bh = 6d
const clefResult = computeNoteheadScore(trebleClefComp, sys, d);
console.log('Clef Classification:', clefResult.symbolType, 'isNote:', clefResult.isNote, 'conf:', clefResult.confidence);
assert(!clefResult.isNote, 'Treble clef must NOT be recognized as a note');
assert.strictEqual(clefResult.symbolType, 'clef');

// 2. Horizontal Beam
const beamComp = { cx: 250, cy: 110, bw: 64, bh: 8, area: 500 }; // bw = 4d, bh = 0.5d
const beamResult = computeNoteheadScore(beamComp, sys, d);
console.log('Beam Classification:', beamResult.symbolType, 'isNote:', beamResult.isNote, 'conf:', beamResult.confidence);
assert(!beamResult.isNote, 'Beam must NOT be recognized as a note');
assert.strictEqual(beamResult.symbolType, 'beam');

// 3. Genuine Notehead
const noteheadComp = { cx: 220, cy: 148, bw: 19, bh: 15, area: 215 }; // on line 3 (cy=148)
const noteResult = computeNoteheadScore(noteheadComp, sys, d, true);
console.log('Notehead Classification:', noteResult.symbolType, 'isNote:', noteResult.isNote, 'conf:', noteResult.confidence);
assert(noteResult.isNote, 'Genuine notehead MUST be recognized as a note');
assert(noteResult.confidence >= 0.85, 'Genuine notehead confidence must be high');
assert.strictEqual(noteResult.step, 2, 'Note on line 3 must have step 2');
console.log('✓ OMR Symbol Classification & Scoring: PASSED\n');

// -------------------------------------------------------------
// 3. Beat Grid Quantization Test
// -------------------------------------------------------------
console.log('Testing Beat Grid Quantization without Drift...');
function quantizeAudioNotes(rawEvents, bpm, quantGrid = 0.5, meterNum = 4, meterDen = 4) {
  const secPerBeat = 60 / bpm;
  const gridStepSec = secPerBeat * quantGrid;
  const notes = [];

  let curTimeSec = 0;
  for (const ev of rawEvents) {
    if (ev.durationSec < 0.06) {
      curTimeSec += ev.durationSec;
      continue;
    }

    const startSec = curTimeSec;
    const endSec = curTimeSec + ev.durationSec;
    curTimeSec = endSec;

    // Grid ticks
    const startTick = Math.round(startSec / gridStepSec);
    const endTick = Math.max(startTick + 1, Math.round(endSec / gridStepSec));
    const durationBeats = (endTick - startTick) * quantGrid;

    // Check gap from previous note
    if (notes.length > 0) {
      const prev = notes[notes.length - 1];
      const prevEndTick = Math.round(prev.endTime / gridStepSec);
      if (startTick > prevEndTick) {
        const gapBeats = (startTick - prevEndTick) * quantGrid;
        if (gapBeats >= quantGrid) {
          notes.push({
            midi: 0,
            duration: gapBeats,
            isRest: true,
            confidence: 1.0,
            startTime: prev.endTime,
            endTime: startSec
          });
        }
      }
    }

    if (ev.midi === -1) {
      notes.push({
        midi: 0,
        duration: durationBeats,
        isRest: true,
        confidence: 0.95,
        startTime: startSec,
        endTime: endSec
      });
    } else {
      notes.push({
        midi: ev.midi,
        duration: durationBeats,
        isRest: false,
        confidence: ev.confidence || 0.9,
        startTime: startSec,
        endTime: endSec,
        pitchConfidence: ev.pitchConfidence || 0.9,
        onsetConfidence: ev.onsetConfidence || 0.9
      });
    }
  }

  return notes;
}

// 4 quarter notes at 120 BPM (0.5s each)
const rawEvents = [
  { midi: 60, durationSec: 0.51, confidence: 0.95 },
  { midi: 62, durationSec: 0.49, confidence: 0.92 },
  { midi: 64, durationSec: 0.50, confidence: 0.96 },
  { midi: 65, durationSec: 0.52, confidence: 0.94 }
];
const quantized = quantizeAudioNotes(rawEvents, 120, 0.5);
console.log('Quantized Notes Durations:', quantized.map(n => n.duration));
assert.strictEqual(quantized.length, 4, 'Should have 4 notes');
quantized.forEach(n => {
  assert.strictEqual(n.duration, 1.0, 'Each note at 120BPM with ~0.5s should quantize to 1.0 beat');
  assert(n.confidence !== undefined, 'Note must contain confidence metadata');
});
console.log('✓ Beat Grid Quantization: PASSED\n');

console.log('=== ALL UNIT TESTS PASSED SUCCESSFULLY! ===');
