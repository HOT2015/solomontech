from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

def get_youtube_script(url: str) -> str:
    """
    유튜브 URL에서 스크립트를 추출합니다.

    Args:
        url: 유튜브 비디오 URL.

    Returns:
        추출된 스크립트 텍스트 또는 오류 메시지.
    """
    try:
        video_id = url.split("v=")[1]
        # "&" 뒤에 오는 추가 파라미터 제거
        ampersand_position = video_id.find("&")
        if ampersand_position != -1:
            video_id = video_id[:ampersand_position]

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # 한국어 스크립트 찾기, 없으면 영어, 없으면 사용 가능한 첫 번째 스크립트
        target_language_codes = ['ko', 'en']
        transcript = None\

        for lang_code in target_language_codes:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang_code])
                break
            except:
                try:
                    transcript = transcript_list.find_generated_transcript([lang_code])
                    break
                except:
                    continue
        
        if not transcript: # 한국어 또는 영어 스크립트가 없는 경우
            available_transcripts = transcript_list._transcripts
            if not available_transcripts:
                return "스크립트를 찾을 수 없습니다. 해당 영상에 스크립트가 없거나 지원하지 않는 형식일 수 있습니다."
            # 첫번째로 찾은 언어의 스크립트를 사용
            first_lang_code = list(available_transcripts.keys())[0]
            try:
                transcript = transcript_list.find_manually_created_transcript([first_lang_code])
            except:
                transcript = transcript_list.find_generated_transcript([first_lang_code])


        fetched_transcript = transcript.fetch()
        formatter = TextFormatter()
        text_transcript = formatter.format_transcript(fetched_transcript)
        return text_transcript

    except Exception as e:
        if "NoSuitableTranscriptsFound" in str(e):
            return "스크립트를 찾을 수 없습니다. 해당 영상에 스크립트가 없거나 지원하지 않는 형식일 수 있습니다."
        elif "TooManyRequests" in str(e) or "TranscriptsDisabled" in str(e):
             return f"스크립트를 가져오는 중 오류가 발생했습니다: {e}. 나중에 다시 시도해주세요."
        elif "InvalidURL" in str(e) or "YouTubeRequestFailed" in str(e) or "VideoUnavailable" in str(e):
            return "잘못된 유튜브 URL이거나 영상을 찾을 수 없습니다. URL을 확인해주세요."
        else:
            return f"알 수 없는 오류가 발생했습니다: {e}"

if __name__ == "__main__":
    youtube_url = input("유튜브 URL을 입력하세요: ")
    script = get_youtube_script(youtube_url)
    print("\n--- 스크립트 ---")
    print(script)
    print("---------------") 