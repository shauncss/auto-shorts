import os
import json
import random
import subprocess
import requests

from google import genai 
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
import moviepy.video.fx.all as vfx 
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
import openai

# ==========================================
# 1. SETUP & CREDENTIALS
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
CUSTOM_IDEA = os.environ.get("CUSTOM_IDEA", "").strip()

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
if OPENAI_API_KEY:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ==========================================
# 2. THE BRAIN: GENERATE SCRIPT, THEMES & TAGS
# ==========================================
VIRAL_THEMES = [
    "creepy unsolved historical mysteries",
    "mind-blowing deep space anomalies",
    "scary deep ocean creatures and phenomena",
    "crazy survival stories against all odds",
    "secret historical cover-ups and glitches in reality"
]

def generate_content():
    print("🧠 Generating high-retention script with Gemini...")
    selected_theme = random.choice(VIRAL_THEMES) if not CUSTOM_IDEA else CUSTOM_IDEA
    topic_prompt = f"Write about this specific idea: {selected_theme}."

    prompt = f"""
    {topic_prompt}
    
    You MUST write a highly engaging 30-second YouTube Shorts script following this EXACT structure:
    1. Hook (0-3s): Start with a bold, controversial statement.
    2. Build-up (3-10s): Quickly explain the situation.
    3. Value / Twist (10-20s): Deliver something surprising.
    4. Payoff (20-25s): Show the result or conclusion.
    5. CTA (last 3s): Encourage engagement.

    Length: Exactly 70-80 words total.
    
    CRITICAL INSTRUCTION: Break this script down into exactly 10 to 12 fast-paced scenes to ensure the visuals change every 2 to 3 seconds.
    
    Format your response EXACTLY like this JSON:
    {{
        "title": "Catchy title",
        "description": "Short description #shorts",
        "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
        "scenes": [
            {{"text": "Hook text...", "search": "2-3 word visual description (e.g., 'exploding volcano')"}},
            {{"text": "Next text...", "search": "2-3 word visual description (e.g., 'dark forest')"}}
            // ... 10 to 12 scenes total
        ]
    }}
    """
    response = gemini_client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt
    )
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

# ==========================================
# 3. THE VISUALS: FETCH PEXELS VIDEOS
# ==========================================
def fetch_pexels_media(query, index):
    if not PEXELS_API_KEY: return None
        
    print(f"🎬 Fetching video for scene {index+1}: '{query}'")
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        r = requests.get(url, headers=headers)
        data = r.json()
        if data.get("videos"):
            # Grab the highest quality video link available
            video_files = data["videos"][0]["video_files"]
            hd_files = [v for v in video_files if v['quality'] == 'hd']
            file_url = hd_files[0]['link'] if hd_files else video_files[0]['link']
            
            video_data = requests.get(file_url).content
            filename = f"scene_{index}.mp4"
            with open(filename, "wb") as f:
                f.write(video_data)
            return filename
    except Exception as e:
        print(f"⚠️ Failed to fetch video for '{query}': {e}")
    return None

# ==========================================
# 4. OPENAI TTS & WHISPER TIMESTAMPS
# ==========================================
def generate_audio_and_subs(script_text):
    print("🎙️ Generating hyper-realistic voiceover with OpenAI Onyx...")
    
    # Generate the pristine audio
    response = openai_client.audio.speech.create(
        model="tts-1",
        voice="onyx", # Deep, gripping narrator voice
        input=script_text
    )
    response.stream_to_file("voice.mp3")
    
    print("📝 Generating perfect word-level timestamp data via Whisper...")
    # Map the exact millisecond each word is spoken
    with open("voice.mp3", "rb") as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )
    
    word_data = [{"word": w.word, "start": w.start, "end": w.end} for w in transcript.words]
    with open("subs.json", "w", encoding="utf-8") as f:
        json.dump(word_data, f)

# ==========================================
# 5. DYNAMIC CAPTION GENERATOR
# ==========================================
def get_dynamic_captions(json_file, video_w, video_h):
    with open(json_file, 'r', encoding='utf-8') as f:
        word_list = json.load(f)

    font_path = os.path.abspath('Roboto-Bold.ttf') 
    clips = []
    chunk_size = 2 # Show 2 words on screen at a time
    
    for i in range(0, len(word_list), chunk_size):
        chunk = word_list[i:i+chunk_size]
        c_start, c_end = chunk[0]["start"], chunk[-1]["end"]
        
        text = " ".join([w["word"] for w in chunk])
        clean_text = "".join([c for c in text if c.isalnum() or c in ".,!? "]).strip().upper()
        if not clean_text: continue
        
        try:
            txt_bg = TextClip(txt=clean_text, fontsize=95, color='black', font=font_path, stroke_color='black', stroke_width=12).set_pos('center')
            txt_fg = TextClip(txt=clean_text, fontsize=95, color='white', font=font_path).set_pos('center')
            
            combo_clip = CompositeVideoClip([txt_bg, txt_fg], size=txt_bg.size)
            combo_clip = combo_clip.set_pos('center').set_start(c_start).set_duration(c_end - c_start)
            clips.append(combo_clip)
        except Exception:
            pass
            
    print(f"✅ Generated {len(clips)} perfectly synced caption clips.")
    return clips

# ==========================================
# 6. THE EDITOR
# ==========================================
def edit_video(scenes):
    print("🎬 Assembling split-screen sequence...")
    W, H = 1080, 1920
    half_H = 960
    
    audio = AudioFileClip("voice.mp3")
    segment_duration = audio.duration / len(scenes)
    top_clips = []
    start_t = 0
    
    for i, scene in enumerate(scenes):
        vid_path = f"scene_{i}.mp4" if os.path.exists(f"scene_{i}.mp4") else None
        if vid_path:
            try:
                clip = VideoFileClip(vid_path, audio=False)
                scale = max(W / clip.w, half_H / clip.h)
                clip = clip.resize(scale).crop(x_center=clip.w/2, y_center=clip.h/2, width=W, height=half_H)
                
                # Loop or cut the clip to perfectly fit its timeframe
                if clip.duration > segment_duration:
                    clip = clip.subclip(0, segment_duration)
                else:
                    clip = clip.fx(vfx.loop, duration=segment_duration)
                    
                clip = clip.set_start(start_t).set_pos(("center", "top"))
                top_clips.append(clip)
            except Exception as e:
                print(f"⚠️ Video processing failed for {i}: {e}")
        start_t += segment_duration
        
    try:
        video = VideoFileClip("brainrot.mp4", audio=False)
        scale = max(W / video.w, half_H / video.h)
        video = video.resize(scale).crop(x_center=video.w/2, y_center=video.h/2, width=W, height=half_H)
        
        max_start = max(0, video.duration - audio.duration - 5)
        random_start = random.uniform(0, max_start)
        bottom_half = video.subclip(random_start, random_start + audio.duration)
    except Exception as e:
        bottom_half = ColorClip(size=(W, half_H), color=(20, 20, 20)).set_duration(audio.duration)

    bottom_half = bottom_half.set_start(0).set_pos(("center", "bottom"))
    bg_canvas = ColorClip(size=(W, H), color=(0,0,0)).set_duration(audio.duration)
    caption_clips = get_dynamic_captions("subs.json", W, H)
    
    final_video = CompositeVideoClip([bg_canvas] + top_clips + [bottom_half] + caption_clips)
    final_video = final_video.set_audio(audio)
    final_video.write_videofile("final_short.mp4", fps=30, preset="fast", threads=4, logger=None)
    
    final_video.close()
    audio.close()

# ==========================================
# 7. THE PUBLISHER
# ==========================================
def upload_to_youtube(title, description, tags):
    print(f"🚀 Uploading to YouTube with hyper-targeted tags: {tags}")
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
                "tags": tags # Using Gemini's generated tags
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
            fetch_pexels_media(scene["search"], i)
            
        full_script = " ".join([scene["text"] for scene in content["scenes"]])
        generate_audio_and_subs(full_script)
        edit_video(content["scenes"])
        upload_to_youtube(content["title"], content["description"], content.get("tags", ["shorts", "facts"]))
        
        try:
            os.remove("voice.mp3")
            os.remove("subs.json")
            os.remove("brainrot.mp4")
            for i in range(len(content["scenes"])):
                if os.path.exists(f"scene_{i}.mp4"): os.remove(f"scene_{i}.mp4")
        except PermissionError:
            pass
    except Exception as e:
        print(f"❌ An error occurred: {e}")