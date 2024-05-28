import os
import json
import requests


if __name__ == "__main__":
    url = os.getenv("VLM_BACKEND_ENDPOINT")

    image_url = "https://news.cgtn.com/news/2023-01-02/Shaolin-spirit-lives-on-in-kung-fu-pupils-1ggiWpJcmVa/img/5e1e6c4fba30426c86a16f3c7e1e9448/5e1e6c4fba30426c86a16f3c7e1e9448.jpeg"

    data = {
        "image_url": image_url
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=data, headers=headers, verify=False)

    print(response.text)
