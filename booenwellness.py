import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips
)

# Fix for newer Pillow versions
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS
    
# === CONFIGURATION ===
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
FONT_PATH = "content/THEBOLDFONT-FREEVERSION.ttf"

# === 1. WATERMARK GENERATOR (UPDATED: CENTERED) ===
def create_watermark_image(text, video_w, video_h):
    img = Image.new('RGBA', (video_w, video_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Adjusted size slightly larger for center visibility if desired, 
    # or keep at 0.04. Let's keep it standard but centered.
    font_size = int(video_w * 0.05) 
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # --- CHANGE: Calculate Center Coordinates ---
    x_pos = (video_w - text_w) // 2
    y_pos = (video_h - text_h) // 2

    # Draw text (White with transparency)
    draw.text((x_pos, y_pos), text, font=font, fill=(255, 255, 255, 140))
    return np.array(img)

# === VIDEO COMPOSITOR ===
def create_cinematic_video(video_paths, captions_list, output_path):
    print(f"--- Processing {len(video_paths)} videos ---")

    # === STEP 1: Prepare Background Video ===
    processed_clips = []

    for path in video_paths:
        try:
            clip = VideoFileClip(path)
            
            # Resize logic
            ratio_w = TARGET_WIDTH / clip.w
            ratio_h = TARGET_HEIGHT / clip.h
            scale_factor = max(ratio_w, ratio_h)
            clip = clip.resize(scale_factor * 1.05)
            
            # Center Crop
            clip = clip.crop(
                x_center=clip.w / 2,
                y_center=clip.h / 2,
                width=TARGET_WIDTH,
                height=TARGET_HEIGHT
            )
            processed_clips.append(clip)
        except Exception as e:
            print(f"Skipping bad file {path}: {e}")

    if not processed_clips:
        print("Error: No valid clips created.")
        return

    final_bg = concatenate_videoclips(processed_clips, method="compose")
    
    if final_bg.size != (TARGET_WIDTH, TARGET_HEIGHT):
        final_bg = final_bg.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))
    
    total_duration = final_bg.duration

    # === STEP 2: Main Captions (REMOVED) ===
    # The loop that generated word-by-word captions has been removed.
    # We still accept 'captions_list' as an argument to avoid breaking the calling function,
    # but we don't use it.

    # === STEP 3: Watermark (CENTERED) ===
    watermark_arr = create_watermark_image("Booen Wellness", TARGET_WIDTH, TARGET_HEIGHT)
    watermark_clip = (ImageClip(watermark_arr)
                      .set_start(0)
                      .set_duration(total_duration)
                      .set_position('center'))

    # === STEP 4: Render ===
    print(f"Rendering {output_path}...")
    
    # --- CHANGE: Removed text_clips from the list below ---
    final_video = CompositeVideoClip(
        [final_bg, watermark_clip],
        size=(TARGET_WIDTH, TARGET_HEIGHT)
    )

    final_video.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        threads=8,
        preset="ultrafast",
        ffmpeg_params=["-vf", "scale=1080:1920", "-aspect", "9:16"],
        logger=None
    )

    final_video.close()
    for c in processed_clips: c.close()
    print(f"Done! Saved to: {output_path}")

# ================= DYNAMIC FOLDER LOADER =================

def get_category_content(category_folder_path):
    """
    Reads videos and captions.txt from a specific folder path.
    """
    video_extensions = ('.mp4', '.mov', '.avi', '.mkv')
    video_files = []
    
    # Get all video files in the folder
    if os.path.exists(category_folder_path):
        files = sorted(os.listdir(category_folder_path))
        for f in files:
            if f.lower().endswith(video_extensions):
                video_files.append(os.path.join(category_folder_path, f))
    
    # Get captions (files are still read, but not used in rendering)
    caption_lines = []
    caption_path = os.path.join(category_folder_path, "captions.txt")
    if os.path.exists(caption_path):
        with open(caption_path, "r", encoding="utf-8") as f:
            caption_lines = [line.strip() for line in f.readlines() if line.strip()]
    
    return video_files, caption_lines

if __name__ == "__main__":
    BASE_DIR = "booenwellness"
    RESULT_DIR = "booenwellness"

    # Ensure source folder exists
    if not os.path.exists(BASE_DIR):
        print(f"CRITICAL: '{BASE_DIR}' folder not found. Please create it.")
        exit()

    # Get all subdirectories inside 'videos'
    categories = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]

    if not categories:
        print(f"No subfolders found inside '{BASE_DIR}'.")
    else:
        print(f"Found categories: {categories}")

        for category in categories:
            print(f"\n=== Processing Category: {category} ===")
            
            # 1. Get Source Content
            category_path = os.path.join(BASE_DIR, category)
            videos, captions = get_category_content(category_path)

            if not videos:
                print(f"Skipping '{category}': No videos found.")
                continue
            
            # 2. Create Dynamic Output Folder Structure
            output_folder_path = os.path.join(RESULT_DIR, category)
            os.makedirs(output_folder_path, exist_ok=True)
            
            # 3. Define Output Filename
            output_filename = os.path.join(output_folder_path, f"{category}_final.mp4")
            
            # 4. Generate Video
            create_cinematic_video(videos, captions, output_filename)