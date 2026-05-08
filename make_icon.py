from PIL import Image, ImageDraw, ImageFont
import os

# Create an image with a transparent background
size = (256, 256)
img = Image.new("RGBA", size, (255, 255, 255, 0))
draw = ImageDraw.Draw(img)

# Draw a modern rounded rectangle for the camera body
body_rect = [32, 64, 224, 192]
draw.rounded_rectangle(body_rect, radius=24, fill="#1e272e", outline="#00d2d3", width=8)

# Draw the lens
lens_center = (128, 128)
lens_radius = 40
draw.ellipse(
    [lens_center[0] - lens_radius, lens_center[1] - lens_radius, 
     lens_center[0] + lens_radius, lens_center[1] + lens_radius], 
    fill="#2f3542", outline="#00d2d3", width=6
)

# Draw a flash/shutter button
button_rect = [64, 48, 100, 64]
draw.rounded_rectangle(button_rect, radius=4, fill="#00d2d3")

# Save as ICO
img.save("icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
print("icon.ico created successfully")
