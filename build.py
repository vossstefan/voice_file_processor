import PyInstaller.__main__
import os

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the paths
script_path = os.path.join(current_dir, 'voice_buffer_gui.py')
icon_path = os.path.join(current_dir, 'icon.ico')  # If you have an icon
dist_path = os.path.join(current_dir, 'dist')
build_path = os.path.join(current_dir, 'build')

# PyInstaller arguments
args = [
    script_path,
    '--name=VoiceBufferSplitter',
    '--onefile',
    '--windowed',
    f'--distpath={dist_path}',
    f'--workpath={build_path}',
    '--clean',
    '--noconfirm',
]

# Add icon if it exists
if os.path.exists(icon_path):
    args.append(f'--icon={icon_path}')

# Add hidden imports
args.extend([
    '--hidden-import=webrtcvad',
    '--hidden-import=pydub',
    '--hidden-import=simpleaudio',
    '--hidden-import=numpy',
    '--hidden-import=dearpygui',
])

# Run PyInstaller
PyInstaller.__main__.run(args)

print("Build completed! The executable can be found in the 'dist' directory.") 