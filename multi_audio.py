# !pip install -q kokoro>=0.9.2 soundfile moviepy deep-translator edge-tts
# !apt-get -qq -y install espeak-ng > /dev/null 2>&1

import os
import asyncio
import numpy as np
import torch
import soundfile as sf
import edge_tts 
from kokoro import KPipeline
from deep_translator import GoogleTranslator
from PIL import Image, ImageDraw, ImageFont
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips
)

# === CONFIGURATION ===
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
FONT_PATH = "content/THEBOLDFONT-FREEVERSION.ttf" 
OUTPUT_FOLDER = "multilingual_output"

# Ensure output folder exists
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# === LANGUAGES CONFIGURATION (For Audio Only) ===
# Format: "Language Name": ("Language Code", "EdgeTTS Voice Code")
LANGUAGES = {
    "Spanish":    ("es", "es-ES-AlvaroNeural"),
    "French":     ("fr", "fr-FR-HenriNeural"),
    "German":     ("de", "de-DE-ConradNeural"),
    "Portuguese": ("pt", "pt-BR-AntonioNeural"),
    "Italian":    ("it", "it-IT-DiegoNeural"),
    "Turkish":    ("tr", "tr-TR-AhmetNeural"),
    "Indonesian": ("id", "id-ID-ArdiNeural"),
    "Hindi":      ("hi", "hi-IN-MadhurNeural")
}

# ============================================================
#  PART 1: KOKORO AUDIO (For English Video)
# ============================================================
def generate_kokoro_audio(captions_list, output_filename="generated_audio.wav"):
    """
    Generates a single audio file from a list of captions using Kokoro TTS (Adam Voice).
    """
    print(f"--- [English] Generating Audio with Kokoro (Voice: Adam) ---")

    try:
        pipeline = KPipeline(lang_code='a') # 'a' for American English
    except Exception as e:
        print(f"Error initializing Kokoro: {e}")
        return None

    full_text = " ".join(captions_list)
    print("Synthesizing text...")

    generator = pipeline(full_text, voice='am_adam', speed=1, split_pattern=r'\n+')

    all_audio_pieces = []
    sample_rate = 24000

    for i, (gs, ps, audio) in enumerate(generator):
        all_audio_pieces.append(audio)

    if not all_audio_pieces:
        print("Error: No audio generated.")
        return None

    final_audio_data = np.concatenate(all_audio_pieces)
    sf.write(output_filename, final_audio_data, sample_rate)
    print(f"English Audio saved to: {output_filename}")

    return output_filename

# ============================================================
#  PART 2: MULTILINGUAL AUDIO (Edge TTS -> WAV)
# ============================================================
async def _generate_edge_audio_async(text, voice, output_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def generate_multilingual_wav(captions_list, lang_name, lang_code, voice_name):
    print(f"--- [{lang_name}] Processing ---")
    
    # 1. Translate Text
    full_text = " ".join(captions_list)
    try:
        translated_text = GoogleTranslator(source='auto', target=lang_code).translate(full_text)
        print(f"  Translation successful ({len(translated_text)} chars)")
    except Exception as e:
        print(f"  Translation failed: {e}")
        return

    # 2. Paths
    temp_mp3 = os.path.join(OUTPUT_FOLDER, f"temp_{lang_name}.mp3")
    final_wav = os.path.join(OUTPUT_FOLDER, f"Audio_{lang_name}.wav")

    # 3. Generate MP3 (Async wrapper)
    try:
        asyncio.run(_generate_edge_audio_async(translated_text, voice_name, temp_mp3))
    except Exception as e:
        print(f"  TTS Generation failed: {e}")
        return

    # 4. Convert MP3 to WAV using MoviePy
    try:
        if os.path.exists(temp_mp3):
            clip = AudioFileClip(temp_mp3)
            clip.write_audiofile(
                final_wav, 
                fps=24000, 
                nbytes=2, 
                codec='pcm_s16le', 
                verbose=False, 
                logger=None
            )
            clip.close()
            os.remove(temp_mp3) # Cleanup temp file
            print(f"  -> Saved: {final_wav}")
    except Exception as e:
        print(f"  Conversion to WAV failed: {e}")

# ============================================================
#  PART 3: VIDEO GENERATION (English Only)
# ============================================================
def create_pil_text_image(text, video_w, video_h):
    img = Image.new('RGBA', (video_w, video_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    target_font_size = int(video_w * 0.13)
    try:
        font = ImageFont.truetype(FONT_PATH, target_font_size)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x_pos = (video_w - text_w) // 2
    y_pos = (video_h - text_h) // 2

    offsets = [(-4, -4), (-4, 4), (4, -4), (4, 4), (0, 5), (0, -5), (5, 0), (-5, 0)]
    for ox, oy in offsets:
        draw.text((x_pos + ox, y_pos + oy), text, font=font, fill="black")

    draw.text((x_pos, y_pos), text, font=font, fill="#FFD700") 
    return np.array(img)

def create_cinematic_video(video_paths, audio_path, captions_list, output_path='final_output.mp4'):
    print(f"--- Starting Video Composition ---")
    processed_clips = []

    for path in video_paths:
        try:
            clip = VideoFileClip(path)
            ratio_w = TARGET_WIDTH / clip.w
            ratio_h = TARGET_HEIGHT / clip.h
            scale_factor = max(ratio_w, ratio_h)
            clip = clip.resize(scale_factor * 1.05)
            clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=TARGET_WIDTH, height=TARGET_HEIGHT)
            clip = clip.resize(lambda t: 1 + 0.03 * t)
            processed_clips.append(clip)
        except Exception as e:
            print(f"Skipping {path}: {e}")

    if not processed_clips:
        print("No videos loaded!")
        return

    final_bg = concatenate_videoclips(processed_clips, method="compose")
    final_bg = final_bg.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))

    try:
        audio = AudioFileClip(audio_path)
        if audio.duration > final_bg.duration:
            n_loops = int(audio.duration / final_bg.duration) + 1
            final_bg = final_bg.loop(n=n_loops)

        final_bg = final_bg.set_audio(audio)
        final_bg = final_bg.subclip(0, audio.duration)
    except Exception as e:
        print(f"Audio sync failed: {e}")
        return

    text_clips = []
    total_duration = final_bg.duration

    if len(captions_list) > 0:
        duration_per_sentence = total_duration / len(captions_list)
        current_time = 0.0

        for sentence in captions_list:
            words = sentence.split()
            if not words: continue
            duration_per_word = duration_per_sentence / len(words)
            for word in words:
                img_arr = create_pil_text_image(word.upper(), TARGET_WIDTH, TARGET_HEIGHT)
                txt = (ImageClip(img_arr)
                       .set_start(current_time)
                       .set_duration(duration_per_word)
                       .set_position('center')
                       .resize(lambda t: 0.9 + 0.3 * t))
                text_clips.append(txt)
                current_time += duration_per_word

    print("Rendering Video...")
    final_video = CompositeVideoClip([final_bg] + text_clips, size=(TARGET_WIDTH, TARGET_HEIGHT))
    
    final_video.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        preset="medium",
        ffmpeg_params=["-vf", "scale=1080:1920", "-aspect", "9:16"],
        logger='bar'
    )
    final_video.close()
    for c in processed_clips: c.close()
    print("Video Done!")

# ================= USAGE =================

videos = [
    "videos/winter1.mp4",
    "videos/winter2.mp4",
    "videos/winter3.mp4",
    "videos/winter4.mp4",
    "videos/winter5.mp4",
    "videos/winter6.mp4",
]

captions = [
"Oranges deliver powerful winter nourishment with vitamin C and essential nutrients.",
"Their natural antioxidants help strengthen cellular defense during cold weather.",
"Oranges support immune balance and skin health with abundant vitamin C.",
"The digestive system breaks down their fiber and natural sugars for clean, steady energy.",
"Citrus compounds promote collagen formation and overall tissue support.",
"A simple daily orange can be a refreshing, immunity-boosting winter habit."
]

if __name__ == "__main__":
    if not os.path.exists(FONT_PATH):
        print("WARNING: Font not found. Ensure path is correct.")

    print("\n========== STEP 1: ENGLISH VIDEO GENERATION ==========")
    
    # 1. Generate Kokoro Audio (English)
    english_audio_path = os.path.join(OUTPUT_FOLDER, "english_kokoro.wav")
    audio_result = generate_kokoro_audio(captions, english_audio_path)

    # 2. Make English Video
    if audio_result and os.path.exists(audio_result):
        if os.path.exists(videos[0]):
            create_cinematic_video(videos, audio_result, captions, os.path.join(OUTPUT_FOLDER, "Youtube_Short_English.mp4"))
        else:
            print("Video source files not found.")
    else:
        print("English Audio generation failed.")

    print("\n========== STEP 2: MULTILINGUAL AUDIO GENERATION ==========")
    
    # 3. Loop through languages and generate audio
    for lang_name, (lang_code, voice_name) in LANGUAGES.items():
        generate_multilingual_wav(captions, lang_name, lang_code, voice_name)

    print("\n========== ALL PROCESSES COMPLETED ==========")