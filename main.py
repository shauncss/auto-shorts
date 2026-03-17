import os
import json
import random
import re
import subprocess
from google import genai 
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# ==========================================
# 1. SETUP & CREDENTIALS
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
CUSTOM_IDEA = os.environ.get("CUSTOM_IDEA", "").strip()

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. THE BRAIN: GENERATE SCRIPT
# ==========================================
def generate_content():
    print("🧠 Generating script with Gemini...")
    
    # Check if you manually typed an idea in GitHub
    if CUSTOM_IDEA:
        topic_prompt = f"Write about this specific idea: {CUSTOM_IDEA}."
    else:
        topic_prompt = "Pick a random, highly fascinating historical or scientific fact."

    prompt = f"""
    {topic_prompt}
    The script MUST be exactly 70 to 80 words long so it takes about 30 seconds to speak.
    Format your response EXACTLY like this JSON:
    {{
        "script": "The actual spoken text goes here.",
        "title": "A catchy YouTube title",
        "description": "A short YouTube description with 3 hashtags"
    }}
    """
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt
    )
    
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

# ==========================================
# 3. THE VOICE & SUBTITLES
# ==========================================
def generate_audio_and_subs(script_text):
    print("🎙️ Generating voiceover and sync data...")
    # This now generates an MP3 AND a WebVTT subtitle file
    subprocess.run([
        "edge-tts", 
        "--voice", "en-US-ChristopherNeural", 
        "--text", script_text, 
        "--write-media", "voice.mp3",
        "--write-subtitles", "subs.vtt"
    ])

# ==========================================
# 4. THE VISUALS: BRAINROT GAMEPLAY
# ==========================================
def download_background():
    print("🎮 Fetching brainrot gameplay background...")
    
    # Add as many long, no-copyright gameplay URLs here as you want!
    gameplay_videos = [
        "https://www.youtube.com/watch?v=n_Dv4JMmAWA", # Minecraft Parkour 1
        "https://www.youtube.com/watch?v=ANOTHER_ID",  # GTA V Mega Ramp Cars
        "https://www.youtube.com/watch?v=ANOTHER_ID",  # Subway Surfers Gameplay
        "https://www.youtube.com/watch?v=ANOTHER_ID",  # Satisfying Kinetic Sand
        "https://www.youtube.com/watch?v=ANOTHER_ID"   # Trackmania Racing
    ]
    
    # The script randomly picks ONE of these links every time it runs
    video_url = random.choice(gameplay_videos)
    
    # It then picks a random 45-second chunk from somewhere in the middle
    start_time = random.randint(60, 1200)
    end_time = start_time + 45

    subprocess.run([
        "yt-dlp", 
        "-f", "bestvideo[ext=mp4]", 
        "--download-sections", f"*{start_time}-{end_time}", 
        video_url, 
        "-o", "background.mp4"
    ])

# ==========================================
# 5. DYNAMIC CAPTION PARSER
# ==========================================
def get_dynamic_captions(vtt_file, video_w):
    with open(vtt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract timestamps and text words
    pattern = re.compile(r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\n(.*?)\n", re.DOTALL)
    matches = pattern.findall(content)
    
    def to_sec(t_str):
        h, m, s = t_str.split(':')
        s, ms = s.split('.')
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0

    clips = []
    chunk_size = 4 # Shows 4 words at a time
    
    for i in range(0, len(matches), chunk_size):
        chunk = matches[i:i+chunk_size]
        if not chunk: continue
        
        start_t = to_sec(chunk[0][0])
        end_t = to_sec(chunk[-1][1])
        text = " ".join([m[2].strip() for m in chunk])
        
        txt_clip = TextClip(
            text=text,
            font_size=80, # Huge, readable font
            color='white',
            font='Roboto-Bold.ttf',
            stroke_color='black',
            stroke_width=4,
            method='caption',
            size=(video_w - 200, None) # Safe zone to prevent border clipping
        ).with_position('center').with_start(start_t).with_duration(end_t - start_t)
        
        clips.append(txt_clip)
    return clips

# ==========================================
# 6. THE EDITOR: ASSEMBLE
# ==========================================
def edit_video():
    print("🎬 Assembling the final video...")
    
    video = VideoFileClip("background.mp4")
    audio = AudioFileClip("voice.mp3")
    
    # Crop the widescreen gameplay to 9:16 vertical
    target_w = video.h * (9/16)
    x_center = video.w / 2
    video = video.cropped(
        x1=x_center - target_w/2, 
        y1=0, 
        x2=x_center + target_w/2, 
        y2=video.h
    )
    
    # Loop if necessary, then trim to audio length
    if video.duration < audio.duration:
        from moviepy import concatenate_videoclips
        loops = int(audio.duration // video.duration) + 1
        video = concatenate_videoclips([video] * loops)
        
    video = video.subclipped(0, audio.duration).with_audio(audio)
    
    # Add the dynamic pop-up captions
    caption_clips = get_dynamic_captions("subs.vtt", video.w)
    
    final_video = CompositeVideoClip([video] + caption_clips)
    final_video.write_videofile("final_short.mp4", fps=30, preset="ultrafast", logger=None)
    
    final_video.close()
    video.close()
    audio.close()

# ==========================================
# 7. THE PUBLISHER
# ==========================================
def upload_to_youtube(title, description):
    print("🚀 Uploading to YouTube...")
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    credentials = Credentials.from_authorized_user_file("token.json", SCOPES)
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "categoryId": "22",
                "title": title[:100], 
                "description": description,
                "tags": ["shorts", "facts"]
            },
            "status": {
                "privacyStatus": "private", 
                "selfDeclaredMadeForKids": False
            }
        },
        media_body=MediaFileUpload("final_short.mp4")
    )
    
    response = request.execute()
    print(f"✅ Success! Video ID: {response['id']}")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    try:
        content = generate_content()
        generate_audio_and_subs(content["script"])
        download_background()
        edit_video()
        upload_to_youtube(content["title"], content["description"])
        
        try:
            os.remove("voice.mp3")
            os.remove("subs.vtt")
            os.remove("background.mp4")
        except PermissionError:
            pass
            
    except Exception as e:
        print(f"❌ An error occurred: {e}")