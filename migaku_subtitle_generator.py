#!/usr/bin/env python

# This program takes a video file and a subtitle file as input and
# outputs an audio file with all audio without subtitles trimmed out.
# We will then use whisper to generate a new subtitle file in Japanese.
# Afterwards wie will have to re-add the trimmed timing to the new
# subtitle file.

import sys
import pysubs2
import os
from pydub import AudioSegment
import platform
import whisper
from shutil import which

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)


app = QApplication([])

ffprobe_command: str = ""
ffmpeg_command: str = ""


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


if os.path.isfile(resource_path("./ffprobe")):
    ffprobe_command = resource_path("./ffprobe")
if os.path.isfile(resource_path("./ffmpeg")):
    ffmpeg_command = resource_path("./ffmpeg")
if platform.system() == "Windows":
    ffprobe_command = "ffprobe.exe"
    ffmpeg_command = "ffmpeg.exe"


if not ffprobe_command:
    if temp_ffprobe_command_path := which("ffprobe"):
        ffprobe_command = temp_ffprobe_command_path
if not ffmpeg_command:
    if temp_ffmpeg_command_path := which("ffmpeg"):
        ffmpeg_command = temp_ffmpeg_command_path

missing_program = ""
if not ffprobe_command:
    missing_program = "ffprobe"
if not ffmpeg_command:
    missing_program = "ffmpeg"
if missing_program:
    QMessageBox.critical(
        None,
        "Migaku Error Dialog",
        f"It seems {missing_program} is not installed. Please retry after installing",
        buttons=QMessageBox.Ok,
    )
    sys.exit(1)

os.environ["PATH"] = os.path.dirname(ffmpeg_command) + os.pathsep + os.environ["PATH"]
if os.path.dirname(ffprobe_command) != os.path.dirname(ffmpeg_command):
    os.environ["PATH"] = os.path.dirname(ffprobe_command) + os.pathsep + os.environ["PATH"]

subtitle_text_codec_names = ["srt", "ass", "ssa", "subrip", "vtt", "webvtt", "mov_text"]

subtitle_file_endings_to_convert = [
    ".ass",
    ".ssa",
    ".vtt",
]

video_file_endings = [
    ".webm",
    ".mkv",
    ".flv",
    ".flv",
    ".vob",
    ".ogv",
    ".ogg",
    ".drc",
    ".gif",
    ".gifv",
    ".mng",
    ".avi",
    ".MTS",
    ".M2TS",
    ".TS",
    ".mov",
    ".qt",
    ".wmv",
    ".yuv",
    ".rm",
    ".rmvb",
    ".viv",
    ".asf",
    ".amv",
    ".mp4",
    ".m4p",
    ".m4v",
    ".mpg",
    ".mp2",
    ".mpeg",
    ".mpe",
    ".mpv",
    ".mpg",
    ".mpeg",
    ".m2v",
    ".m4v",
    ".svi",
    ".3gp",
    ".3g2",
    ".mxf",
    ".roq",
    ".nsv",
    ".flv",
    ".f4v",
    ".f4p",
    ".f4a",
    ".f4b",
]

audio_file_endings = [
    ".3gp",
    ".aa",
    ".aac",
    ".aax",
    ".act",
    ".aiff",
    ".alac",
    ".amr",
    ".ape",
    ".au",
    ".awb",
    ".dss",
    ".dvf",
    ".flac",
    ".gsm",
    ".ikla",
    ".ivs",
    ".m4a",
    ".m4b",
    ".m4p",
    ".mmf",
    ".mp3",
    ".mpc",
    ".msv",
    ".nmf",
    ".ogg",
    ".opus",
    ".ra",
    ".raw",
    ".rf64",
    ".sln",
    ".tta",
    ".voc",
    ".vox",
    ".wav",
    ".wma",
    ".wv",
    ".webm",
    ".8svx",
    ".cda",
]


if len(sys.argv) not in [4, 5]:
    print(f"Usage: {sys.argv[0]} <whisper-model> <video> <subtitle> [<initial_prompt>]")
    sys.exit(1)


whisper_model = sys.argv[1]
video = sys.argv[2]
subtitle = sys.argv[3]
initial_prompt = sys.argv[4] if len(sys.argv) == 5 else ""

print("Caluculating speech segments...")
subs = pysubs2.load(subtitle, encoding="utf-8")
speech_times = [[line.start, line.end] for line in subs]
# merge overlapping or adjacent speech times
merged_speech_times = []
for speech_time in speech_times:
    if not merged_speech_times or merged_speech_times[-1][1] < speech_time[0]:
        merged_speech_times.append(speech_time)
    else:
        merged_speech_times[-1][1] = max(merged_speech_times[-1][1], speech_time[1])
# add padding so nothing is cut off and whisper can recognize when the sentence changes
speech_times_with_padding = [
    [max(0, speech_time[0] - 200), speech_time[1] + 200] for speech_time in merged_speech_times
]
# merge again
merged_speech_times_with_padding = []
for speech_time in speech_times_with_padding:
    if not merged_speech_times_with_padding or merged_speech_times_with_padding[-1][1] < speech_time[0]:
        merged_speech_times_with_padding.append(speech_time)
    else:
        merged_speech_times_with_padding[-1][1] = max(merged_speech_times_with_padding[-1][1], speech_time[1])

print("Trimming audio...")

segment = AudioSegment.from_file(video)
result = AudioSegment.empty()
# only keep the audio with speech
for speech_time in merged_speech_times_with_padding:
    result += segment[speech_time[0] : speech_time[1]]

result.export("result.ogg", format="ogg")


print("Running whisper...")
# generate japanese subtitles with whisper
# example: whisper --language ja --model large file.mkv
model = whisper.load_model(whisper_model)
result = model.transcribe(
    "result.ogg",
    beam_size=5,
    best_of=5,
    verbose=True,
    no_speech_threshold=0.9,
    initial_prompt=initial_prompt,
)

print("re-adding timing to subtitle file...")
# removed times with start and end
removed_timings = []
for i in range(len(merged_speech_times_with_padding)):
    if i == 0:
        removed_timings.append([0, merged_speech_times_with_padding[i][0]])
    else:
        removed_timings.append([merged_speech_times_with_padding[i - 1][1], merged_speech_times_with_padding[i][0]])


def shift_after(subs, ms, start):
    for line in subs:
        if line.end >= start:
            line.start += ms
            line.end += ms


# # read new subtitle file
whisper_subs = pysubs2.load_from_whisper(result)
# re-add removed timing to align with original audio
for timing in removed_timings:
    shift_after(whisper_subs, timing[1] - timing[0], timing[0])

whisper_subs.save(f"{video}-original.srt", encoding="utf-8")


# align with original subtitle file
# loop through generated subtitle.
# For each line check the provided subtitle if a line starts at the same timestamp.
# If yes, keep it, if not align it to the closest line in the provided sub except if a line already starts at that position (i.e. something already got aligned there).
# We are going to do it two times, check for lines that are already in perfect or almost perfect positions and use these as anchors.
# So a line that should be moved to an anchor would be kept in place instead
print("aligning with original subtitle file...")


def align_if_offset_smaller_than(offset: int):
    for whisper_line in whisper_subs:
        start_times_original = [line.start for line in subs]
        if any(abs(whisper_line.start - start) < offset for start in start_times_original):
            new_start = min(start_times_original, key=lambda x: abs(x - whisper_line.start))
            if any(line.start == new_start for line in whisper_subs):
                # print(f"keeping {whisper_line.text} because {new_start} is already taken")
                continue
            shift_time = new_start - whisper_line.start
            print(f"aligning {whisper_line.text} to {new_start}")
            whisper_line.start += shift_time
            whisper_line.end += shift_time


for offset in range(5, 4000, 20):
    print(f"offset: {offset}")
    align_if_offset_smaller_than(offset)

# iterate through subs and cut off end time if it overlaps with the following line

print("fixing overlapping lines")
whisper_subs.sort()

for idx, line in enumerate(whisper_subs):
    try:
        next_line = whisper_subs[idx + 1]
    except IndexError:
        continue
    if line.end > next_line.start:
        line.end = next_line.start

# save the modified subtitle file
whisper_subs.save(f"{video}.srt", encoding="utf-8")
