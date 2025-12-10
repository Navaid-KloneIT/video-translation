import pysrt
from deep_translator import GoogleTranslator
import time
import os

# Configuration
INPUT_FOLDER = "translate_input"
OUTPUT_FOLDER = "translate_output"
INPUT_FILENAME = "English.srt"

# Full path to the input file
INPUT_PATH = os.path.join(INPUT_FOLDER, INPUT_FILENAME)

# Mapping language names to ISO-639-1 codes
TARGET_LANGUAGES = {
    "Spanish": "es",
    "French": "fr",
    "Arabic": "ar",
    "Russian": "ru",
    "Portuguese": "pt",
    "Indonesian": "id",
    "German": "de",
    "Japanese": "ja",
    "Turkish": "tr",
    "Vietnamese": "vi",
    "Hindi": "hi",
    "Urdu": "ur",
    "Italian": "it"  # Added Italian
}

def translate_srt():
    # 1. Check if input file exists
    if not os.path.exists(INPUT_PATH):
        print(f"Error: '{INPUT_FILENAME}' not found in '{INPUT_FOLDER}' folder.")
        print(f"Please create the folder '{INPUT_FOLDER}' and place the file inside it.")
        return

    # 2. Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Created output directory: {OUTPUT_FOLDER}")

    print(f"Loading source file: {INPUT_PATH}...")
    
    # Iterate through each target language
    for lang_name, lang_code in TARGET_LANGUAGES.items():
        print(f"------------------------------------------------")
        print(f"Translating to {lang_name} ({lang_code})...")
        
        try:
            # Reload the original file for every language to ensure we start fresh
            subs = pysrt.open(INPUT_PATH, encoding='utf-8')
            
            # Initialize translator for specific language
            translator = GoogleTranslator(source='auto', target=lang_code)
            
            # Iterate through each subtitle line
            for index, sub in enumerate(subs):
                original_text = sub.text
                
                # Skip empty lines
                if not original_text.strip():
                    continue

                try:
                    # Translate the text
                    translated_text = translator.translate(original_text)
                    sub.text = translated_text

                except Exception as e:
                    print(f"Error translating line {index+1}: {e}")
                
                # Small sleep to avoid hitting API rate limits
                time.sleep(0.1) 

            # Construct output path
            output_filename = f"{lang_name}.srt"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            # Save the new file
            subs.save(output_path, encoding='utf-8')
            print(f"Saved: {output_path}")

        except Exception as e:
            print(f"Failed to process language {lang_name}: {e}")

    print("------------------------------------------------")
    print(f"All translations completed. Check the '{OUTPUT_FOLDER}' folder.")

if __name__ == "__main__":
    translate_srt()