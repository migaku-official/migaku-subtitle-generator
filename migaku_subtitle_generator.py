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

os.environ['PATH'] = os.path.dirname(ffmpeg_command) + os.pathsep + os.environ['PATH']
if os.path.dirname(ffprobe_command) != os.path.dirname(ffmpeg_command):
    os.environ['PATH'] = os.path.dirname(ffprobe_command) + os.pathsep + os.environ['PATH']


if len(sys.argv) != 4:
    print(f"Usage: {sys.argv[0]} <whisper-model> <video> <subtitle>")
    sys.exit(1)


whisper_model = sys.argv[1]
video = sys.argv[2]
subtitle = sys.argv[3]

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
result = model.transcribe("result.ogg", no_speech_threshold=0.9)

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

# save the modified subtitle file
whisper_subs.save(f"{video}.srt", encoding="utf-8")
