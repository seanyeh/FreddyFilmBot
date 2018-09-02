#!/usr/bin/env python3

import argparse
import math
import json
import random
import re
import shutil
import subprocess
import urllib.request

import os
import os.path

import spacy


NLP = spacy.load("en")

ID = 0
CACHE_DIR=".freddy_cache"

'''
Hacky way to generate a new temporary filename
'''
def get_filename(ext):
    global ID

    if not os.path.isdir(CACHE_DIR):
        os.mkdir(CACHE_DIR)

    filename = os.path.join(CACHE_DIR, "{x}.{ext}".format(x=ID, ext=ext))

    ID += 1
    return filename


def get_duration(filename):
    output = subprocess.check_output(["ffprobe", "-i", filename, "-show_format"])

    result = re.search("duration=(\d+\.\d+)", output.decode("utf-8"))

    return math.ceil(float(result.groups()[0]))


def generate_audio(text):
    filename = get_filename("wav")

    subprocess.run(["espeak", "-w", filename, text])
    return filename


'''
Add text to a video clip
'''
def _add_text(clip_file, text):
    # Resize to 720x720
    output_filename2 = get_filename("mp4")
    subprocess.run(["ffmpeg", "-i", clip_file, "-vf", "scale=720x720,setdar=1:1", output_filename2])

    # https://stackoverflow.com/questions/17623676/text-on-video-ffmpeg
    # ffmpeg -i input.mp4 -vf drawtext="fontfile=/path/to/font.ttf: \
    #         text='xxx': fontcolor=white: fontsize=24: box=1: boxcolor=black@0.5: \
    #         boxborderw=5: x=(w-text_w)/2: y=(h-text_h)/2" -codec:a copy out.mp4
    drawtext = "drawtext=\"font= :text='{text}': fontcolor=white: fontsize=24: box=1: boxcolor=black@0.5: boxborderw=5: x=(w-text_w)/2: y=50"

    output_filename = get_filename("mp4")

    subprocess.run(["ffmpeg", "-i", output_filename2, "-vf", drawtext.format(text=text), output_filename])

    return output_filename



def giphy_search(search):
    search=search.replace(" ","+")
    URL = "https://api.giphy.com/v1/gifs/search?q={search}&api_key={secret}"
    with urllib.request.urlopen(URL.format(search=search, secret=os.environ["GIPHY_API_KEY"])) as resp:
        data = json.loads(resp.read());

    # choose random
    item = random.choice(data["data"])

    return item["images"]["original_mp4"]["mp4"]


def get_search_terms(text):
    doc = NLP(text)
    chunks = list(doc.noun_chunks)

    if len(chunks) == 0:
        return text

    # Root verb?
    root = str(list(doc.sents)[0].root)

    search = str(random.choice(chunks))

    if root not in search:
        search = root + " " + search

    return search


def get_clip(text):
    # First generate audio
    audio_filename = generate_audio(text)
    audio_duration = get_duration(audio_filename)

    # Get video url from giphy
    search = get_search_terms(text)
    url = giphy_search(search)

    # Download video
    filename = get_filename("mp4")
    with urllib.request.urlopen(url) as resp:
        contents = resp.read()

    with open(filename, "wb") as f:
        f.write(contents)

    # Add text
    vid_filename = _add_text(filename, text)

    while get_duration(vid_filename) < audio_duration:
        new_filename = get_filename("mp4")
        concat_video_wo_audio([vid_filename, vid_filename], new_filename)
        vid_filename = new_filename

    filename = merge_video_audio(vid_filename, audio_filename)

    return filename


def merge_video_audio(vid_fn, audio_fn):
    output = get_filename("mp4")

    subprocess.run(["ffmpeg", "-i", vid_fn, "-i", audio_fn, "-shortest", output])

    return output


def concat_video_wo_audio(filenames, output):
    num = len(filenames)

    input_args = []
    filter_str = ""
    for i,f in enumerate(filenames):
        input_args.append("-i")
        input_args.append(f)

        filter_str += "[{x}:0]".format(x=i)

    filter_args = "{filter_str}concat=n={num}:v=1:a=0".format(filter_str=filter_str, num=num)


    args = ["ffmpeg", *input_args, "-filter_complex", filter_args, output]
    subprocess.run(args)


def concat_video(filenames, output):
    num = len(filenames)

    input_args = []
    filter_str = ""
    for i,f in enumerate(filenames):
        input_args.append("-i")
        input_args.append(f)

        filter_str += "[{x}:v:0][{x}:a:0]".format(x=i)

    filter_args = "{filter_str}concat=n={num}:v=1:a=1[outv][outa]".format(filter_str=filter_str, num=num)

    args = ["ffmpeg", *input_args, "-filter_complex", filter_args, "-map", "[outv]", "-map", "[outa]", output]
    print("args:", args)
    subprocess.run(args)



PUNCTS=[",", ";"]

'''
Separate a given text into short phrases
'''
def tokenize_text(text):
    doc = NLP(text)

    phrases = []
    for s in doc.sents:
        tokens = tokenize(str(s))
        phrases += get_phrases(tokens)

    return phrases


def tokenize(text):
    tokens = text.split(" ")

    new_tokens = []

    for i,_t in enumerate(tokens):
        t = _t.strip()

        if len(t) == 0:
            continue
        elif t[-1] in PUNCTS and len(t) > 1:
            new_tokens.append(t[:-1])
            new_tokens.append(t[-1])
        else:
            new_tokens.append(t)

    return new_tokens


def _next_punct(words, start_index):
    for i,w in enumerate(words[start_index:]):
        if w in PUNCTS:
            return start_index + i

    return -1


def get_phrases(words):
    if len(words) <= 5:
        return [" ".join(words)]

    i = _next_punct(words, 3)

    if (i == -1 or len(words) - i < 3):
        return [" ".join(words)]

    return [" ".join(words[0:i])] + get_phrases(words[i+1:])


'''
Main run function
'''
def run(input_file, output_file):
    clean()

    with open(input_file) as f:
        text = f.read().replace("\n", ", ")

    phrases = tokenize_text(text)
    phrases += ["The End."]

    files = [ get_clip(p) for p in phrases ]
    concat_video(files, output_file)



def main():
    desc = '''
FreddyFilmBot

Freddy is a bot that can auto-generate a narrated animated film based on a given text story.
All clips are retrieved from Giphy

Example usage:

GIPHY_API_KEY=XXX freddy.py -i examples/jack_and_jill.txt out.mp4'''

    parser = argparse.ArgumentParser(description=desc, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("--cache-dir", "-c", type=str,
            default=".freddy_cache",
            help="Cache directory to store temporary files. Default: .freddy_cache"
            )

    parser.add_argument("--input-file", "-i", type=str, required=True,
            help="Input text file of story/script"
            )

    parser.add_argument("--clean", type=bool, default=False,
            help="Clean the cache directory. Default: false"
            )

    parser.add_argument("output_file", metavar="OUTPUT_FILE",
        help="Output video filename")

    args = parser.parse_args()

    # Set custom cache directory
    if args.cache_dir:
        global CACHE_DIR
        CACHE_DIR=args.cache_dir

    if args.clean:
        clean()

    run(args.input_file, args.output_file)


def clean():
    if os.path.isdir(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)


if __name__ == "__main__":
    main()
