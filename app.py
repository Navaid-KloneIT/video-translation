import os
import time
import numpy as np
import PIL.Image
from PIL import Image, ImageDraw, ImageFont
import datetime
import logging
import asyncio 
import edge_tts 
import warnings # <--- ADDED: To manage warnings

# ============================================================
#  SUPPRESS FFmpeg WARNINGS
# ============================================================
# This stops the "bytes wanted but 0 bytes read" spam in the console
warnings.filterwarnings("ignore", category=UserWarning, module="moviepy")

# ============================================================
#  LOGGING SETUP
# ============================================================
def setup_logging():
    log_folder = "logs"
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_folder, f"execution_log_{timestamp}.txt")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"📁 Log file created at: {log_file}")

# ============================================================
#  CUSTOM TIMER CLASS
# ============================================================
class Timer:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.start_time = time.time()
        logging.info(f"⏱️  [START] {self.name}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        logging.info(f"✅ [DONE]  {self.name} took {self.duration:.2f} seconds.")

# ============================================================
#  FIX: PATCH FOR PILLOW 10+
# ============================================================
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

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
OUTPUT_FOLDER = "result"
TEMP_FOLDER = "temp"

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
#  TTS AUDIO
# ============================================================
async def _generate_audio_async(text, voice, output_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def generate_audio_male_only(text, voice_name, output_file):
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))

    if os.path.exists(output_file):
        os.remove(output_file)
    
    try:
        asyncio.run(_generate_audio_async(text, voice_name, output_file))

        if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
            return True
        else:
            logging.error("  [Error] Audio file was not created (unknown reason).")
            return False
    except Exception as e:
        logging.error(f"  [Error] Failed to generate audio: {e}")
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

    for ox, oy in [(-4,-4), (-4,4), (4,-4), (4,4), (0,5), (0,-5), (5,0), (-5,0)]:
        draw.text((x_pos + ox, y_pos + oy), final_text, font=font, fill="black")

    draw.text((x_pos, y_pos), final_text, font=font, fill="#FFD700")
    return np.array(img)

# ============================================================
#                    VIDEO CREATION
# ============================================================
def create_cinematic_video(video_paths, audio_path, captions_list, output_path, lang_code):
    logging.info(f"  [Video] Preparing assets for {output_path}...")
    processed_clips = []

    for path in video_paths:
        if os.path.exists(path):
            try:
                clip = VideoFileClip(path)
                
                # --- FIX 1: Remove Audio Track (Prevents duration mismatch) ---
                clip = clip.without_audio()
                
                # --- FIX 2: Aggressive trim (0.15s) to avoid bad frames at end ---
                if clip.duration > 0.2:
                    clip = clip.subclip(0, clip.duration - 0.15)
                
                # Resize logic
                scale = max(TARGET_WIDTH / clip.w, TARGET_HEIGHT / clip.h)
                clip = clip.resize(scale * 1.05)
                clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_WIDTH, height=TARGET_HEIGHT)
                clip = clip.resize(lambda t: 1 + 0.03 * t)
                processed_clips.append(clip)
            except Exception as e:
                logging.error(f"  [Error] Could not load {path}: {e}")
        else:
            logging.warning(f"  [Warning] Video not found: {path}")

    if not processed_clips:
        logging.error("  [Error] No video clips loaded. Cannot create video.")
        return False

    final_bg = concatenate_videoclips(processed_clips, method="compose")
    final_bg = final_bg.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))

    try:
        audio = AudioFileClip(audio_path)
        if audio.duration > final_bg.duration:
            loops = int(audio.duration / final_bg.duration) + 1
            final_bg = concatenate_videoclips([final_bg] * loops)
        
        # Ensure final cut aligns exactly with audio
        final_bg = final_bg.subclip(0, audio.duration).set_audio(audio)
    except Exception as e:
        logging.error(f"  [Error] Audio processing failed: {e}")
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
    
    with Timer(f"Render MoviePy ({lang_code})"):
        # Added verbose=False to reduce terminal clutter
        final_video.write_videofile(
            output_path, codec="libx264", audio_codec="aac", fps=30, 
            threads=4, preset="ultrafast", logger=None, verbose=False
        )
    
    final_video.close()
    for clip in processed_clips: clip.close()
    return True

# ============================================================
#                    RUN
# ============================================================
if __name__ == "__main__":
    
    setup_logging()
    
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        logging.info(f"Created folder: {OUTPUT_FOLDER}")

    if not os.path.exists(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)
        logging.info(f"Created folder: {TEMP_FOLDER}")

    videos = ["videos/winter1.mp4", "videos/winter2.mp4", "videos/winter3.mp4", "videos/winter4.mp4", "videos/winter5.mp4", "videos/winter6.mp4"]
    
    captions = [
        "Winter can challenge the body's balance. Eating pistachios daily adds valuable nutrients.",
        "Their antioxidants begin supporting natural defenses. The body absorbs their benefits smoothly.",
        "Immune cells stay active and ready. Healthy fats gently support circulation.",
        "Vitamin E helps nourish skin in dry winter air. Protein and fiber provide steady energy.",
        "B-vitamins help maintain a stable mood. Together, these nutrients support whole-body balance.",
        "Just remember, a small handful is enough. Enjoy pistachios as a healthy winter habit."
    ]

    logging.info(">>> STARTING PIPELINE")
    
    with Timer("Total Script Execution"):
        
        for lang_name, (lang_code, voice_name) in LANGUAGES.items():
            logging.info(f"--------------------------------------------------")
            logging.info(f"Processing Language: {lang_name}")
            logging.info(f"--------------------------------------------------")
            
            with Timer(f"Full Loop for {lang_name}"):
                
                # --- STEP 1: TRANSLATE ---
                trans_captions = []
                with Timer("Translation"):
                    for cap in captions:
                        try:
                            t = GoogleTranslator(source='auto', target=lang_code).translate(cap)
                            trans_captions.append(t)
                        except Exception as e:
                            logging.warning(f"Translation failed for '{cap}': {e}")
                            trans_captions.append(cap)
                
                # --- STEP 2: AUDIO ---
                audio_filename = f"temp_{lang_code}.mp3"
                audio_file_path = os.path.join(TEMP_FOLDER, audio_filename)
                
                full_text = " ".join(trans_captions)
                audio_success = False
                
                with Timer("Audio Generation (Edge-TTS)"):
                    audio_success = generate_audio_male_only(full_text, voice_name, audio_file_path)

                # --- STEP 3: VIDEO ---
                output_video_path = os.path.join(OUTPUT_FOLDER, f"Output_{lang_name}.mp4")
                
                if audio_success:
                    with Timer("Video Processing Setup & Render"):
                        create_cinematic_video(videos, audio_file_path, trans_captions, output_video_path, lang_code)
                    
                    if os.path.exists(audio_file_path): os.remove(audio_file_path)
                    logging.info(f"  -> Saved to: {output_video_path}")
                else:
                    logging.error("  [SKIP] Skipping video generation because audio failed.")
            
    logging.info(">>> PIPELINE FINISHED!")