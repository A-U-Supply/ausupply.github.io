"""Slack poster with MIDI file upload support."""
import logging
from pathlib import Path

from slack_sdk import WebClient

logger = logging.getLogger(__name__)

TRACK_LABELS = {
    "melody": ":musical_keyboard: Melody",
    "drums": ":drum_with_drumsticks: Drums",
    "bass": ":guitar: Bass",
    "chords": ":musical_score: Chords",
}


def _find_instrument_name(program: int, instrument_list: list[dict]) -> str:
    """Look up instrument name by MIDI program number."""
    for inst in instrument_list:
        if inst["program"] == program:
            return inst["name"]
    return f"MIDI {program}"


def format_message(params: dict, instruments: dict) -> str:
    """Format the main Slack message with all metadata."""
    melody_name = _find_instrument_name(params["melody_instrument"], instruments["melody"])
    chord_name = _find_instrument_name(params["chord_instrument"], instruments["chords"])
    chords_str = "  ".join(params["chords"])

    lines = [
        f":musical_note: *Daily MIDI* — {params['scale']} in {params['root']} ({params['tempo']} BPM)",
        f"_{params['description']}_",
        "",
        f":musical_keyboard: Melody — ImprovRNN, {melody_name} (MIDI {params['melody_instrument']}), temperature {params['temperature']}",
        f":drum_with_drumsticks: Drums — DrumsRNN, temperature {params['temperature']}",
        f":guitar: Bass — Programmatic from chord roots",
        f":musical_score: Chords — {chords_str}",
    ]
    return "\n".join(lines)


def post_midi_to_slack(
    params: dict,
    instruments: dict,
    midi_dir: Path,
    channel: str,
    token: str,
) -> bool:
    """Post main message + 4 MIDI files as threaded replies."""
    try:
        client = WebClient(token=token)

        # Post main message
        message = format_message(params, instruments)
        resp = client.chat_postMessage(channel=channel, text=message)
        thread_ts = resp["ts"]
        logger.info(f"Posted main message to {channel}")

        # Upload each MIDI file as a threaded reply
        upload_failures = 0
        for track in ["melody", "drums", "bass", "chords"]:
            filepath = midi_dir / f"{track}.mid"
            if not filepath.exists():
                logger.warning(f"Missing MIDI file: {filepath}")
                upload_failures += 1
                continue

            try:
                client.files_upload_v2(
                    channel=channel,
                    file=str(filepath),
                    filename=f"{track}.mid",
                    initial_comment=TRACK_LABELS[track],
                    thread_ts=thread_ts,
                )
                logger.info(f"Uploaded {track}.mid")
            except Exception as upload_err:
                logger.warning(f"Failed to upload {track}.mid: {upload_err}")
                if hasattr(upload_err, 'response') and upload_err.response:
                    logger.warning(f"Slack API response: {upload_err.response.data}")
                upload_failures += 1

        if upload_failures > 0:
            logger.warning(f"{upload_failures}/4 file uploads failed (missing files:write scope?)")

        return True
    except Exception as e:
        logger.error(f"Failed to post to Slack: {e}")
        return False
