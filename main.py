#!/usr/bin/env python

# This program takes a video file and a subtitle file as input and
# outputs an audio file with all audio without subtitles trimmed out.
# We will then use whisper to generate a new subtitle file in Japanese.
# Afterwards wie will have to re-add the trimmed timing to the new
# subtitle file.

import sys
import pysubs2
import subprocess
from pydub import AudioSegment
from stable_whisper import results_to_sentence_srt
from stable_whisper import load_model


if len(sys.argv) != 4:
    print(f"Usage: {sys.argv[0]} <whisper-model> <video> <subtitle>")
    sys.exit(1)

whisper_model = sys.argv[1]
video = sys.argv[2]
subtitle = sys.argv[3]

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
speech_times_with_padding = [[max(0, speech_time[0] - 200), speech_time[1] + 200] for speech_time in merged_speech_times]
# merge again
merged_speech_times_with_padding = []
for speech_time in speech_times_with_padding:
    if not merged_speech_times_with_padding or merged_speech_times_with_padding[-1][1] < speech_time[0]:
        merged_speech_times_with_padding.append(speech_time)
    else:
        merged_speech_times_with_padding[-1][1] = max(merged_speech_times_with_padding[-1][1], speech_time[1])


segment = AudioSegment.from_file(video)
# temp = AudioSegment.empty()
result = AudioSegment.empty()
removed_timings = []
added_silence = []
print("creating trimmed audio file")
for count, speech_time in enumerate(merged_speech_times_with_padding):
    if count % 10 == 0:
        print(f"processing speech time {count + 1}/{len(merged_speech_times)}")
    before = len(result)
    result += segment[speech_time[0]:speech_time[1]]
    after_sub = len(result)
    result += AudioSegment.silent(duration=700)
    after_silence = len(result)
    removed_timings.append([before, after_sub])
    added_silence.append([after_sub, after_silence])
# only keep the audio with speech
# for speech_time in merged_speech_times_with_padding:
#     result += segment[speech_time[0]:speech_time[1]]

result.export("result.mp3", format="mp3")

# generate japanese subtitles with whisper
# example: whisper --language ja --model large file.mkv
# subprocess.run(["whisper", "--language", "ja", "--model", whisper_model, "--no_speech_threshold", "0.9", "result.ogg"])
print("generating whisper subtitles")
model = load_model(whisper_model)
results = model.transcribe("result.mp3", language="ja")
results_to_sentence_srt(results, 'audio.srt', end_at_last_word=True)

# # list of time ranges that have been removed
# for i in range(len(merged_speech_times_with_padding)):
#     if i == 0:
#         removed_timings.append([0, merged_speech_times_with_padding[i][0]])
#     else:
#         removed_timings.append([merged_speech_times_with_padding[i - 1][1], merged_speech_times_with_padding[i][0]])
#
    
# for i in range(len(merged_speech_times_with_padding)):
#     if i == 0:
#         removed_timings.append([0, merged_speech_times_with_padding[i][0]])
#     else:
#         removed_timings.append([merged_speech_times_with_padding[i - 1][1], merged_speech_times_with_padding[i][0]])


def shift_forward_after(subs, ms, start):
    for line in subs:
        if line.end >= start:
            line.start += ms
            line.end += ms


def shift_backward_after(subs, ms, start):
    for line in subs:
        if line.start >= start:
            line.start -= ms
            line.end -= ms

print("shifting whisper subtitles")
# # read new subtitle file
whisper_subs = pysubs2.load("audio.srt", encoding="utf-8")
# shift subtitles back to account for added silence
for i in range(len(added_silence)):
    shift_backward_after(whisper_subs, added_silence[i][1] - added_silence[i][0], added_silence[i][0])
    # shift_after(whisper_subs, added_silence[i][0] - added_silence[i][1], added_silence[i][0])
# re-add removed timing to align with original audio
for timing in removed_timings:
    shift_forward_after(whisper_subs, timing[1] - timing[0], timing[0])
    # shift_after(whisper_subs, timing[1] - timing[0], timing[0])


print("writing new subtitle file")
# save the modified subtitle file
whisper_subs.save(f"{video}.srt", encoding="utf-8")
