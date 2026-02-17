/**
 * Extend MIDI tracks using Magenta.js models.
 * Reads params from stdin JSON.
 */

const fs = require('fs');
const path = require('path');
const mm = require('@magenta/music/node/music_rnn');
const core = require('@magenta/music/node/core');
const { Midi } = require('@tonejs/midi');

const IMPROV_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/chord_pitches_improv';
const DRUMS_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/drum_kit_rnn';
const STEPS_PER_QUARTER = 4;

function readMidi(filePath) {
    const data = fs.readFileSync(filePath);
    return new Midi(data);
}

function midiToNoteSequence(midi, isDrum = false) {
    const notes = [];
    for (const track of midi.tracks) {
        for (const note of track.notes) {
            notes.push({
                pitch: note.midi,
                startTime: note.time,
                endTime: note.time + note.duration,
                velocity: Math.round(note.velocity * 127),
                program: isDrum ? 0 : (track.instrument ? track.instrument.number : 0),
                instrument: 0,
                isDrum: isDrum,
            });
        }
    }
    return {
        ticksPerQuarter: 220,
        totalTime: Math.max(...notes.map(n => n.endTime), 0),
        tempos: [{ time: 0, qpm: midi.header.tempos[0]?.bpm || 120 }],
        timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
        notes: notes,
        controlChanges: [],
    };
}

function buildScalePitches(root, intervals, minPitch = 36, maxPitch = 96) {
    const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const rootIdx = noteNames.indexOf(root.replace('b', '#'));
    const pitches = [];
    for (let octave = 0; octave < 10; octave++) {
        for (const interval of intervals) {
            const pitch = rootIdx + (octave * 12) + interval;
            if (pitch >= minPitch && pitch <= maxPitch) {
                pitches.push(pitch);
            }
        }
    }
    return [...new Set(pitches)].sort((a, b) => a - b);
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

async function extendMelody(seedSeq, params, scalePitches, targetBars) {
    const improvRnn = new mm.MusicRNN(IMPROV_CHECKPOINT);
    await improvRnn.initialize();

    const secondsPerBar = (60.0 / params.tempo) * 4;
    const stepsPerBar = STEPS_PER_QUARTER * 4;
    const allNotes = [...seedSeq.notes];
    let currentTime = seedSeq.totalTime;

    const baseBars = Math.ceil(seedSeq.totalTime / secondsPerBar);
    let barsGenerated = baseBars;

    while (barsGenerated < targetBars) {
        // Cycle temperature: some chunks repeat-ish (low temp), some explore (high temp)
        const cyclePos = (barsGenerated - baseBars) % 12;
        let temp;
        if (cyclePos < 4) temp = params.temperature * 0.6;
        else if (cyclePos < 8) temp = params.temperature * 1.0;
        else temp = params.temperature * 1.3;

        const recentNotes = allNotes.slice(-8).map(n => ({
            ...n,
            startTime: n.startTime - (currentTime - secondsPerBar),
            endTime: n.endTime - (currentTime - secondsPerBar),
        })).filter(n => n.startTime >= 0);

        const seed = {
            ticksPerQuarter: 220,
            totalTime: secondsPerBar,
            tempos: [{ time: 0, qpm: params.tempo }],
            timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
            notes: recentNotes.length > 0 ? recentNotes : [{
                pitch: scalePitches[Math.floor(scalePitches.length / 2)],
                startTime: 0, endTime: 0.5, velocity: 100,
                program: 0, instrument: 0, isDrum: false,
            }],
            controlChanges: [],
        };

        const quantizedSeed = core.sequences.quantizeNoteSequence(seed, STEPS_PER_QUARTER);
        const barsToGen = Math.min(4, targetBars - barsGenerated);
        const totalSteps = barsToGen * stepsPerBar;

        try {
            const continuation = await improvRnn.continueSequence(
                quantizedSeed, totalSteps, temp, params.chords
            );

            // Magenta returns quantized sequences — timing is in steps, not seconds
            const stepDuration = secondsPerBar / stepsPerBar;
            for (const note of continuation.notes) {
                const startStep = note.quantizedStartStep || 0;
                const endStep = note.quantizedEndStep || (startStep + 1);
                allNotes.push({
                    pitch: quantizeToScale(note.pitch, scalePitches),
                    startTime: (startStep * stepDuration) + currentTime,
                    endTime: (endStep * stepDuration) + currentTime,
                    velocity: note.velocity || 100,
                    program: params.melodyInstrument || 0,
                    instrument: 0,
                    isDrum: false,
                });
            }
            currentTime += barsToGen * secondsPerBar;
        } catch (e) {
            console.error('Magenta continuation error, looping original:', e.message);
            for (const note of seedSeq.notes) {
                allNotes.push({
                    ...note,
                    startTime: note.startTime + currentTime,
                    endTime: note.endTime + currentTime,
                });
            }
            currentTime += seedSeq.totalTime;
        }

        barsGenerated += 4;
    }

    improvRnn.dispose();

    return {
        ...seedSeq,
        notes: allNotes,
        totalTime: currentTime,
        controlChanges: [],
    };
}

async function extendDrums(seedSeq, params, targetBars) {
    const drumsRnn = new mm.MusicRNN(DRUMS_CHECKPOINT);
    await drumsRnn.initialize();

    const secondsPerBar = (60.0 / params.tempo) * 4;
    const stepsPerBar = STEPS_PER_QUARTER * 4;
    const allNotes = [...seedSeq.notes];
    let currentTime = seedSeq.totalTime;
    let barsGenerated = Math.ceil(seedSeq.totalTime / secondsPerBar);

    while (barsGenerated < targetBars) {
        const recentNotes = allNotes.slice(-8).map(n => ({
            ...n,
            startTime: Math.max(0, n.startTime - (currentTime - secondsPerBar)),
            endTime: Math.max(0.1, n.endTime - (currentTime - secondsPerBar)),
        })).filter(n => n.startTime >= 0 && n.endTime > n.startTime);

        const seed = {
            ticksPerQuarter: 220,
            totalTime: secondsPerBar,
            tempos: [{ time: 0, qpm: params.tempo }],
            timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
            notes: recentNotes.length > 0 ? recentNotes : [
                { pitch: 36, startTime: 0, endTime: 0.5, velocity: 100, isDrum: true, instrument: 0 },
                { pitch: 42, startTime: 0, endTime: 0.5, velocity: 80, isDrum: true, instrument: 0 },
            ],
            controlChanges: [],
        };

        const quantizedSeed = core.sequences.quantizeNoteSequence(seed, STEPS_PER_QUARTER);
        const barsToGen = Math.min(4, targetBars - barsGenerated);

        try {
            const continuation = await drumsRnn.continueSequence(
                quantizedSeed, barsToGen * stepsPerBar, params.temperature
            );
            // Magenta returns quantized sequences — timing is in steps, not seconds
            const stepDuration = secondsPerBar / stepsPerBar;
            for (const note of continuation.notes) {
                const startStep = note.quantizedStartStep || 0;
                const endStep = note.quantizedEndStep || (startStep + 1);
                allNotes.push({
                    pitch: note.pitch,
                    startTime: (startStep * stepDuration) + currentTime,
                    endTime: (endStep * stepDuration) + currentTime,
                    velocity: note.velocity || 100,
                    program: 0, instrument: 0, isDrum: true,
                });
            }
        } catch (e) {
            console.error('Drums continuation error, looping:', e.message);
            for (const note of seedSeq.notes) {
                allNotes.push({ ...note, startTime: note.startTime + currentTime, endTime: note.endTime + currentTime });
            }
        }
        currentTime += barsToGen * secondsPerBar;
        barsGenerated += 4;
    }

    drumsRnn.dispose();
    return { ...seedSeq, notes: allNotes, totalTime: currentTime, controlChanges: [] };
}

function extendProgrammatic(seedSeq, targetDuration) {
    const allNotes = [...seedSeq.notes];
    const origDuration = seedSeq.totalTime;
    if (origDuration <= 0) return seedSeq;

    let t = origDuration;
    while (t < targetDuration) {
        for (const note of seedSeq.notes) {
            if (note.startTime + t >= targetDuration) break;
            allNotes.push({
                ...note,
                startTime: note.startTime + t,
                endTime: Math.min(note.endTime + t, targetDuration),
            });
        }
        t += origDuration;
    }
    return { ...seedSeq, notes: allNotes, totalTime: targetDuration, controlChanges: [] };
}

async function main() {
    const input = fs.readFileSync(0, 'utf-8');
    const params = JSON.parse(input);

    const scalePitches = buildScalePitches(params.root, params.scaleIntervals);
    const secondsPerBar = (60.0 / params.tempo) * 4;
    const targetBars = Math.ceil(params.targetDuration / secondsPerBar);

    console.error(`Extending to ${targetBars} bars (~${params.targetDuration}s) at ${params.tempo} BPM`);

    const melodyMidi = readMidi(params.melodyMidi);
    const drumsMidi = readMidi(params.drumsMidi);
    const bassMidi = readMidi(params.bassMidi);
    const chordsMidi = readMidi(params.chordsMidi);

    const melodySeed = midiToNoteSequence(melodyMidi);
    const drumsSeed = midiToNoteSequence(drumsMidi, true);
    const bassSeed = midiToNoteSequence(bassMidi);
    const chordsSeed = midiToNoteSequence(chordsMidi);

    const extendedMelody = await extendMelody(melodySeed, params, scalePitches, targetBars);
    const extendedDrums = await extendDrums(drumsSeed, params, targetBars);
    const extendedBass = extendProgrammatic(bassSeed, params.targetDuration);
    const extendedChords = extendProgrammatic(chordsSeed, params.targetDuration);

    const outputDir = params.outputDir;
    fs.mkdirSync(outputDir, { recursive: true });

    for (const [name, seq] of [
        ['melody.mid', extendedMelody],
        ['drums.mid', extendedDrums],
        ['bass.mid', extendedBass],
        ['chords.mid', extendedChords],
    ]) {
        const midiBytes = core.sequenceProtoToMidi(seq);
        fs.writeFileSync(path.join(outputDir, name), Buffer.from(midiBytes));
    }

    console.error('Extension complete');
    console.log(JSON.stringify({
        melody_notes: extendedMelody.notes.length,
        drums_notes: extendedDrums.notes.length,
        bass_notes: extendedBass.notes.length,
        chords_notes: extendedChords.notes.length,
        target_duration: params.targetDuration,
        target_bars: targetBars,
    }));
}

main().catch(e => { console.error(e); process.exit(1); });
