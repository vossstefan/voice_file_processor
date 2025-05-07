# Voice File Processor

This project provides a GUI tool to process voice recordings in `.m4a` format, split them into voice buffers, and create a new MP3 file with user-selected buffer repetitions and silence.

## Features
- Detects voice regions in an `.m4a` file using VAD
- Lets you preview and select which buffers to repeat
- Adds silence before and after repeated buffers (1.5x buffer length)
- Exports the result as an MP3 file

## Requirements
- Python 3.7+
- [ffmpeg](https://ffmpeg.org/download.html) (must be installed and in your PATH)

## Python Dependencies
Install with:
```bash
pip install -r requirements.txt
```

## Usage
1. Run the script:
   ```bash
   python voice_buffer_gui.py
   ```
2. Use the GUI to select your `.m4a` file, preview buffers, select which to repeat, and choose output location/filename.
3. Click "Process and Save" to generate your MP3.

## Notes
- The tool uses [webrtcvad](https://github.com/wiseman/py-webrtcvad) for voice activity detection.
- [pydub](https://github.com/jiaaro/pydub) is used for audio manipulation and playback.
- Make sure `ffmpeg` is installed and accessible from your command line for audio conversion and playback. 