import requests
import base64
import os

def upload_to_imgur(image_path, client_id):
    """
    로컬 이미지를 Imgur API에 업로드하고 Public URL을 반환합니다.
    Threads API는 Public URL 형태의 이미지만 지원하므로 이 우회 과정이 필수적입니다.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    url = "https://api.imgur.com/3/image"
    headers = {
        "Authorization": f"Client-ID {client_id}"
    }

    with open(image_path, "rb") as file:
        image_data = file.read()
        b64_image = base64.b64encode(image_data).decode("utf-8")

    payload = {
        "image": b64_image,
        "type": "base64",
        "name": os.path.basename(image_path),
        "title": "KBO Daily Chart"
    }

    response = requests.post(url, headers=headers, data=payload)
    
    if response.status_code == 200:
        data = response.json()
        link = data.get("data", {}).get("link")
        return link
    else:
        raise Exception(f"Imgur 업로드 실패: {response.status_code} - {response.text}")

if __name__ == "__main__":
    # Test execution
    # print(upload_to_imgur("sample.png", "YOUR_IMGUR_CLIENT_ID"))
    pass
