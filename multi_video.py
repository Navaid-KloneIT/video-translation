import os
import time
import numpy as np
import PIL.Image
from PIL import Image, ImageDraw, ImageFont
import datetime
import logging
import asyncio 
import edge_tts 
import warnings 
import glob

# ============================================================
#  SUPPRESS WARNINGS
# ============================================================
warnings.filterwarnings("ignore", category=UserWarning, module="moviepy")

# ============================================================
#  CONFIGURATION & SETTINGS
# ============================================================
BASE_VIDEO_DIR = "videos"
BASE_RESULT_DIR = "result"
BASE_TEMP_DIR = "temp"
BASE_LOG_DIR = "logs"

# --- ⚡ PERFORMANCE SETTINGS ⚡ ---
# FALSE = Static images (Very Fast)
# TRUE  = Zoom effects (Slow on CPU)
ENABLE_ZOOM_EFFECTS = False 

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# --- 🅰️ FONTS ---
# Make sure these files exist in your 'content/' folder
FONT_PATH = "content/THEBOLDFONT-FREEVERSION.ttf" 
ARABIC_FONT_PATH = "content/NotoSansArabic-Bold.ttf"
JAPANESE_FONT_PATH = "content/NotoSansJP-Bold.ttf" 

LANGUAGES = {
    "Spanish":    ("es", "es-ES-AlvaroNeural"),
    "French":     ("fr", "fr-FR-HenriNeural"),
    "Arabic":     ("ar", "ar-SA-HamedNeural"),
    "Portuguese": ("pt", "pt-BR-AntonioNeural"),
    "German":     ("de", "de-DE-ConradNeural"),
    "Turkish":    ("tr", "tr-TR-AhmetNeural"),
    "Japanese":   ("ja", "ja-JP-KeitaNeural"), 
}

# ============================================================
#  DYNAMIC LOGGING SETUP
# ============================================================
def setup_dynamic_logging(project_name):
    """
    Sets up logging to save inside logs/{project_name}/
    """
    # 1. Determine folder
    log_folder = os.path.join(BASE_LOG_DIR, project_name)
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)
    
    # 2. Reset existing handlers (so we don't write to previous folders)
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # 3. Create new log file
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_folder, f"log_{project_name}_{timestamp}.txt")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"📁 Log initialized for project: {project_name}")
    logging.info(f"   path: {log_file}")

# ============================================================
#  CUSTOM TIMER
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
#  PATCH PILLOW
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

# ============================================================
#  HELPER: LOAD ASSETS
# ============================================================
def get_video_files(folder_path):
    """Finds all .mp4 files in the folder and sorts them."""
    # Search for .mp4 files
    search_path = os.path.join(folder_path, "*.mp4")
    files = sorted(glob.glob(search_path))
    return files

def get_captions(folder_path):
    """Reads captions.txt from the folder."""
    txt_path = os.path.join(folder_path, "captions.txt")
    
    if not os.path.exists(txt_path):
        logging.error(f"❌ captions.txt not found in {folder_path}")
        return []
    
    with open(txt_path, "r", encoding="utf-8") as f:
        # Read lines and remove empty lines
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    return lines

# ============================================================
#  TTS AUDIO
# ============================================================
async def _generate_audio_async(text, voice, output_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def generate_audio_male_only(text, voice_name, output_file):
    # Ensure folder exists
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))

    if os.path.exists(output_file):
        os.remove(output_file)
    
    try:
        asyncio.run(_generate_audio_async(text, voice_name, output_file))

        if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
            return True
        else:
            logging.error("  [Error] Audio file was not created.")
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

    # Handle Arabic Reshaping
    if lang_code == 'ar':
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            final_text = get_display(reshaped_text)
        except:
            pass

    # --- FONT SELECTION LOGIC ---
    font_to_use = FONT_PATH # Default Latin Font
    
    if lang_code == 'ar':
        font_to_use = ARABIC_FONT_PATH
    elif lang_code == 'ja':
        font_to_use = JAPANESE_FONT_PATH

    # --- FONT SIZE LOGIC ---
    scale_factor = 0.13
    if lang_code == 'ar':
        scale_factor = 0.10
    elif lang_code == 'ja':
        scale_factor = 0.12 

    target_font_size = int(video_w * scale_factor)
    
    if os.path.exists(font_to_use):
        try:
            font = ImageFont.truetype(font_to_use, target_font_size)
        except:
            logging.warning(f"Could not load font {font_to_use}, using default.")
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

    # Draw Outline
    for ox, oy in [(-4,-4), (-4,4), (4,-4), (4,4), (0,5), (0,-5), (5,0), (-5,0)]:
        draw.text((x_pos + ox, y_pos + oy), final_text, font=font, fill="black")

    # Draw Text
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
                clip = clip.without_audio()
                
                # Trim to prevent EOF errors
                if clip.duration > 0.2:
                    clip = clip.subclip(0, clip.duration - 0.15)
                
                scale = max(TARGET_WIDTH / clip.w, TARGET_HEIGHT / clip.h)
                clip = clip.resize(scale * 1.05)
                clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_WIDTH, height=TARGET_HEIGHT)
                
                if ENABLE_ZOOM_EFFECTS:
                    clip = clip.resize(lambda t: 1 + 0.03 * t) 
                
                processed_clips.append(clip)
            except Exception as e:
                logging.error(f"  [Error] Could not load {path}: {e}")
        else:
            logging.warning(f"  [Warning] Video not found: {path}")

    if not processed_clips:
        logging.error("  [Error] No video clips loaded.")
        return False

    final_bg = concatenate_videoclips(processed_clips, method="compose")
    final_bg = final_bg.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))

    try:
        audio = AudioFileClip(audio_path)
        if audio.duration > final_bg.duration:
            loops = int(audio.duration / final_bg.duration) + 1
            final_bg = concatenate_videoclips([final_bg] * loops)
        
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
                        .set_position('center'))
            
            if ENABLE_ZOOM_EFFECTS:
                txt_clip = txt_clip.resize(lambda t: 0.9 + 0.3 * t)

            text_clips.append(txt_clip)
            current_time += duration_per_word

    final_video = CompositeVideoClip([final_bg] + text_clips, size=(TARGET_WIDTH, TARGET_HEIGHT))
    
    # --------------------------------------------------------
    # FIXED: REMOVED GPU CHECK TO PREVENT CRASH ON OLD DRIVERS
    # --------------------------------------------------------
    with Timer(f"Render (CPU Mode) ({lang_code})"):
        final_video.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac", 
            fps=30, 
            preset="ultrafast", # 'ultrafast' for speed, 'medium' for smaller file size
            threads=None,
            logger=None
        )
    
    final_video.close()
    for clip in processed_clips: clip.close()
    return True

# ============================================================
#                    RUN
# ============================================================
if __name__ == "__main__":
    
    # 1. Check if 'videos' folder exists
    if not os.path.exists(BASE_VIDEO_DIR):
        print(f"ERROR: '{BASE_VIDEO_DIR}' folder not found. Please create it and add subfolders.")
        exit()

    # 2. Get all subfolders (projects) in the 'videos' directory
    projects = [f for f in os.listdir(BASE_VIDEO_DIR) if os.path.isdir(os.path.join(BASE_VIDEO_DIR, f))]
    
    if not projects:
        print(f"ERROR: No subfolders found in '{BASE_VIDEO_DIR}'. Please add folders like 'Summer', 'Winter'.")
        exit()

    print(f"Found {len(projects)} projects: {projects}")

    # ==========================
    # LOOP THROUGH PROJECTS
    # ==========================
    for project_name in projects:
        
        # 3. Setup dynamic paths
        project_video_dir = os.path.join(BASE_VIDEO_DIR, project_name)
        project_result_dir = os.path.join(BASE_RESULT_DIR, project_name)
        project_temp_dir = os.path.join(BASE_TEMP_DIR, project_name)
        
        # 4. Setup Logging for this specific project
        setup_dynamic_logging(project_name)

        # 5. Create directories
        if not os.path.exists(project_result_dir): os.makedirs(project_result_dir)
        if not os.path.exists(project_temp_dir): os.makedirs(project_temp_dir)

        logging.info(f"==================================================")
        logging.info(f">>> STARTING PROJECT: {project_name}")
        logging.info(f"==================================================")

        # 6. Load Assets
        videos = get_video_files(project_video_dir)
        captions = get_captions(project_video_dir)

        if not videos:
            logging.error(f"SKIPPING {project_name}: No .mp4 files found.")
            continue
        if not captions:
            logging.error(f"SKIPPING {project_name}: captions.txt missing or empty.")
            continue

        logging.info(f"Loaded {len(videos)} videos and {len(captions)} caption lines.")

        with Timer(f"Total Time for Project: {project_name}"):
            
            # ==========================
            # LOOP THROUGH LANGUAGES
            # ==========================
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
                    # Save audio to temp/{project_name}/temp_{lang}.mp3
                    audio_filename = f"temp_{lang_code}.mp3"
                    audio_file_path = os.path.join(project_temp_dir, audio_filename)
                    
                    full_text = " ".join(trans_captions)
                    audio_success = False
                    
                    with Timer("Audio Generation (Edge-TTS)"):
                        audio_success = generate_audio_male_only(full_text, voice_name, audio_file_path)

                    # --- STEP 3: VIDEO ---
                    # Save video to result/{project_name}/Output_{lang}.mp4
                    output_video_path = os.path.join(project_result_dir, f"Output_{lang_name}.mp4")
                    
                    if audio_success:
                        with Timer("Video Processing Setup & Render"):
                            create_cinematic_video(videos, audio_file_path, trans_captions, output_video_path, lang_code)
                        
                        # Clean up specific audio
                        if os.path.exists(audio_file_path): os.remove(audio_file_path)
                        logging.info(f"  -> Saved to: {output_video_path}")
                    else:
                        logging.error("  [SKIP] Skipping video generation because audio failed.")
        
        logging.info(f"Completed Project: {project_name}\n")
    
    print("\nALL PROJECTS FINISHED!")