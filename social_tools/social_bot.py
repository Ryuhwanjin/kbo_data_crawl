import os
import requests
import tweepy
from dotenv import load_dotenv
from image_hoster import upload_to_imgur

class KBOSocialBot:
    def __init__(self):
        load_dotenv()
        self.imgur_client_id = os.getenv("IMGUR_CLIENT_ID")
        
        # Threads Credentials
        self.threads_user_id = os.getenv("THREADS_USER_ID")
        self.threads_token = os.getenv("THREADS_ACCESS_TOKEN")
        
        # X (Twitter) Credentials
        self.x_consumer_key = os.getenv("X_CONSUMER_KEY")
        self.x_consumer_secret = os.getenv("X_CONSUMER_SECRET")
        self.x_access_token = os.getenv("X_ACCESS_TOKEN")
        self.x_access_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        self.x_bearer_token = os.getenv("X_BEARER_TOKEN")
        
        # Tweepy Client (API v2 for Text, API v1.1 for Media Upload)
        try:
            auth = tweepy.OAuth1UserHandler(
                self.x_consumer_key, self.x_consumer_secret,
                self.x_access_token, self.x_access_secret
            )
            self.x_api_v1 = tweepy.API(auth)
            
            self.x_client = tweepy.Client(
                bearer_token=self.x_bearer_token,
                consumer_key=self.x_consumer_key,
                consumer_secret=self.x_consumer_secret,
                access_token=self.x_access_token,
                access_token_secret=self.x_access_secret
            )
        except Exception as e:
            print(f"X API 초기화 경고 (키 누락일 수 있음): {e}")

    def post_to_x(self, text, image_path):
        """X(Twitter)에 미디어와 함께 포스팅합니다."""
        print("[X] 트위터 포스팅 시작...")
        if not all([self.x_consumer_key, self.x_access_token]):
            print("[X] API 키가 누락되어 트위터 포스팅을 건너뜁니다.")
            return False
            
        try:
            # 1. 미디어 업로드 (v1.1 API 사용 필요)
            media = self.x_api_v1.media_upload(filename=image_path)
            media_id = media.media_id
            
            # 2. 트윗 작성 (v2 API)
            response = self.x_client.create_tweet(text=text, media_ids=[media_id])
            print(f"[X] 트윗 게시 성공! ID: {response.data['id']}")
            return True
        except Exception as e:
            print(f"[X] 트위터 포스팅 에러: {e}")
            return False

    def post_to_threads(self, text, image_path):
        """Threads에 퍼블릭 URL 우회 방식을 사용하여 포스팅합니다 (2-Step Publish)."""
        print("[Threads] 스레드 포스팅 시작...")
        if not all([self.threads_user_id, self.threads_token, self.imgur_client_id]):
            print("[Threads] API 키 또는 Imgur Client ID가 누락되어 스레드 포스팅을 건너뜁니다.")
            return False
            
        try:
            # Step 0: 로컬 이미지를 Imgur에 올려 Public URL 획득
            print("[Threads] Imgur에 이미지 임시 호스팅 중...")
            public_image_url = upload_to_imgur(image_path, self.imgur_client_id)
            print(f"[Threads] Public URL 획득: {public_image_url}")
            
            base_url = f"https://graph.threads.net/v1.0/{self.threads_user_id}"
            
            # Step 1: 미디어 컨테이너 생성
            print("[Threads] 미디어 컨테이너 생성 중...")
            container_payload = {
                "media_type": "IMAGE",
                "image_url": public_image_url,
                "text": text,
                "access_token": self.threads_token
            }
            res_container = requests.post(f"{base_url}/threads", data=container_payload)
            res_container.raise_for_status()
            creation_id = res_container.json().get("id")
            
            # Step 2: 컨테이너 발행(Publish)
            print(f"[Threads] 컨테이너({creation_id}) 발행 중...")
            publish_payload = {
                "creation_id": creation_id,
                "access_token": self.threads_token
            }
            res_publish = requests.post(f"{base_url}/threads_publish", data=publish_payload)
            res_publish.raise_for_status()
            
            print(f"[Threads] 스레드 게시 성공! ID: {res_publish.json().get('id')}")
            return True
        except Exception as e:
            print(f"[Threads] 스레드 포스팅 에러: {e}")
            return False

    def broadcast(self, text, image_path):
        """설정된 모든 소셜 미디어 플랫폼에 동시 송출합니다."""
        print("=" * 50)
        print("📡 KBO Social Bot 브로드캐스트 가동")
        print("=" * 50)
        self.post_to_x(text, image_path)
        self.post_to_threads(text, image_path)
        print("=" * 50)
        print("✅ 브로드캐스트 완료")

if __name__ == "__main__":
    # Test execution
    # bot = KBOSocialBot()
    # bot.broadcast("오늘의 KBO 투수 데이터 분석 결과입니다! ⚾️🔥 #KBO #야구데이터", "sample_chart.png")
    pass
