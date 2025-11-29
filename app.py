import os
import subprocess
import time
import numpy as np
import PIL.Image
from PIL import Image, ImageDraw, ImageFont

# ============================================================
#  FIX: PATCH FOR PILLOW 10+ (Fixes the ANTIALIAS error)
# ============================================================
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ============================================================

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips
)
from deep_translator import GoogleTranslator
import arabic_reshaper
from bidi.algorithm import get_display

# === CONFIGURATION ===
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
OUTPUT_FOLDER = "result"  # Folder name for outputs

# NOTE: Ensure these paths are correct relative to app.py
FONT_PATH = "content/THEBOLDFONT-FREEVERSION.ttf" 
ARABIC_FONT_PATH = "content/NotoSansArabic-Bold.ttf"

LANGUAGES = {
    "Spanish":    ("es", "es-ES-AlvaroNeural"),
    "French":     ("fr", "fr-FR-HenriNeural"),
    "Arabic":     ("ar", "ar-SA-HamedNeural"),
    "Portuguese": ("pt", "pt-BR-AntonioNeural"),
    "German":     ("de", "de-DE-ConradNeural"),
    "Turkish":    ("tr", "tr-TR-AhmetNeural"),
}

# ============================================================
#                    TTS AUDIO (CLI MODE)
# ============================================================
def generate_audio_male_only(text, voice_name, output_file):
    if os.path.exists(output_file):
        os.remove(output_file)
    
    print(f"  [edge-tts] Generating: {voice_name}")
    
    command = [
        "edge-tts",
        "--text", text,
        "--voice", voice_name,
        "--write-media", output_file
    ]
    
    try:
        # shell=True helps Windows find the command
        subprocess.run(command, capture_output=True, text=True, shell=True)

        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            return True
        else:
            print("  [Error] File not created. Check if edge-tts is installed.")
            return False
    except Exception as e:
        print(f"  [Error] {e}")
        return False

# ============================================================
#                    TEXT IMAGES
# ============================================================
def create_pil_text_image(text, video_w, video_h, lang_code='en'):
    img = Image.new('RGBA', (video_w, video_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    final_text = text

    if lang_code == 'ar':
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            final_text = get_display(reshaped_text)
        except:
            pass

    target_font_size = int(video_w * (0.10 if lang_code == 'ar' else 0.13))
    
    font_to_use = ARABIC_FONT_PATH if lang_code == 'ar' else FONT_PATH
    
    if os.path.exists(font_to_use):
        try:
            font = ImageFont.truetype(font_to_use, target_font_size)
        except:
            font = ImageFont.load_default()
    else:
        try:
            font = ImageFont.truetype("arial.ttf", target_font_size)
        except:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), final_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x_pos = (video_w - text_w) // 2
    y_pos = (video_h - text_h) // 2

    # Outline
    for ox, oy in [(-4,-4), (-4,4), (4,-4), (4,4), (0,5), (0,-5), (5,0), (-5,0)]:
        draw.text((x_pos + ox, y_pos + oy), final_text, font=font, fill="black")

    draw.text((x_pos, y_pos), final_text, font=font, fill="#FFD700")
    return np.array(img)

# ============================================================
#                    VIDEO CREATION
# ============================================================
def create_cinematic_video(video_paths, audio_path, captions_list, output_path, lang_code):
    print(f"  [Video] Rendering {output_path}...")
    processed_clips = []

    for path in video_paths:
        if os.path.exists(path):
            try:
                clip = VideoFileClip(path)
                scale = max(TARGET_WIDTH / clip.w, TARGET_HEIGHT / clip.h)
                clip = clip.resize(scale * 1.05)
                clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_WIDTH, height=TARGET_HEIGHT)
                clip = clip.resize(lambda t: 1 + 0.03 * t)
                processed_clips.append(clip)
            except Exception as e:
                print(f"  [Error] Could not load {path}: {e}")
        else:
            print(f"  [Warning] Video not found: {path}")

    if not processed_clips: return False

    final_bg = concatenate_videoclips(processed_clips, method="compose")
    final_bg = final_bg.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))

    try:
        audio = AudioFileClip(audio_path)
        if audio.duration > final_bg.duration:
            loops = int(audio.duration / final_bg.duration) + 1
            final_bg = concatenate_videoclips([final_bg] * loops)
        final_bg = final_bg.subclip(0, audio.duration).set_audio(audio)
    except:
        return False

    text_clips = []
    current_time = 0.0
    duration_per_sentence = final_bg.duration / len(captions_list)

    for sentence in captions_list:
        words = sentence.split()
        if not words: continue
        duration_per_word = duration_per_sentence / len(words)
        for word in words:
            img_arr = create_pil_text_image(word.upper(), TARGET_WIDTH, TARGET_HEIGHT, lang_code)
            txt_clip = (ImageClip(img_arr)
                        .set_start(current_time)
                        .set_duration(duration_per_word)
                        .set_position('center')
                        .resize(lambda t: 0.9 + 0.3 * t))
            text_clips.append(txt_clip)
            current_time += duration_per_word

    final_video = CompositeVideoClip([final_bg] + text_clips, size=(TARGET_WIDTH, TARGET_HEIGHT))
    
    final_video.write_videofile(
        output_path, codec="libx264", audio_codec="aac", fps=30, 
        threads=4, preset="ultrafast", logger=None
    )
    
    final_video.close()
    for clip in processed_clips: clip.close()
    return True

# ============================================================
#                    RUN
# ============================================================
if __name__ == "__main__":
    
    # 1. Ensure result folder exists
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Created folder: {OUTPUT_FOLDER}")

    # 2. Your video paths
    videos = ["videos/winter1.mp4", "videos/winter2.mp4", "videos/winter3.mp4"]
    
    captions = [
        "Pumpkin seeds deliver rich daily nourishment",
        "Their natural antioxidants help protect cells",
        "A simple daily handful supports strength"
    ]

    print("STARTING...")
    
    for lang_name, (lang_code, voice_name) in LANGUAGES.items():
        print(f"\nProcessing {lang_name}...")
        
        # Translate
        trans_captions = []
        for cap in captions:
            try:
                t = GoogleTranslator(source='auto', target=lang_code).translate(cap)
                trans_captions.append(t)
            except:
                trans_captions.append(cap)
        
        # Audio
        # We save temp audio in the main folder to keep things clean
        audio_file = f"temp_{lang_code}.mp3"
        
        # We save video in the RESULT folder
        output_video_path = os.path.join(OUTPUT_FOLDER, f"Output_{lang_name}.mp4")

        full_text = " ".join(trans_captions)
        
        if generate_audio_male_only(full_text, voice_name, audio_file):
            create_cinematic_video(videos, audio_file, trans_captions, output_video_path, lang_code)
            
            # Clean up audio
            if os.path.exists(audio_file): os.remove(audio_file)
            print(f"  -> Saved to: {output_video_path}")
    
    print("\nDONE!")