import os
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"

import dearpygui.dearpygui as dpg
from pydub import AudioSegment
import webrtcvad
import tempfile
import threading
import traceback
import wave
import io
import simpleaudio as sa
import numpy as np
import time

# Global variables
current_playback = None
buffers = []
speech_regions = []
buffer_descriptions = []
selected_buffers = set()
excluded_buffers = set()  # New set for excluded buffers
excluded_buffer_history = []  # Stack to track excluded buffers for undo
audio = None
merge_buffers = set()
last_input_dir = os.path.join(os.getcwd(), "raw")  # Initialize with default paths
last_output_dir = os.path.join(os.getcwd(), "processed")

def play_audiosegment(segment):
    global current_playback
    try:
        # Stop any existing playback
        if current_playback is not None:
            current_playback.stop()
            current_playback = None
            time.sleep(0.1)  # Small delay to ensure clean stop
        
        # Convert to raw PCM data
        samples = np.array(segment.get_array_of_samples())
        
        # Get audio parameters
        channels = segment.channels
        sample_width = segment.sample_width
        frame_rate = segment.frame_rate
        
        # Play using simpleaudio
        current_playback = sa.play_buffer(
            samples.tobytes(), 
            num_channels=channels,
            bytes_per_sample=sample_width,
            sample_rate=frame_rate
        )
        
        # Wait for playback to finish
        current_playback.wait_done()
        current_playback = None
            
    except Exception as e:
        print(f"Playback error: {str(e)}")
        traceback.print_exc()

def detect_voice_buffers(audio, aggressiveness=2, frame_ms=30):
    audio = audio.set_channels(1).set_frame_rate(16000)
    raw_audio = audio.raw_data
    vad = webrtcvad.Vad(aggressiveness)  # Reduced aggressiveness for less strict detection
    frame_bytes = int(audio.frame_rate * frame_ms / 1000 * 2)
    frames = [raw_audio[i:i+frame_bytes] for i in range(0, len(raw_audio), frame_bytes)]
    speech_regions = []
    is_speech = False
    start = 0
    silence_frames = 0
    max_silence_frames = int(200 / frame_ms)  # Increased from 20ms to 50ms for more lenient detection
    merge_silence_frames = int(300 / frame_ms)  # 0.3 second threshold for merging
    
    # First pass: detect speech regions
    for i, frame in enumerate(frames):
        if len(frame) < frame_bytes:
            break
        if vad.is_speech(frame, audio.frame_rate):
            if not is_speech:
                start = i * frame_ms
                is_speech = True
            silence_frames = 0
        else:
            if is_speech:
                silence_frames += 1
                if silence_frames >= max_silence_frames:
                    end = (i - silence_frames) * frame_ms
                    speech_regions.append((start, end))
                    is_speech = False
                    silence_frames = 0
    if is_speech:
        speech_regions.append((start, len(frames) * frame_ms))
    
    # Second pass: merge regions
    filtered_regions = []
    filtered_buffers = []
    for start, end in speech_regions:
        if end - start >= 500:  # Keep only buffers >= 1 second
            filtered_regions.append((start, end))
            filtered_buffers.append(audio[start:end])
    
    return filtered_regions, filtered_buffers

def play_buffer(sender, app_data, user_data):
    global buffers
    idx = user_data
    if 0 <= idx < len(buffers):
        threading.Thread(target=play_audiosegment, args=(buffers[idx],), daemon=True).start()
        dpg.set_value("status", f"Playing buffer {idx}...")

def select_input_file(sender, app_data):
    global last_input_dir
    if app_data['file_path_name']:
        dpg.set_value("file_selector", app_data['file_path_name'])
        last_input_dir = os.path.dirname(app_data['file_path_name'])
        
        # Set default output filename based on input filename
        input_filename = os.path.basename(app_data['file_path_name'])
        output_filename = input_filename.rsplit('.', 1)[0] + '-processed.wav'
        dpg.set_value("output_file", output_filename)
        
        load_audio(None, None)

def load_audio(sender, app_data):
    global audio, buffers, speech_regions, buffer_descriptions, selected_buffers, merge_buffers, excluded_buffers
    
    try:
        infile = dpg.get_value("file_selector")
        if not infile:
            dpg.set_value("status", "No file selected")
            return
            
        print(f"Attempting to open: {infile}")
        print(f"File exists: {os.path.exists(infile)}")
        
        # Reset all selections and states when loading a new file
        selected_buffers.clear()  # Clear repeat selections
        merge_buffers.clear()     # Clear merge selections
        excluded_buffers.clear()  # Clear excluded buffers
        
        # Get file extension
        file_ext = os.path.splitext(infile)[1].lower()
        
        # Load audio based on file type
        if file_ext == '.m4a':
            audio = AudioSegment.from_file(infile, format='m4a', codec='aac')
        elif file_ext == '.mp3':
            audio = AudioSegment.from_file(infile, format='mp3')
        elif file_ext == '.wav':
            audio = AudioSegment.from_file(infile, format='wav')
        else:
            dpg.set_value("status", f"Unsupported file format: {file_ext}")
            return
            
        print(f"Successfully loaded audio file: {len(audio)}ms duration")
        speech_regions, buffers = detect_voice_buffers(audio)
        print(f"Detected {len(buffers)} voice regions")
        
        # Clear old controls
        dpg.delete_item("buffer_group", children_only=True)
        
        # Create buffer descriptions and add controls
        buffer_descriptions = []
        for idx, (region, buf) in enumerate(zip(speech_regions, buffers)):
            start, end = region
            dur = (end - start) / 1000.0
            desc = f'Buffer {idx}: {start}ms - {end}ms ({dur:.2f}s)'
            buffer_descriptions.append(desc)
        
        # Refresh the buffer list with all controls
        refresh_buffer_list()
        
        dpg.set_value("status", f"Loaded {len(buffers)} buffers.")
        
    except Exception as e:
        print(f"Error details: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()
        dpg.set_value("status", f"Error loading file: {str(e)}")

def toggle_repeat(sender, app_data, user_data):
    global selected_buffers
    idx = user_data
    if idx in selected_buffers:
        selected_buffers.remove(idx)
        dpg.configure_item(sender, label="Repeat")
    else:
        selected_buffers.add(idx)
        dpg.configure_item(sender, label="Repeating")
    
    # Update status with current buffer descriptions
    selected_descriptions = [buffer_descriptions[i] for i in sorted(selected_buffers)]
    dpg.set_value("status", f'Selected buffers for repetition: {", ".join(selected_descriptions)}')

def toggle_merge(sender, app_data, user_data):
    global merge_buffers
    idx = user_data
    if idx in merge_buffers:
        merge_buffers.remove(idx)
    else:
        merge_buffers.add(idx)
    
    # Update status with current buffer descriptions
    merge_descriptions = [buffer_descriptions[i] for i in sorted(merge_buffers)]
    dpg.set_value("status", f'Selected buffers for merging: {", ".join(merge_descriptions)}')

def toggle_exclude(sender, app_data, user_data):
    global excluded_buffers, excluded_buffer_history
    idx = user_data
    if idx in excluded_buffers:
        excluded_buffers.remove(idx)
        dpg.configure_item(sender, label="Exclude")
    else:
        excluded_buffers.add(idx)
        # Store the buffer info for undo
        excluded_buffer_history.append({
            'index': idx,
            'buffer': buffers[idx],
            'region': speech_regions[idx],
            'description': buffer_descriptions[idx],
            'was_selected': idx in selected_buffers,
            'was_merge_selected': idx in merge_buffers
        })
        dpg.configure_item(sender, label="Excluded")
    
    # Update status with current buffer descriptions
    excluded_descriptions = [buffer_descriptions[i] for i in sorted(excluded_buffers)]
    dpg.set_value("status", f'Excluded buffers: {", ".join(excluded_descriptions)}')
    
    # Refresh the buffer list to update visibility
    refresh_buffer_list()

def undo_exclude(sender, app_data):
    global excluded_buffers, excluded_buffer_history, buffers, speech_regions, buffer_descriptions, selected_buffers, merge_buffers
    
    if not excluded_buffer_history:
        dpg.set_value("status", "No excluded buffers to restore")
        return
    
    # Get the last excluded buffer info
    last_excluded = excluded_buffer_history.pop()
    idx = last_excluded['index']
    
    # Remove from excluded set
    excluded_buffers.remove(idx)
    
    # Restore the buffer
    buffers[idx] = last_excluded['buffer']
    speech_regions[idx] = last_excluded['region']
    buffer_descriptions[idx] = last_excluded['description']
    
    # Restore selection states
    if last_excluded['was_selected']:
        selected_buffers.add(idx)
    if last_excluded['was_merge_selected']:
        merge_buffers.add(idx)
    
    # Update buffer labels
    update_buffer_labels()
    
    # Refresh the buffer list
    refresh_buffer_list()
    
    # Update status
    dpg.set_value("status", f"Restored {buffer_descriptions[idx]}")

def move_buffer_up(sender, app_data, user_data):
    global buffers, speech_regions, buffer_descriptions
    idx = user_data
    if idx > 0:  # Can't move first buffer up
        # Swap buffers
        buffers[idx], buffers[idx-1] = buffers[idx-1], buffers[idx]
        speech_regions[idx], speech_regions[idx-1] = speech_regions[idx-1], speech_regions[idx]
        buffer_descriptions[idx], buffer_descriptions[idx-1] = buffer_descriptions[idx-1], buffer_descriptions[idx]
        
        # Update selected, excluded, and merge sets if needed
        if idx in selected_buffers:
            selected_buffers.remove(idx)
            selected_buffers.add(idx-1)
        if idx-1 in selected_buffers:
            selected_buffers.remove(idx-1)
            selected_buffers.add(idx)
            
        if idx in merge_buffers:
            merge_buffers.remove(idx)
            merge_buffers.add(idx-1)
        if idx-1 in merge_buffers:
            merge_buffers.remove(idx-1)
            merge_buffers.add(idx)
            
        if idx in excluded_buffers:
            excluded_buffers.remove(idx)
            excluded_buffers.add(idx-1)
        if idx-1 in excluded_buffers:
            excluded_buffers.remove(idx-1)
            excluded_buffers.add(idx)
        
        # Update buffer labels with new indices
        update_buffer_labels()
        
        # Refresh the buffer list
        refresh_buffer_list()
        
        # Update status with current buffer descriptions
        selected_descriptions = [buffer_descriptions[i] for i in sorted(selected_buffers)]
        excluded_descriptions = [buffer_descriptions[i] for i in sorted(excluded_buffers)]
        
        status_parts = []
        if selected_descriptions:
            status_parts.append(f'Selected for repetition: {", ".join(selected_descriptions)}')
        if excluded_descriptions:
            status_parts.append(f'Excluded: {", ".join(excluded_descriptions)}')
        
        status_message = f"Moved {buffer_descriptions[idx-1]} up"
        if status_parts:
            status_message += " | " + " | ".join(status_parts)
        
        dpg.set_value("status", status_message)

def move_buffer_down(sender, app_data, user_data):
    global buffers, speech_regions, buffer_descriptions
    idx = user_data
    if idx < len(buffers) - 1:  # Can't move last buffer down
        # Swap buffers
        buffers[idx], buffers[idx+1] = buffers[idx+1], buffers[idx]
        speech_regions[idx], speech_regions[idx+1] = speech_regions[idx+1], speech_regions[idx]
        buffer_descriptions[idx], buffer_descriptions[idx+1] = buffer_descriptions[idx+1], buffer_descriptions[idx]
        
        # Update selected, excluded, and merge sets if needed
        if idx in selected_buffers:
            selected_buffers.remove(idx)
            selected_buffers.add(idx+1)
        if idx+1 in selected_buffers:
            selected_buffers.remove(idx+1)
            selected_buffers.add(idx)
            
        if idx in merge_buffers:
            merge_buffers.remove(idx)
            merge_buffers.add(idx+1)
        if idx+1 in merge_buffers:
            merge_buffers.remove(idx+1)
            merge_buffers.add(idx)
            
        if idx in excluded_buffers:
            excluded_buffers.remove(idx)
            excluded_buffers.add(idx+1)
        if idx+1 in excluded_buffers:
            excluded_buffers.remove(idx+1)
            excluded_buffers.add(idx)
        
        # Update buffer labels with new indices
        update_buffer_labels()
        
        # Refresh the buffer list
        refresh_buffer_list()
        
        # Update status with current buffer descriptions
        selected_descriptions = [buffer_descriptions[i] for i in sorted(selected_buffers)]
        excluded_descriptions = [buffer_descriptions[i] for i in sorted(excluded_buffers)]
        
        status_parts = []
        if selected_descriptions:
            status_parts.append(f'Selected for repetition: {", ".join(selected_descriptions)}')
        if excluded_descriptions:
            status_parts.append(f'Excluded: {", ".join(excluded_descriptions)}')
        
        status_message = f"Moved {buffer_descriptions[idx+1]} down"
        if status_parts:
            status_message += " | " + " | ".join(status_parts)
        
        dpg.set_value("status", status_message)

def update_buffer_labels():
    # Update buffer descriptions with new indices
    new_descriptions = []
    for idx, (region, buf) in enumerate(zip(speech_regions, buffers)):
        start, end = region
        dur = (end - start) / 1000.0
        if "Merged Buffer" in buffer_descriptions[idx]:
            desc = f'Merged Buffer {idx}: {start}ms - {end}ms ({dur:.2f}s)'
        else:
            desc = f'Buffer {idx}: {start}ms - {end}ms ({dur:.2f}s)'
        new_descriptions.append(desc)
    buffer_descriptions.clear()
    buffer_descriptions.extend(new_descriptions)

def merge_selected(sender, app_data):
    global buffers, speech_regions, buffer_descriptions, selected_buffers, merge_buffers, excluded_buffers
    
    if not buffers:
        dpg.set_value("status", "No buffers loaded")
        return
        
    if len(merge_buffers) < 2:
        dpg.set_value("status", "Please select at least 2 buffers to merge")
        return
    
    try:
        # Sort selected indices to maintain order
        selected_indices = sorted(list(merge_buffers))
        
        # Create new merged buffer
        merged_buffer = AudioSegment.silent(duration=0)
        for idx in selected_indices:
            merged_buffer += buffers[idx]
        
        # Update buffers and descriptions
        new_buffers = []
        new_regions = []
        new_descriptions = []
        
        # Track which indices in the new list correspond to which old indices
        new_to_old_mapping = {}
        current_new_idx = 0
        
        # Add unselected buffers before the first selected one
        for i in range(selected_indices[0]):
            new_buffers.append(buffers[i])
            new_regions.append(speech_regions[i])
            new_descriptions.append(buffer_descriptions[i])
            new_to_old_mapping[current_new_idx] = i
            current_new_idx += 1
        
        # Add merged buffer
        new_buffers.append(merged_buffer)
        start_time = speech_regions[selected_indices[0]][0]
        end_time = speech_regions[selected_indices[-1]][1]
        new_regions.append((start_time, end_time))
        dur = (end_time - start_time) / 1000.0
        new_descriptions.append(f'Merged Buffer: {start_time}ms - {end_time}ms ({dur:.2f}s)')
        new_to_old_mapping[current_new_idx] = selected_indices[0]  # Map merged buffer to first selected buffer
        current_new_idx += 1
        
        # Add unselected buffers after the last selected one
        for i in range(selected_indices[-1] + 1, len(buffers)):
            new_buffers.append(buffers[i])
            new_regions.append(speech_regions[i])
            new_descriptions.append(buffer_descriptions[i])
            new_to_old_mapping[current_new_idx] = i
            current_new_idx += 1
        
        # Update global variables
        buffers = new_buffers
        speech_regions = new_regions
        buffer_descriptions = new_descriptions
        
        # Update selected and excluded buffers based on the new mapping
        new_selected = set()
        new_excluded = set()
        
        for new_idx, old_idx in new_to_old_mapping.items():
            if old_idx in selected_buffers:
                new_selected.add(new_idx)
            if old_idx in excluded_buffers:
                new_excluded.add(new_idx)
        
        selected_buffers = new_selected
        excluded_buffers = new_excluded
        
        # Update buffer labels with new indices
        update_buffer_labels()
        
        # Clear old controls
        dpg.delete_item("buffer_group", children_only=True)
        
        # Refresh the buffer list with all controls
        refresh_buffer_list()
        
        # Clear merge checkboxes and merge_buffers set
        merge_buffers.clear()
        for idx in range(len(buffers)):
            if idx not in excluded_buffers:  # Only clear checkboxes for visible buffers
                dpg.set_value(f"merge_{idx}", False)
        
        # Update status messages with new buffer descriptions
        selected_descriptions = [buffer_descriptions[i] for i in sorted(selected_buffers)]
        excluded_descriptions = [buffer_descriptions[i] for i in sorted(excluded_buffers)]
        
        status_parts = []
        if selected_descriptions:
            status_parts.append(f'Selected for repetition: {", ".join(selected_descriptions)}')
        if excluded_descriptions:
            status_parts.append(f'Excluded: {", ".join(excluded_descriptions)}')
        
        status_message = f"Merged {len(selected_indices)} buffers into one."
        if status_parts:
            status_message += " | " + " | ".join(status_parts)
        
        dpg.set_value("status", status_message)
        
    except Exception as e:
        print(f"Error merging buffers: {str(e)}")
        traceback.print_exc()
        dpg.set_value("status", "Error merging buffers")

def select_output_folder(sender, app_data):
    global last_output_dir
    if app_data['file_path_name']:
        dpg.set_value("output_folder", app_data['file_path_name'])
        last_output_dir = app_data['file_path_name']

def show_input_dialog():
    global last_input_dir
    if last_input_dir and os.path.exists(last_input_dir):
        dpg.set_value("input_file_dialog", last_input_dir)
    dpg.show_item("input_file_dialog")

def show_output_dialog():
    global last_output_dir
    if last_output_dir and os.path.exists(last_output_dir):
        dpg.set_value("output_folder_dialog", last_output_dir)
    dpg.show_item("output_folder_dialog")

def show_message(title, message):
    def close_message(sender, app_data):
        dpg.delete_item(dpg.last_root_window())
    
    with dpg.window(label=title, modal=True, autosize=True, pos=[200, 200], tag="message_window"):
        dpg.add_text(message)
        dpg.add_button(label="OK", callback=close_message)

def process_and_save(sender, app_data):
    global audio, buffers, selected_buffers
    
    if not audio or not buffers:
        dpg.set_value("status", "No audio loaded or no buffers detected.")
        return
        
    outfolder = dpg.get_value("output_folder")
    outfile = dpg.get_value("output_file")
    if not outfolder or not outfile:
        dpg.set_value("status", "Please select output folder and filename.")
        return
        
    # Ensure output file has .wav extension
    if not outfile.endswith('.wav'):
        outfile = outfile.rsplit('.', 1)[0] + '.wav'
        
    output = AudioSegment.silent(duration=0)
    
    # Get selected buffers for repetition
    repeat_indices = sorted(list(selected_buffers))
    
    # Process all buffers
    for i, buf in enumerate(buffers):
        # Skip excluded buffers
        if i in excluded_buffers:
            continue
            
        # If this buffer is selected for repetition, add silence before first instance
        if i in repeat_indices:
            silence_duration = int(len(buf) * 1.5)
            output += AudioSegment.silent(duration=silence_duration)
        
        # Add the buffer
        output += buf
        
        # Add 2 seconds of silence after the first buffer
        if i == 0:
            output += AudioSegment.silent(duration=2000)
        
        # If this buffer is selected for repetition
        if i in repeat_indices:
            # Calculate silence duration (1.5x buffer duration)
            silence_duration = int(len(buf) * 1.5)
            
            # Add silence before the repeated buffer
            output += AudioSegment.silent(duration=silence_duration)
            
            # Add the buffer again
            output += buf
            
            # Add silence after the repeated buffer
            output += AudioSegment.silent(duration=silence_duration)
                
    try:
        # Create output directory if it doesn't exist
        os.makedirs(outfolder, exist_ok=True)
        
        # Construct the full output path
        outpath = os.path.abspath(os.path.join(outfolder, outfile))
        print(f"Saving to: {outpath}")
        
        # Export as WAV with maximum quality
        output.export(
            outpath,
            format='wav',
            parameters=[
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-ar', '44100',          # 44.1kHz sample rate
                '-ac', '2'               # Stereo
            ]
        )
        
        # Show success message
        print("File successfully saved!")
        dpg.set_value("status", f'Successfully saved to {outpath}')
    except Exception as e:
        print(f"Error saving file: {str(e)}")
        traceback.print_exc()
        dpg.set_value("status", f'Error saving file: {e}')

def refresh_buffer_list():
    # Clear old controls
    dpg.delete_item("buffer_group", children_only=True)
    
    # Add new controls
    for idx, desc in enumerate(buffer_descriptions):
        # Skip excluded buffers
        if idx in excluded_buffers:
            continue
            
        with dpg.group(parent="buffer_group", horizontal=True):
            dpg.add_checkbox(label="Merge", tag=f"merge_{idx}", callback=toggle_merge, user_data=idx)
            dpg.add_text(desc)
            dpg.add_button(label="Play", tag=f"play_{idx}", callback=play_buffer, user_data=idx)
            dpg.add_button(label="Repeat", tag=f"repeat_{idx}", callback=toggle_repeat, user_data=idx)
            dpg.add_button(label="Up", tag=f"up_{idx}", callback=move_buffer_up, user_data=idx)
            dpg.add_button(label="Down", tag=f"down_{idx}", callback=move_buffer_down, user_data=idx)
            dpg.add_button(label="Exclude", tag=f"exclude_{idx}", callback=toggle_exclude, user_data=idx)
            
            # Update checkbox and button states
            if idx in merge_buffers:
                dpg.set_value(f"merge_{idx}", True)
            if idx in selected_buffers:
                dpg.configure_item(f"repeat_{idx}", label="Repeating")

def main():
    global merge_buffers
    
    dpg.create_context()
    dpg.create_viewport(title="Voice Buffer Splitter", width=800, height=600)
    dpg.setup_dearpygui()
    
    merge_buffers = set()  # Initialize merge_buffers set
    
    # Create file dialogs
    with dpg.file_dialog(
        directory_selector=True, 
        show=False,
        callback=select_output_folder,
        tag="output_folder_dialog",
        width=700,
        height=400
    ):
        dpg.add_file_extension("")
        
    with dpg.file_dialog(
        show=False,
        callback=select_input_file,
        tag="input_file_dialog",
        width=700,
        height=400
    ):
        dpg.add_file_extension(".m4a")
        dpg.add_file_extension(".mp3")
        dpg.add_file_extension(".wav")
    
    with dpg.window(label="Voice Buffer Splitter", tag="Primary Window"):
        dpg.add_text("Select input audio file:")
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="file_selector", readonly=True, width=400)
            dpg.add_button(label="Browse", callback=lambda: dpg.show_item("input_file_dialog"))
        
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_text("Voice Buffers:")
            dpg.add_button(label="Merge Selected", callback=merge_selected)
            dpg.add_button(label="Undo Exclude", callback=undo_exclude)
        
        dpg.add_text("Use checkboxes to select buffers to merge, and 'Repeat' buttons to mark buffers for repetition:")
        with dpg.child_window(tag="buffer_window", height=300):
            dpg.add_group(tag="buffer_group")
        
        dpg.add_separator()
        
        dpg.add_text("Select output folder:")
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="output_folder", readonly=True, width=400)
            dpg.add_button(label="Browse", callback=lambda: dpg.show_item("output_folder_dialog"))
        
        dpg.add_text("Output filename:")
        dpg.add_input_text(tag="output_file", default_value="output-processed.wav")
        
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="Process and Save", callback=process_and_save)
            dpg.add_button(label="Exit", callback=lambda: dpg.stop_dearpygui())
        
        dpg.add_text("", tag="status")
    
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == '__main__':
    main() 