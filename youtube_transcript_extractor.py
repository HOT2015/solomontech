from youtube_transcript_api import YouTubeTranscriptApi

def get_transcript(video_url):
    try:
        video_id = video_url.split("v=")[1]
        # Handle URLs with additional parameters after video_id
        ampersand_position = video_id.find('&')
        if ampersand_position != -1:
            video_id = video_id[:ampersand_position]
            
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        transcript_text = ""
        for item in transcript_list:
            transcript_text += item['text'] + " "
        return transcript_text.strip()
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    youtube_url = input("Enter YouTube URL: ")
    transcript = get_transcript(youtube_url)
    print("\nTranscript:\n", transcript) 