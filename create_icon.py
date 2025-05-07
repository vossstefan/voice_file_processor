from PIL import Image, ImageDraw

# Create a 256x256 image with a white background
img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
draw = ImageDraw.Draw(img)

# Draw a simple sound wave icon
# Draw three curved lines
for i in range(3):
    y = 128 + (i - 1) * 40
    draw.arc([50, y-20, 206, y+20], 0, 180, fill='black', width=8)

# Save as ICO
img.save('icon.ico', format='ICO', sizes=[(256, 256)]) 