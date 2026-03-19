import os
import json
import random
import re
import subprocess
import requests
from google import genai 
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip, ColorClip, concatenate_videoclips
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
# 2. THE BRAIN: GENERATE SCRIPT & SCENES
# ==========================================
def generate_content():
    print("🧠 Generating highly engaging script with Gemini...")
    if CUSTOM_IDEA:
        topic_prompt = f"Write about this specific idea: {CUSTOM_IDEA}."
    else:
        topic_prompt = "Pick a random, highly fascinating historical or scientific fact."

    prompt = f"""
    {topic_prompt}
    
    You MUST write a highly engaging 30-second YouTube Shorts script following this EXACT structure:
    1. Hook (0-3s): Start with a bold, controversial, or curiosity-driven statement to grab attention.
    2. Build-up (3-10s): Quickly explain the situation using fast, simple words.
    3. Value / Twist (10-20s): Deliver something surprising, useful, or unexpected.
    4. Payoff (20-25s): Show the result, reveal, or conclusion.
    5. CTA (last 3s): Encourage engagement (e.g., comment, subscribe).

    Tone: Conversational, slightly dramatic, no fluff.
    Length: Exactly 70-80 words total.
    
    Format your response EXACTLY like this JSON:
    {{
        "title": "A catchy YouTube title",
        "description": "A short YouTube description with 3 hashtags",
        "scenes": [
            {{"text": "Hook text goes here...", "search": "One word to search for an image (e.g. 'fire')"}},
            {{"text": "Build-up text...", "search": "One search word (e.g. 'hacker')"}},
            {{"text": "Twist text...", "search": "One search word (e.g. 'money')"}},
            {{"text": "Payoff text...", "search": "One search word (e.g. 'explosion')"}},
            {{"text": "CTA text...", "search": "One search word (e.g. 'arrow')"}}
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
    except Exception as e:
        print(f"⚠️ Failed to fetch image for '{query}': {e}")
    return None

# ==========================================
# 4. THE VOICE & SUBTITLES (Upgraded Energy)
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
# 5. DYNAMIC CAPTION PARSER (Bulletproof)
# ==========================================
def get_dynamic_captions(vtt_file, video_w, video_h):
    with open(vtt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    def to_sec(t_str):
        h, m, s = t_str.split(':')
        s, ms = s.split('.')
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0

    clips = []
    content = content.replace('\r\n', '\n')
    blocks = content.strip().split('\n\n')
    
    matches = []
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 2 and '-->' in lines[0]:
            times = lines[0].split(' --> ')
            if len(times) == 2:
                start_t = to_sec(times[0].strip())
                end_t = to_sec(times[1].strip())
                text = " ".join(lines[1:]).strip()
                matches.append({"start": start_t, "end": end_t, "text": text})
    
    chunk_size = 2 
    for i in range(0, len(matches), chunk_size):
        chunk = matches[i:i+chunk_size]
        if not chunk: continue
        
        start_t = chunk[0]["start"]
        end_t = chunk[-1]["end"]
        text = " ".join([m["text"] for m in chunk])
        
        # Strip characters that crash ImageMagick
        clean_text = text.replace('"', '').replace("'", "").replace("\u2019", "").replace(";", "")
        
        txt_clip = TextClip(
            text=clean_text.upper(),
            font_size=95,
            color='white',
            font='DejaVu-Sans-Bold', 
            stroke_color='black',
            stroke_width=6,
            method='caption',
            size=(video_w - 150, None)
        ).with_position('center').with_start(start_t).with_duration(end_t - start_t)
        
        clips.append(txt_clip)
        
    print(f"✅ Generated {len(clips)} dynamic caption clips.")
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
    
    # --- TOP HALF: Contextual Images ---
    top_clips = []
    for i, scene in enumerate(scenes):
        img_path = f"scene_{i}.jpg" if os.path.exists(f"scene_{i}.jpg") else None
        
        if img_path:
            img_clip = ImageClip(img_path).with_duration(segment_duration)
            scale = max(W / img_clip.w, half_H / img_clip.h)
            img_clip = img_clip.resized(scale)
            img_clip = img_clip.cropped(x_center=img_clip.w/2, y_center=img_clip.h/2, width=W, height=half_H)
        else:
            img_clip = ColorClip(size=(W, half_H), color=(30, 30, 30)).with_duration(segment_duration)
            
        top_clips.append(img_clip)
        
    top_half = concatenate_videoclips(top_clips).with_position(("center", "top"))
    
    # --- BOTTOM HALF: Brainrot ---
    video = VideoFileClip("brainrot.mp4", audio=False)
    scale = max(W / video.w, half_H / video.h)
    video = video.resized(scale)
    video = video.cropped(x_center=video.w/2, y_center=video.h/2, width=W, height=half_H)
    
    safety_buffer = 15
    max_start_time = video.duration - audio.duration - safety_buffer
    
    if max_start_time > 0:
        random_start = random.uniform(0, max_start_time)
        bottom_half = video.subclipped(random_start, random_start + audio.duration)
    else:
        bottom_half = video.subclipped(0, video.duration)

    bottom_half = bottom_half.with_position(("center", "bottom"))
    
    # --- COMBINE & RENDER ---
    bg_canvas = ColorClip(size=(W, H), color=(0,0,0)).with_duration(audio.duration)
    bg_canvas = bg_canvas.with_audio(audio)
    
    caption_clips = get_dynamic_captions("subs.vtt", W, H)
    
    final_video = CompositeVideoClip([bg_canvas, top_half, bottom_half] + caption_clips)
    
    final_video.write_videofile(
        "final_short.mp4", 
        fps=30, 
        preset="ultrafast", 
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

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    try:
        content = generate_content()
        
        # 1. Fetch Images based on scenes
        for i, scene in enumerate(content["scenes"]):
            fetch_pexels_image(scene["search"], i)
            
        # 2. Combine scenes for voiceover
        full_script = " ".join([scene["text"] for scene in content["scenes"]])
        generate_audio_and_subs(full_script)
        
        # 3. Edit & Upload
        edit_video(content["scenes"])
        upload_to_youtube(content["title"], content["description"])
        
        # Cleanup
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