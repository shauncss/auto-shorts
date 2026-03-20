import os
import json
import random
import subprocess
import requests

# === THE MOVIEPY/PILLOW PATCH ===
# This tricks MoviePy 1.0.3 into working with modern Pillow!
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS
# ================================

from google import genai 
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip, ColorClip, concatenate_videoclips
import moviepy.video.fx.all as vfx 
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# ==========================================
# 1. SETUP & CREDENTIALS
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
CUSTOM_IDEA = os.environ.get("CUSTOM_IDEA", "").strip()

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. THE BRAIN: GENERATE SCRIPT & THEMES
# ==========================================
VIRAL_THEMES = [
    "creepy unsolved historical mysteries",
    "mind-blowing deep space anomalies",
    "bizarre psychological experiments",
    "scary deep ocean creatures and phenomena",
    "crazy survival stories against all odds",
    "secret historical cover-ups and glitches in reality",
    "fascinating ancient technologies that shouldn't exist"
]

def generate_content():
    print("🧠 Generating highly engaging script with Gemini...")
    
    if CUSTOM_IDEA:
        topic_prompt = f"Write about this specific idea: {CUSTOM_IDEA}."
    else:
        selected_theme = random.choice(VIRAL_THEMES)
        print(f"🎯 Selected Theme for this video: {selected_theme.upper()}")
        topic_prompt = f"Pick a highly fascinating, true fact related to: {selected_theme}."

    prompt = f"""
    {topic_prompt}
    
    You MUST write a highly engaging 30-second YouTube Shorts script following this EXACT structure:
    1. Hook (0-3s): Start with a bold, controversial, or curiosity-driven statement.
    2. Build-up (3-10s): Quickly explain the situation.
    3. Value / Twist (10-20s): Deliver something surprising.
    4. Payoff (20-25s): Show the result or conclusion.
    5. CTA (last 3s): Encourage engagement.

    Length: Exactly 70-80 words total.
    
    Format your response EXACTLY like this JSON:
    {{
        "title": "Catchy title",
        "description": "Short description #shorts",
        "scenes": [
            {{"text": "Hook text...", "search": "2-3 word LITERAL visual description (e.g., 'man running fast')"}},
            {{"text": "Build-up text...", "search": "2-3 word LITERAL visual description (e.g., 'hacker typing dark')"}},
            {{"text": "Twist text...", "search": "2-3 word LITERAL visual description (e.g., 'ancient roman sword')"}},
            {{"text": "Payoff text...", "search": "2-3 word LITERAL visual description (e.g., 'scientist laboratory')"}},
            {{"text": "CTA text...", "search": "2-3 word LITERAL visual description (e.g., 'finger pointing screen')"}}
        ]
    }}
    """
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt
    )
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

# ==========================================
# 3. THE VISUALS: FETCH PEXELS IMAGES
# ==========================================
def fetch_pexels_image(query, index):
    if not PEXELS_API_KEY:
        print("⚠️ No Pexels API Key found! Skipping image fetch.")
        return None
        
    print(f"🖼️ Fetching image for scene {index+1}: '{query}'")
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1&orientation=portrait"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        r = requests.get(url, headers=headers)
        data = r.json()
        if data.get("photos"):
            img_url = data["photos"][0]["src"]["large2x"]
            img_data = requests.get(img_url).content
            filename = f"scene_{index}.jpg"
            with open(filename, "wb") as f:
                f.write(img_data)
            return filename
        else:
            print(f"⚠️ No Pexels results found for '{query}'.")
    except Exception as e:
        print(f"⚠️ Failed to fetch image for '{query}': {e}")
    return None

# ==========================================
# 4. THE VOICE & SUBTITLES
# ==========================================
def generate_audio_and_subs(script_text):
    print("🎙️ Generating energetic voiceover and sync data...")
    subprocess.run([
        "edge-tts", 
        "--voice", "en-US-AndrewNeural", 
        "--rate", "+10%", 
        "--text", script_text, 
        "--write-media", "voice.mp3",
        "--write-subtitles", "subs.vtt"
    ])

# ==========================================
# 5. DYNAMIC CAPTION PARSER (2-Word Chunks)
# ==========================================
def get_dynamic_captions(vtt_file, video_w, video_h):
    with open(vtt_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    raw_matches = []
    start_t = None
    end_t = None
    text_buffer = []
    
    for line in lines:
        line = line.strip()
        if '-->' in line:
            if start_t and end_t and text_buffer:
                raw_matches.append({"start": start_t, "end": end_t, "text": " ".join(text_buffer)})
            parts = line.split('-->')
            start_t = parts[0].strip()
            end_t = parts[1].strip()
            text_buffer = []
        elif line and not line.isdigit() and line != "WEBVTT":
            text_buffer.append(line)
            
    if start_t and end_t and text_buffer:
        raw_matches.append({"start": start_t, "end": end_t, "text": " ".join(text_buffer)})

    def to_sec(t_str):
        try:
            t_str = t_str.replace(',', '.')
            parts = t_str.split(':')
            if len(parts) == 3:
                h, m, s = parts
            elif len(parts) == 2:
                h, m, s = 0, parts[0], parts[1]
            else:
                h, m, s = 0, 0, parts[0]
                
            if '.' in s:
                s, ms = s.split('.')
            else:
                ms = 0
            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
        except Exception:
            return 0.0

    font_path = os.path.abspath('Roboto-Bold.ttf') 
    
    word_list = []
    for match in raw_matches:
        c_start = to_sec(match["start"])
        c_end = to_sec(match["end"])
        
        if c_end <= c_start:
            c_end = c_start + 0.5 
            
        words = match["text"].split()
        if not words: continue
        
        word_duration = (c_end - c_start) / len(words)
        
        for idx, word in enumerate(words):
            w_start = c_start + (idx * word_duration)
            w_end = w_start + word_duration
            word_list.append({"word": word, "start": w_start, "end": w_end})

    clips = []
    chunk_size = 2 
    
    for i in range(0, len(word_list), chunk_size):
        chunk = word_list[i:i+chunk_size]
        
        c_start = chunk[0]["start"]
        c_end = chunk[-1]["end"]
        
        text = " ".join([w["word"] for w in chunk])
        clean_text = "".join([c for c in text if c.isalnum() or c in ".,!? "]).strip()
        
        if not clean_text: continue
        
        try:
            # FIX: Switched back to 'fontsize' for 1.0.3 and added 'method=caption' 
            # to safely bound the stroke from getting cut off.
            txt_clip = TextClip(
                txt=clean_text.upper(), 
                fontsize=95,
                color='white',
                font=font_path, 
                stroke_color='black',
                stroke_width=5,
                method='caption',
                align='center',
                size=(video_w - 100, None)
            ).set_pos('center').set_start(c_start).set_duration(c_end - c_start)
            
            clips.append(txt_clip)
        except Exception as e:
            print(f"⚠️ Failed to render caption block '{clean_text}': {e}")
            
    print(f"✅ Generated {len(clips)} fast-paced 2-word caption clips.")
    return clips

# ==========================================
# 6. THE EDITOR: SPLIT SCREEN ASSEMBLE
# ==========================================
def edit_video(scenes):
    print("🎬 Assembling Split-Screen Video...")
    
    W, H = 1080, 1920
    half_H = 960
    
    audio = AudioFileClip("voice.mp3")
    segment_duration = audio.duration / len(scenes)
    
    top_clips = []
    for i, scene in enumerate(scenes):
        img_path = f"scene_{i}.jpg" if os.path.exists(f"scene_{i}.jpg") else None
        if img_path:
            img_clip = ImageClip(img_path).set_duration(segment_duration)
            scale = max(W / img_clip.w, half_H / img_clip.h)
            img_clip = img_clip.resize(scale)
            img_clip = img_clip.crop(x_center=img_clip.w/2, y_center=img_clip.h/2, width=W, height=half_H)
        else:
            img_clip = ColorClip(size=(W, half_H), color=(30, 30, 30)).set_duration(segment_duration)
        top_clips.append(img_clip)
        
    top_half = concatenate_videoclips(top_clips).set_pos(("center", "top"))
    
    video = VideoFileClip("brainrot.mp4", audio=False)
    scale = max(W / video.w, half_H / video.h)
    video = video.resize(scale)
    video = video.crop(x_center=video.w/2, y_center=video.h/2, width=W, height=half_H)
    
    safety_buffer = 15
    max_start_time = video.duration - audio.duration - safety_buffer
    
    if max_start_time > 0:
        random_start = random.uniform(0, max_start_time)
        bottom_half = video.subclip(random_start, random_start + audio.duration)
    else:
        bottom_half = video.subclip(0, video.duration)
        bottom_half = bottom_half.fx(vfx.loop, duration=audio.duration)

    bottom_half = bottom_half.set_pos(("center", "bottom"))
    
    bg_canvas = ColorClip(size=(W, H), color=(0,0,0)).set_duration(audio.duration)
    bg_canvas = bg_canvas.set_audio(audio)
    
    caption_clips = get_dynamic_captions("subs.vtt", W, H)
    
    final_video = CompositeVideoClip([bg_canvas, top_half, bottom_half] + caption_clips)
    
    final_video.write_videofile(
        "final_short.mp4", 
        fps=30, 
        preset="fast", 
        threads=4,
        logger=None
    )
    
    final_video.close()
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
                "tags": ["shorts", "facts", "story"]
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

if __name__ == "__main__":
    try:
        content = generate_content()
        for i, scene in enumerate(content["scenes"]):
            fetch_pexels_image(scene["search"], i)
            
        full_script = " ".join([scene["text"] for scene in content["scenes"]])
        generate_audio_and_subs(full_script)
        
        edit_video(content["scenes"])
        upload_to_youtube(content["title"], content["description"])
        
        try:
            os.remove("voice.mp3")
            os.remove("subs.vtt")
            os.remove("brainrot.mp4")
            for i in range(len(content["scenes"])):
                if os.path.exists(f"scene_{i}.jpg"):
                    os.remove(f"scene_{i}.jpg")
        except PermissionError:
            pass
    except Exception as e:
        print(f"❌ An error occurred: {e}")