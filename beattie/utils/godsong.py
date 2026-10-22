from __future__ import annotations

import asyncio
import io
import random
import struct
import wave
from asyncio import subprocess

from beattie.utils.aioutils import try_wait_for

# Base frequencies (Hz) for octave 4 (G4 through G5).
# Other octaves scale by powers of 2: freq * (2 ** (octave - 4)).
BASE_FREQS: dict[tuple[int, str], float] = {
    (0, "G"): 391.995,  # G4
    (0, "A"): 440.000,  # A4
    (0, "B"): 493.883,  # B4
    (1, "C"): 523.251,  # C5
    (1, "D"): 587.330,  # D5
    (1, "E"): 659.255,  # E5
    (1, "F"): 698.456,  # F5
    (1, "G"): 783.991,  # G5
}

DUR_4 = 0
DUR_8_8 = 1
DUR_3_3_3 = 2
DUR_16_16_16_16 = 3
DUR_8DOT_16 = 4
DUR_8_16_16 = 5
DUR_16_16_8 = 6

GOD_SIMPLE_SONGS = (DUR_4, DUR_4, DUR_4, DUR_4, DUR_8_8)
GOD_NORMAL_SONGS = (DUR_4, DUR_4, DUR_8_8, DUR_3_3_3, DUR_16_16_16_16)
GOD_COMPLEX_SONGS = (
    DUR_4,
    DUR_4,
    DUR_8_8,
    DUR_8_8,
    DUR_8DOT_16,
    DUR_3_3_3,
    DUR_8_16_16,
    DUR_16_16_8,
    DUR_16_16_16_16,
)


def _ins_note(
    k: int,
    octave: int,
    octave_state: int,
    rests: bool,
    buf: list[str],
) -> tuple[int, float]:
    """Port of InsNote() from GodSong.HC. Returns (new_octave_state, freq_hz)."""
    if k == 0 and rests:
        buf.append("R")
        return octave_state, 0.0

    k //= 2
    if k < 3:
        if octave_state != octave:
            octave_state = octave
            buf.append(str(octave_state))
        note = "G" if k == 0 else chr(ord("A") + k - 1)
        buf.append(note)
        rel_oct = 0
    else:
        if octave_state != octave + 1:
            octave_state = octave + 1
            buf.append(str(octave_state))
        note = chr(ord("A") + k - 1)
        buf.append(note)
        rel_oct = 1

    freq = BASE_FREQS[(rel_oct, note)] * (2 ** (octave - 4))
    return octave_state, freq


def god_song_str(
    complexity: int = 1,
    rests: bool = False,
    six_eight: bool = False,
    octave: int = 4,
    beat_sec: float = 0.5,
) -> tuple[str, list[tuple[float, float]]]:
    """
    Port of GodSongStr() from GodSong.HC.
    Generates 2 measures of music and returns (notation_str, [(freq_hz, duration_sec), ...]).
    """
    octave = max(1, min(7, octave))
    octave_state = octave + 1
    buf: list[str] = [str(octave_state)]
    events: list[tuple[float, float]] = []

    if six_eight:
        length = 6
        buf.append("M6/8")
    else:
        length = 8

    last_duration = -1

    for _ in range(length):
        n = random.getrandbits(8)
        if complexity == 2:
            duration = GOD_COMPLEX_SONGS[n % 9]
        elif complexity == 1:
            duration = GOD_NORMAL_SONGS[n % 5]
        else:
            duration = GOD_SIMPLE_SONGS[n % 5]

        match duration:
            case 1:  # DUR_8_8
                if last_duration != DUR_8_8:
                    buf.append("e")
                for _ in range(2):
                    octave_state, f = _ins_note(
                        random.getrandbits(4), octave, octave_state, rests, buf
                    )
                    events.append((f, beat_sec * 0.5))
            case 4:  # DUR_8DOT_16
                buf.append("e.")
                octave_state, f1 = _ins_note(
                    random.getrandbits(4), octave, octave_state, rests, buf
                )
                events.append((f1, beat_sec * 0.75))
                buf.append("s")
                octave_state, f2 = _ins_note(
                    random.getrandbits(4), octave, octave_state, rests, buf
                )
                events.append((f2, beat_sec * 0.25))
                duration = DUR_16_16_16_16
            case 2:  # DUR_3_3_3
                if last_duration != DUR_3_3_3:
                    buf.append("et")
                for _ in range(3):
                    octave_state, f = _ins_note(
                        random.getrandbits(4), octave, octave_state, rests, buf
                    )
                    events.append((f, beat_sec / 3.0))
            case 5:  # DUR_8_16_16
                if last_duration != DUR_8_8:
                    buf.append("e")
                octave_state, f1 = _ins_note(
                    random.getrandbits(4), octave, octave_state, rests, buf
                )
                events.append((f1, beat_sec * 0.5))
                buf.append("s")
                for _ in range(2):
                    octave_state, f = _ins_note(
                        random.getrandbits(4), octave, octave_state, rests, buf
                    )
                    events.append((f, beat_sec * 0.25))
                duration = DUR_16_16_16_16
            case 6:  # DUR_16_16_8
                if last_duration != DUR_16_16_16_16:
                    buf.append("s")
                for _ in range(2):
                    octave_state, f = _ins_note(
                        random.getrandbits(4), octave, octave_state, rests, buf
                    )
                    events.append((f, beat_sec * 0.25))
                buf.append("e")
                octave_state, f3 = _ins_note(
                    random.getrandbits(4), octave, octave_state, rests, buf
                )
                events.append((f3, beat_sec * 0.5))
                duration = DUR_8_8
            case 3:  # DUR_16_16_16_16
                if last_duration != DUR_16_16_16_16:
                    buf.append("s")
                k = random.getrandbits(4)
                k2 = random.getrandbits(4)
                for nibble in (k, k2, k, k2):
                    octave_state, f = _ins_note(
                        nibble, octave, octave_state, rests, buf
                    )
                    events.append((f, beat_sec * 0.25))
            case _:  # DUR_4
                if last_duration != DUR_4:
                    buf.append("q")
                octave_state, f = _ins_note(
                    random.getrandbits(4), octave, octave_state, rests, buf
                )
                events.append((f, beat_sec))

        last_duration = duration

    return "".join(buf), events


def synthesize_godsong_wav(
    complexity: int = 1,
    rests: bool = False,
    six_eight: bool = False,
    octave: int = 4,
    beat_sec: float = 0.5,
    sample_rate: int = 44100,
    amplitude: int = 6000,
) -> tuple[str, bytes]:
    """Generates full AA BB GodSong notation and raw WAV bytes in memory."""
    st1, ev1 = god_song_str(
        complexity=complexity,
        rests=rests,
        six_eight=six_eight,
        octave=octave,
        beat_sec=beat_sec,
    )
    st2, ev2 = god_song_str(
        complexity=complexity,
        rests=rests,
        six_eight=six_eight,
        octave=octave,
        beat_sec=beat_sec,
    )

    full_notation = f"{st1}{st1}{st2}{st2}"
    full_events = ev1 + ev1 + ev2 + ev2

    pcm_samples = bytearray()
    for freq, dur in full_events:
        total_samples = int(sample_rate * dur)
        gap_samples = min(int(sample_rate * 0.01), total_samples // 4)
        tone_samples = total_samples - gap_samples

        if freq <= 0.0:
            pcm_samples.extend(b"\x00\x00" * total_samples)
        else:
            period = sample_rate / freq
            half_period = period / 2.0
            for i in range(tone_samples):
                val = amplitude if (i % period) < half_period else -amplitude
                pcm_samples.extend(struct.pack("<h", val))
            pcm_samples.extend(b"\x00\x00" * gap_samples)

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_samples)

    return full_notation, wav_io.getvalue()


async def generate_godsong_audio(
    complexity: int = 1,
    rests: bool = False,
    six_eight: bool = False,
    octave: int = 4,
) -> tuple[str, io.BytesIO, str]:
    """
    Synthesizes a GodSong melody and compresses it to a 64kbps mono MP3 via FFmpeg.
    Returns (notation_str, audio_buffer, filename).
    """
    notation, wav_bytes = await asyncio.to_thread(
        synthesize_godsong_wav,
        complexity=complexity,
        rests=rests,
        six_eight=six_eight,
        octave=octave,
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "wav",
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-ac",
            "1",
            "-ar",
            "44100",
            "-b:a",
            "64k",
            "-f",
            "mp3",
            "pipe:1",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        stdout, _ = await try_wait_for(proc, wav_bytes)
        if stdout:
            return notation, io.BytesIO(stdout), "godsong.mp3"
    except (FileNotFoundError, asyncio.TimeoutError):
        pass

    return notation, io.BytesIO(wav_bytes), "godsong.wav"