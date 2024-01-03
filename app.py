import os
import time
import json
from urllib.parse import urljoin, urlparse
import subprocess
from bs4 import BeautifulSoup
from flask import Flask, render_template
import schedule
import openai

# Load OpenAI API key from the file
with open('openai.apikey', 'r') as api_key_file:
    openai.api_key = api_key_file.read().strip()

app = Flask(__name__)

BASE_EKSI_URL = "https://eksisozluk111.com"

# Path to store the parsed topics
TOPICS_PATH = "topics"
SUMMARIES_PATH = "summaries"

if not os.path.exists(TOPICS_PATH):
    os.makedirs(TOPICS_PATH)

if not os.path.exists(SUMMARIES_PATH):
    os.makedirs(SUMMARIES_PATH)

def fetch_topics_of_the_day():
    curl_command = f"curl '{BASE_EKSI_URL}/basliklar/m/populer'"
    response = subprocess.check_output(curl_command, shell=True).decode('utf-8')
    soup = BeautifulSoup(response, "html.parser")

    topic_list = soup.find("ul", class_="topic-list partial")
    topics = [(topic.text, topic["href"]) for topic in topic_list.find_all("a")]

    return topics

def parse_topic(title, url):
    curl_command = f"curl '{BASE_EKSI_URL}{url}'"
    response = subprocess.check_output(curl_command, shell=True).decode('utf-8')
    soup = BeautifulSoup(response, "html.parser")

    entries = []
    for entry in soup.find_all("li", id="entry-item"):
        text = entry.find("div", class_="content").text.strip()
        entries.append(text)

    # Generate a filename based on the URL
    parsed_url = urlparse(url)
    filename = f"{parsed_url.path[1:].replace('/', '_')}.json"
    filepath = os.path.join(TOPICS_PATH, filename)

    # Save the parsed entries to a local JSON file with proper encoding and indentation
    timestamp = int(time.time())
    json_data = {"title": title, "entries": entries, "timestamp": timestamp}

    with open(filepath, "w", encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

def create_summary(topic_filepath):
    with open(topic_filepath, "r", encoding='utf-8') as f:
        topic_data = json.load(f)

    entries = topic_data["entries"]
    entry_text = topic_data["title"] + "\n"
    entry_text += "\n".join([f"- {e}" for e in entries])
    entry_text += "\n\n Bazı insanlar bugün yukarıdaki yazıları yazmış. Anlatılmak istenenleri kısa bir paragrafla özetle. Sadece özeti yaz, kibarlık yapma. Gereksiz detay verme. Çok kısa cevap ver ve anahtar noktalara değin."

    # Use OpenAI API for summarization
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type":"text",
                        "text":entry_text
                    }
                ]
            }
        ],
        max_tokens=300
    )
    print(response)
    summary_text = response['choices'][0]["message"]["content"]

    # Generate a filename for the summary based on the URL
    summary_filename = os.path.basename(topic_filepath)
    summary_filepath = os.path.join(SUMMARIES_PATH, summary_filename)

    # Save the summary to a local JSON file with proper encoding and indentation
    timestamp = int(time.time())
    summary_data = {"title": topic_data["title"], "summary": summary_text, "timestamp": timestamp}

    with open(summary_filepath, "w", encoding='utf-8') as summary_file:
        json.dump(summary_data, summary_file, ensure_ascii=False, indent=2)
        print("Summary created for " + topic_data["title"])

def fetch_and_parse_topics():
    topics = fetch_topics_of_the_day()
    for title, url in topics:
        # Check if the topic has been parsed in the last 2 hours
        filepath = os.path.join(TOPICS_PATH, f"{urlparse(url).path[1:].replace('/', '_')}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding='utf-8') as f:
                parsed_data = json.load(f)
                last_timestamp = parsed_data.get("timestamp", 0)
                current_timestamp = int(time.time())
                time_difference = current_timestamp - last_timestamp
                if time_difference < 7200:  # 2 hours in seconds
                    print(f"{title} has been parsed recently. Skipping.")
                    continue

        # Parse the topic
        parse_topic(title, url)

    for title, url in topics:
        # Check if the topic has been parsed in the last 2 hours
        summary_filepath = os.path.join(SUMMARIES_PATH, f"{urlparse(url).path[1:].replace('/', '_')}.json")
        topic_filepath = os.path.join(TOPICS_PATH, f"{urlparse(url).path[1:].replace('/', '_')}.json")
        if os.path.exists(summary_filepath):
            with open(filepath, "r", encoding='utf-8') as f:
                parsed_data = json.load(f)
                last_timestamp = parsed_data.get("timestamp", 0)
                current_timestamp = int(time.time())
                time_difference = current_timestamp - last_timestamp
                if time_difference < 7200:  # 2 hours in seconds
                    print(f"{title} has been parsed recently. Skipping.")
                    continue

        # Create a summary for the topic
        create_summary(topic_filepath)

@app.route("/")
def index():
    topics_data = {}
    for filename in os.listdir(TOPICS_PATH):
        with open(os.path.join(TOPICS_PATH, filename), "r", encoding='utf-8') as f:
            topic_data = json.load(f)
        with open(os.path.join(SUMMARIES_PATH, filename), "r", encoding='utf-8') as f:
            summary_data = json.load(f)
        topics_data[filename] = {**topic_data, **summary_data}
    context = {"topics": topics_data}
    
    return render_template("index.html", context=context)


if __name__ == "__main__":
    # Run fetch_and_parse_topics once before scheduling
    fetch_and_parse_topics()

    # Schedule the topic fetching task
    schedule.every(4).hours.do(fetch_and_parse_topics)

    # Run the Flask app
    app.run(debug=True)

    # Periodically check for new topics
    while True:
        schedule.run_pending()
        time.sleep(1)
