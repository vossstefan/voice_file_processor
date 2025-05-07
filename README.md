# Voice Buffer Splitter

A GUI application for processing audio files by splitting them into voice segments and allowing various manipulations.

## Features

### Audio File Support
- Supports multiple audio formats:
  - M4A
  - MP3
  - WAV

### Buffer Management
- Automatic voice detection and segmentation
- Buffer controls for each detected voice segment:
  - Play: Listen to individual segments
  - Repeat: Mark segments for repetition in output
  - Exclude: Hide segments from processing
  - Up/Down: Reorder segments
  - Merge: Combine multiple segments

### Advanced Features
- **Buffer Reordering**: Move buffers up and down to change their order
- **Buffer Merging**: Combine multiple selected buffers into one
- **Buffer Exclusion**: Hide buffers from processing with undo capability
- **Repeat Selection**: Mark specific buffers for repetition in the output
- **Status Updates**: Real-time feedback on buffer states and operations

### Output Processing
- Customizable output filename
- Selectable output directory
- High-quality WAV output with:
  - 16-bit PCM encoding
  - 44.1kHz sample rate
  - Stereo output
- Automatic silence insertion:
  - 2 seconds after first buffer
  - 1.5x buffer duration before/after repeated buffers

## Usage

1. **Load Audio**
   - Click "Browse" to select an input audio file
   - Supported formats: M4A, MP3, WAV

2. **Process Buffers**
   - Use "Play" to preview individual segments
   - Use "Repeat" to mark segments for repetition
   - Use "Exclude" to hide segments from processing
   - Use "Up/Down" to reorder segments
   - Use "Merge Selected" to combine multiple segments

3. **Undo Operations**
   - Use "Undo Exclude" to restore the last excluded buffer

4. **Save Output**
   - Select output directory
   - Enter output filename
   - Click "Process and Save"

## Requirements

- Windows 10 or later
- FFmpeg (included in the executable)

## Building from Source

1. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the build script:
   ```
   python build.py
   ```

The executable will be created in the `dist` directory.

## Recent Changes

- Added support for WAV and MP3 file formats
- Implemented buffer exclusion with undo functionality
- Added buffer reordering (up/down) capabilities
- Enhanced status messages for better user feedback
- Improved merge operation with proper checkbox clearing
- Added automatic silence insertion for better audio flow
- Implemented high-quality audio output settings 