#!/usr/bin/env node
/**
 * MIDI generator using Magenta.js (ImprovRNN, DrumsRNN) + programmatic bass/chords.
 *
 * Reads JSON params from stdin, writes 4 MIDI files to the output directory.
 *
 * Usage: echo '{"scale":"Hirajoshi",...}' | node generate_midi.js /tmp/midi-output
 */

const fs = require('fs');
const path = require('path');
const { Note, Chord } = require('tonal');

// Magenta.js imports (server-side Node.js paths)
const mm = require('@magenta/music/node/music_rnn');
const core = require('@magenta/music/node/core');

const IMPROV_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/chord_pitches_improv';
const DRUMS_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/drum_kit_rnn';

const STEPS_PER_QUARTER = 4;
const BARS = 4;
const BEATS_PER_BAR = 4;
const TOTAL_STEPS = BARS * BEATS_PER_BAR * STEPS_PER_QUARTER; // 64

// ── Scale quantization ──────────────────────────────────────────────────

function buildScalePitches(root, intervals, minPitch = 36, maxPitch = 96) {
  const rootMidi = Note.midi(root + '0');
  const pitches = new Set();
  for (let octave = 0; octave < 10; octave++) {
    for (const interval of intervals) {
      const pitch = rootMidi + (octave * 12) + interval;
      if (pitch >= minPitch && pitch <= maxPitch) {
        pitches.add(pitch);
      }
    }
  }
  return Array.from(pitches).sort((a, b) => a - b);
}

function quantizeToScale(pitch, scalePitches) {
  let closest = scalePitches[0];
  let minDist = Math.abs(pitch - closest);
  for (const sp of scalePitches) {
    const dist = Math.abs(pitch - sp);
    if (dist < minDist) {
      minDist = dist;
      closest = sp;
    }
  }
  return closest;
}

// ── Melody generation (ImprovRNN) ───────────────────────────────────────

async function generateMelody(params, scalePitches) {
  const improvRnn = new mm.MusicRNN(IMPROV_CHECKPOINT);
  await improvRnn.initialize();

  // Minimal seed: one note in the scale
  const rootMidi = Note.midi(params.root + '4') || 60;
  const seedPitch = quantizeToScale(rootMidi, scalePitches);

  const seedSequence = {
    ticksPerQuarter: 220,
    totalTime: 0.5,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    notes: [{ pitch: seedPitch, startTime: 0.0, endTime: 0.5, velocity: 100 }],
  };

  const quantizedSeed = core.sequences.quantizeNoteSequence(seedSequence, STEPS_PER_QUARTER);

  const continuation = await improvRnn.continueSequence(
    quantizedSeed,
    TOTAL_STEPS,
    params.temperature,
    params.chords
  );

  // Post-process: quantize to scale + set instrument
  continuation.notes.forEach(n => {
    n.pitch = quantizeToScale(n.pitch, scalePitches);
    n.velocity = n.velocity || 100;
    n.program = params.melody_instrument;
    n.instrument = 0;
  });

  // Set tempo
  continuation.tempos = [{ time: 0, qpm: params.tempo }];

  improvRnn.dispose();
  return continuation;
}

// ── Drums generation (DrumsRNN) ─────────────────────────────────────────

async function generateDrums(params) {
  const drumsRnn = new mm.MusicRNN(DRUMS_CHECKPOINT);
  await drumsRnn.initialize();

  // Minimal seed: kick on beat 1
  const seedSequence = {
    ticksPerQuarter: 220,
    totalTime: 0.5,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    notes: [
      { pitch: 36, startTime: 0.0, endTime: 0.5, isDrum: true, velocity: 100 },
      { pitch: 42, startTime: 0.0, endTime: 0.5, isDrum: true, velocity: 80 },
    ],
  };

  const quantizedSeed = core.sequences.quantizeNoteSequence(seedSequence, STEPS_PER_QUARTER);

  const continuation = await drumsRnn.continueSequence(
    quantizedSeed,
    TOTAL_STEPS,
    params.temperature
  );

  continuation.notes.forEach(n => {
    n.velocity = n.velocity || 100;
    n.isDrum = true;
  });

  continuation.tempos = [{ time: 0, qpm: params.tempo }];

  drumsRnn.dispose();
  return continuation;
}

// ── Bass generation (programmatic) ──────────────────────────────────────

function generateBass(params, scalePitches) {
  const bassPitches = scalePitches.filter(p => p >= 36 && p <= 60);
  const secondsPerBeat = 60.0 / params.tempo;
  const totalBeats = BARS * BEATS_PER_BAR;
  const beatsPerChord = totalBeats / params.chords.length;

  const notes = [];
  const patterns = ['root-fifth', 'walking', 'syncopated'];
  const pattern = patterns[Math.floor(Math.random() * patterns.length)];

  for (let ci = 0; ci < params.chords.length; ci++) {
    const chordInfo = Chord.get(params.chords[ci]);
    const rootNote = chordInfo.tonic || params.root;
    const rootMidi = Note.midi(rootNote + '2') || 48;
    const root = quantizeToScale(rootMidi, bassPitches.length ? bassPitches : scalePitches);
    const fifth = quantizeToScale(rootMidi + 7, bassPitches.length ? bassPitches : scalePitches);

    const chordStartBeat = ci * beatsPerChord;

    if (pattern === 'root-fifth') {
      for (let beat = 0; beat < beatsPerChord; beat++) {
        const pitch = beat % 2 === 0 ? root : fifth;
        const startTime = (chordStartBeat + beat) * secondsPerBeat;
        notes.push({
          pitch, startTime, endTime: startTime + secondsPerBeat * 0.9,
          velocity: 100, program: 32, instrument: 0, isDrum: false,
        });
      }
    } else if (pattern === 'walking') {
      const walkNotes = [root, root + 2, fifth, fifth - 2].map(
        p => quantizeToScale(p, bassPitches.length ? bassPitches : scalePitches)
      );
      for (let beat = 0; beat < beatsPerChord; beat++) {
        const pitch = walkNotes[beat % walkNotes.length];
        const startTime = (chordStartBeat + beat) * secondsPerBeat;
        notes.push({
          pitch, startTime, endTime: startTime + secondsPerBeat * 0.9,
          velocity: 100, program: 32, instrument: 0, isDrum: false,
        });
      }
    } else {
      // syncopated: root on beat, rest, root on and-of-2, rest
      const startBeat1 = chordStartBeat;
      notes.push({
        pitch: root, startTime: startBeat1 * secondsPerBeat,
        endTime: (startBeat1 + 1.5) * secondsPerBeat,
        velocity: 100, program: 32, instrument: 0, isDrum: false,
      });
      if (beatsPerChord >= 3) {
        const startBeat2 = chordStartBeat + 2.5;
        notes.push({
          pitch: fifth, startTime: startBeat2 * secondsPerBeat,
          endTime: (startBeat2 + 1) * secondsPerBeat,
          velocity: 90, program: 32, instrument: 0, isDrum: false,
        });
      }
    }
  }

  return {
    ticksPerQuarter: 220,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    totalTime: totalBeats * secondsPerBeat,
    notes,
  };
}

// ── Chords generation (programmatic) ────────────────────────────────────

function generateChords(params, scalePitches) {
  const secondsPerBeat = 60.0 / params.tempo;
  const totalBeats = BARS * BEATS_PER_BAR;
  const beatsPerChord = totalBeats / params.chords.length;

  const notes = [];
  const rhythms = ['whole', 'half', 'comp'];
  const rhythm = rhythms[Math.floor(Math.random() * rhythms.length)];

  for (let ci = 0; ci < params.chords.length; ci++) {
    const chordInfo = Chord.get(params.chords[ci]);
    if (chordInfo.empty) continue;

    // Voice the chord at octave 4
    const chordNotes = chordInfo.notes.map(noteName => {
      const midi = Note.midi(noteName + '4');
      return midi ? quantizeToScale(midi, scalePitches) : null;
    }).filter(Boolean);

    const chordStartBeat = ci * beatsPerChord;

    if (rhythm === 'whole') {
      const startTime = chordStartBeat * secondsPerBeat;
      const endTime = (chordStartBeat + beatsPerChord) * secondsPerBeat;
      for (const pitch of chordNotes) {
        notes.push({
          pitch, startTime, endTime: endTime - 0.05,
          velocity: 80, program: params.chord_instrument, instrument: 0, isDrum: false,
        });
      }
    } else if (rhythm === 'half') {
      for (let h = 0; h < 2; h++) {
        const startTime = (chordStartBeat + h * (beatsPerChord / 2)) * secondsPerBeat;
        const endTime = (chordStartBeat + (h + 1) * (beatsPerChord / 2)) * secondsPerBeat;
        for (const pitch of chordNotes) {
          notes.push({
            pitch, startTime, endTime: endTime - 0.05,
            velocity: h === 0 ? 80 : 70, program: params.chord_instrument, instrument: 0, isDrum: false,
          });
        }
      }
    } else {
      // comp: hit on beat 1, rest, hit on and-of-2, hit on beat 4
      const hits = [0, 1.5, 3];
      const durations = [1.0, 1.0, 1.0];
      for (let h = 0; h < hits.length && hits[h] < beatsPerChord; h++) {
        const startTime = (chordStartBeat + hits[h]) * secondsPerBeat;
        const endTime = startTime + durations[h] * secondsPerBeat;
        for (const pitch of chordNotes) {
          notes.push({
            pitch, startTime, endTime: Math.min(endTime, (chordStartBeat + beatsPerChord) * secondsPerBeat) - 0.05,
            velocity: h === 0 ? 85 : 70, program: params.chord_instrument, instrument: 0, isDrum: false,
          });
        }
      }
    }
  }

  return {
    ticksPerQuarter: 220,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    totalTime: totalBeats * secondsPerBeat,
    notes,
  };
}

// ── Main ────────────────────────────────────────────────────────────────

async function main() {
  const outputDir = process.argv[2];
  if (!outputDir) {
    console.error('Usage: node generate_midi.js <output-dir>');
    process.exit(1);
  }

  // Read params from stdin
  const input = fs.readFileSync(0, 'utf-8');
  const params = JSON.parse(input);

  console.log(`Generating MIDI: ${params.scale} in ${params.root}, ${params.tempo} BPM`);

  // Load scale intervals from params (passed through from scales.json by Python)
  const scalePitches = buildScalePitches(params.root, params.scale_intervals);

  // Ensure output directory exists
  fs.mkdirSync(outputDir, { recursive: true });

  // Generate all 4 tracks
  console.log('Generating melody (ImprovRNN)...');
  const melody = await generateMelody(params, scalePitches);
  fs.writeFileSync(
    path.join(outputDir, 'melody.mid'),
    Buffer.from(core.sequenceProtoToMidi(melody))
  );

  console.log('Generating drums (DrumsRNN)...');
  const drums = await generateDrums(params);
  fs.writeFileSync(
    path.join(outputDir, 'drums.mid'),
    Buffer.from(core.sequenceProtoToMidi(drums))
  );

  console.log('Generating bass (programmatic)...');
  const bass = generateBass(params, scalePitches);
  fs.writeFileSync(
    path.join(outputDir, 'bass.mid'),
    Buffer.from(core.sequenceProtoToMidi(bass))
  );

  console.log('Generating chords (programmatic)...');
  const chords = generateChords(params, scalePitches);
  fs.writeFileSync(
    path.join(outputDir, 'chords.mid'),
    Buffer.from(core.sequenceProtoToMidi(chords))
  );

  console.log('Done! Generated 4 MIDI files.');
}

main().catch(err => {
  console.error('MIDI generation failed:', err);
  process.exit(1);
});
