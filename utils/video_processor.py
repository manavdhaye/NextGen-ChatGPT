# utils/video_processor.py
import os
import speech_recognition as sr
from moviepy import VideoFileClip

def video_to_images(video_path, output_folder):
    """Extracts frames from a video at a specific FPS."""
    os.makedirs(output_folder, exist_ok=True)
    clip = VideoFileClip(video_path)
    
    # Save frames
    clip.write_images_sequence(
        os.path.join(output_folder, "frame%04d.png"), fps=0.02
    )
    clip.close()

def video_to_audio(video_path, output_audio_path):
    """Extracts the audio track from a video file."""
    os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
    clip = VideoFileClip(video_path)
    audio = clip.audio
    audio.write_audiofile(output_audio_path)
    audio.close()
    clip.close()

def audio_to_text(audio_path):
    """Uses Whisper to transcribe an audio file into text."""
    recognizer = sr.Recognizer()
    
    with sr.AudioFile(audio_path) as source:
        audio_data = recognizer.record(source)

        try:
            # Recognize the speech using Whisper
            text = recognizer.recognize_whisper(audio_data)
            return text
        except sr.UnknownValueError:
            print("Speech recognition could not understand the audio.")
            return ""
        except Exception as e:
            print(f"Error during transcription: {e}")
            return ""