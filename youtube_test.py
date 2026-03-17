import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# The specific permission we are requesting (Upload access)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def authenticate_youtube():
    credentials = None
    
    # Check if we already have a token
    if os.path.exists("token.json"):
        credentials = Credentials.from_authorized_user_file("token.json", SCOPES)
        
    # If no valid credentials, force the user to log in
    if not credentials or not credentials.valid:
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            "client_secrets.json", SCOPES
        )
        # This opens the web browser
        credentials = flow.run_local_server(port=0)
        
        # Save the credentials for the next run (and for GitHub Actions later)
        with open("token.json", "w") as token:
            token.write(credentials.to_json())
            
    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

def upload_video(youtube):
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "categoryId": "22", # Category 22 is "People & Blogs"
                "description": "Testing my automated Python pipeline.",
                "title": "First Automated Test Upload"
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False
            }
        },
        media_body=MediaFileUpload("test_video.mp4")
    )
    
    print("Uploading video... This might take a minute.")
    response = request.execute()
    print(f"Success! Video ID: {response['id']}")

if __name__ == "__main__":
    # 1. Authenticate and get the token
    youtube_client = authenticate_youtube()
    
    # 2. Upload the test video
    upload_video(youtube_client)