import os
import json
import requests
import subprocess
from google import genai # <--- Updated Google Import
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips 
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# ==========================================
# 1. SETUP & CREDENTIALS
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# Initialize the new GenAI Client
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. THE BRAIN: GENERATE SCRIPT & METADATA
# ==========================================
def generate_content():
    print("🧠 Generating script with Gemini...")
    
    prompt = """
    Write a 30-word fascinating fact for a YouTube Short. 
    Format your response EXACTLY like this JSON:
    {
        "script": "The actual spoken text goes here.",
        "search_keyword": "A single word for background video, like 'ocean' or 'space'",
        "title": "A catchy YouTube title",
        "description": "A short YouTube description with 3 hashtags"
    }
    """
    # Using the new v1 API syntax with the Gemini 3 Flash model
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt
    )
    
    # Clean the response to ensure it's valid JSON
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

# ==========================================
# 3. THE VOICE: TEXT-TO-SPEECH
# ==========================================
def generate_audio(script_text):
    print("🎙️ Generating voiceover with Edge-TTS...")
    subprocess.run([
        "edge-tts", 
        "--voice", "en-US-ChristopherNeural", 
        "--text", script_text, 
        "--write-media", "voice.mp3"
    ])

# ==========================================
# 4. THE VISUALS: FETCH STOCK FOOTAGE
# ==========================================
def download_background(keyword):
    print(f"🎥 Fetching background video for: {keyword}...")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=1"
    
    response = requests.get(url, headers=headers).json()
    
    video_files = response['videos'][0]['video_files']
    hd_link = next(file['link'] for file in video_files if file['height'] >= 1920 or file['quality'] == 'hd')
    
    vid_data = requests.get(hd_link).content
    with open("background.mp4", "wb") as f:
        f.write(vid_data)

# ==========================================
# 5. THE EDITOR: ASSEMBLE VIDEO (MoviePy v2.0)
# ==========================================
def edit_video(script_text):
    print("🎬 Assembling the final video...")
    
    video = VideoFileClip("background.mp4")
    audio = AudioFileClip("voice.mp3")
    
    # --- NEW LOOPING LOGIC ---
    # If the background video is shorter than the voiceover, loop it!
    if video.duration < audio.duration:
        print("🔄 Video is shorter than audio. Looping the background...")
        # Calculate how many times we need to loop it to cover the audio length
        loops_needed = int(audio.duration // video.duration) + 1
        video = concatenate_videoclips([video] * loops_needed)
    # -------------------------
    
    # Now it is safe to subclip
    video = video.subclipped(0, audio.duration).with_audio(audio)
    
    txt_clip = TextClip(
        text=script_text, 
        font_size=60, 
        color='white', 
        font='Roboto-Bold.ttf',
        stroke_color='black',
        stroke_width=2,
        method='caption', 
        size=(video.w - 100, None)
    )
    
    txt_clip = txt_clip.with_position('center').with_duration(audio.duration)
    
    final_video = CompositeVideoClip([video, txt_clip])
    
    # Render the file
    final_video.write_videofile("final_short.mp4", fps=30, preset="ultrafast", logger=None)
    
    final_video.close()
    video.close()
    audio.close()

# ==========================================
# 6. THE PUBLISHER: UPLOAD TO YOUTUBE
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
                "title": title,
                "description": description,
                "tags": ["shorts", "facts", "automation"]
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
        generate_audio(content["script"])
        download_background(content["search_keyword"])
        edit_video(content["script"])
        upload_to_youtube(content["title"], content["description"])
        
        # Optional Step 6: Clean up temp files safely
        print("🧹 Cleaning up temporary files...")
        try:
            os.remove("voice.mp3")
            os.remove("background.mp4")
        except PermissionError:
            print("⚠️ Note: Windows kept a file lock on the temp files. They will just be overwritten next time!")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")