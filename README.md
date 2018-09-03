# Freddy Film Bot

Freddy is a bot that can auto-generate a narrated animated film based on a given text story.
All clips are retrieved from [Giphy](https://giphy.com).


## Requirements

- Python 3.6+
- spacy
- espeak
- ffmpeg (ffmpeg and ffprobe)
- Giphy API key (get one [here](https://developers.giphy.com/))


## Usage

This will create a video based on "Jack and Jill".

`GIPHY_API_KEY="YOUR_KEY_HERE" freddy.py -i examples/jack_and_jill.txt out.mp4`

