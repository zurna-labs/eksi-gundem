import os
import time
import json
import openai
import schedule
import requests
import threading

from bs4 import BeautifulSoup
from flask import Flask, render_template
from logger import Logger
from datetime import datetime
from summarizer import Summarizer
from urllib.parse import urlparse, urljoin

global CONTEXT
CONTEXT = None

# Create a lock
LOCK = threading.Lock()

# Configuration
BASE_EKSI_URL = "https://eksisozluk111.com"

log = Logger().log
log_main = Logger().log

############################################ UTILITIES ################################################

def get_current_date():
    return datetime.now().strftime('%Y-%m-%d')

# Load OpenAI API key from the file
def load_openai_api_key():
    log_main('+ Loading OpenAI API key')
    with open('openai.apikey', 'r') as api_key_file:
        api_key = api_key_file.read()
    log_main('- Loaded OpenAI API key')
    return api_key


def initialize_directories():
    log('+ Initializing directories')
    # Path to store the parsed topics
    TOPICS_PATH = get_current_date() + "/topics"
    SUMMARIES_PATH = get_current_date() + "/summaries"

    if not os.path.exists(TOPICS_PATH):
        os.makedirs(TOPICS_PATH)

    if not os.path.exists(SUMMARIES_PATH):
        os.makedirs(SUMMARIES_PATH)

    log('- Directories initialized')
    return TOPICS_PATH, SUMMARIES_PATH

def fetch_html_content(url):
    log('+ Requesting....')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        content = response.text
        log('- Request complete')
        return content
    except requests.exceptions.RequestException as e:
        log(f'- Error during request: {e}')
        return None

def parse_soup(response):
    return BeautifulSoup(response, "html.parser")

def save_to_json(filepath, data):
    with open(filepath, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_topics_of_the_day(base_url):
    log('+ Fetching topics of the day')
    url = urljoin(base_url, "/basliklar/m/populer")
    response = fetch_html_content(url)
    soup = parse_soup(response)

    topic_list = soup.find("ul", class_="topic-list partial")
    topics = [(topic.text, topic["href"]) for topic in topic_list.find_all("a")]

    log('- Fetching complete')
    return topics

def parse_topic(base_url, title, endpoint, topics_path):
    log('+ Parsing topic: ' + title)
    url = urljoin(base_url, endpoint)
    response = fetch_html_content(url)
    soup = parse_soup(response)

    entries = []
    for entry in soup.find_all("li", id="entry-item"):
        text = entry.find("div", class_="content").text.strip()
        entries.append(text)

    # Generate a filename based on the URL
    parsed_url = urlparse(url)
    filename = f"{parsed_url.path[1:].replace('/', '_')}.json"
    filepath = os.path.join(topics_path, filename)

    # Save the parsed entries to a local JSON file with proper encoding and indentation
    timestamp = int(time.time())
    json_data = {
        "title": title, 
        "entries": entries, 
        "timestamp": timestamp,
        "url": endpoint
    }
    log('- Parsing complete')
    save_to_json(filepath, json_data)

def create_summary(base_url, topic_filepath, summaries_path):
    log("+ Creating summary for " + topic_filepath)
    with open(topic_filepath, "r", encoding='utf-8') as f:
        topic_data = json.load(f)

    entries = topic_data["entries"]

    # # Generate a filename for the summary based on the URL
    summary_filename = os.path.basename(topic_filepath)
    summary_filepath = os.path.join(summaries_path, summary_filename)

    # added
    summary_text = Summarizer(log).summarize(entries)

    # # Save the summary to a local JSON file with proper encoding and indentation
    timestamp = int(time.time())
    summary_data = {"title": topic_data["title"], "summary": summary_text, "timestamp": timestamp}

    save_to_json(summary_filepath, summary_data)
    log("- Summary created for " + topic_data["title"])


def fetch_and_parse_topics(base_url, topics_path, summaries_path):
    log('+ Parse topics ...')
    topics = fetch_topics_of_the_day(base_url)
    for title, url in topics:
        # Check if the topic has been parsed in the last 2 hours
        filepath = os.path.join(topics_path, f"{urlparse(url).path[1:].replace('/', '_')}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding='utf-8') as f:
                parsed_data = json.load(f)
                last_timestamp = parsed_data.get("timestamp", 0)
                current_timestamp = int(time.time())
                time_difference = current_timestamp - last_timestamp
                if time_difference < 7200:  # 2 hours in seconds
                    # log(f"{title} has been parsed recently. Skipping.")
                    continue

        # Parse the topic
        parse_topic(base_url, title, url, topics_path)

    log('> ... and summarize')
    for filename in os.listdir(topics_path):
        if not filename.endswith('.json'):
            continue
        # Check if the topic has been parsed in the last 2 hours
        summary_filepath = os.path.join(summaries_path, filename)
        topic_filepath = os.path.join(topics_path, filename)
        if os.path.exists(summary_filepath):
            with open(filepath, "r", encoding='utf-8') as f:
                parsed_data = json.load(f)
                last_timestamp = parsed_data.get("timestamp", 0)
                current_timestamp = int(time.time())
                time_difference = current_timestamp - last_timestamp
                if time_difference < 7200:  # 2 hours in seconds
                    # log(f"{filename} has been summarized recently. Skipping.")
                    continue

        # Create a summary for the topic
        create_summary(base_url, topic_filepath, summaries_path)
    log('- Parse and summarize complete')

def load_topics_and_summaries(topics_path, summaries_path):
    topics_data = {}
    for filename in os.listdir(summaries_path):
        if not filename.endswith(".json"):
            continue
        topics_filepath = os.path.join(topics_path, filename)
        summary_filepath = os.path.join(summaries_path, filename)
        with open(topics_filepath, "r", encoding='utf-8') as f:
            topic_data = json.load(f)
        with open(summary_filepath, "r", encoding='utf-8') as f:
            summary_data = json.load(f)
        topics_data[filename] = {**topic_data, **summary_data}
    return topics_data

def populate_context(topics_path, summaries_path):

    topics_data = load_topics_and_summaries(topics_path, summaries_path)
    topics_list = sorted(topics_data.items(), key=lambda k: -1*int(k[1]['title'].split()[-1]))

    with LOCK:
        global CONTEXT
        CONTEXT = {
            "topics_list": topics_list,
            "base_url": BASE_EKSI_URL
        }

def processing_routine():
    topics_path, summaries_path = initialize_directories()

    populate_context(topics_path, summaries_path)

    fetch_and_parse_topics(BASE_EKSI_URL, topics_path, summaries_path)

    populate_context(topics_path, summaries_path)

def schedule_topic_fetching(fetch_and_parse_topics_func):
    # Run fetch_and_parse_topics once before scheduling
    fetch_and_parse_topics_func()

    time.sleep(60)

    # Schedule the topic fetching task
    schedule.every(24).hours.do(fetch_and_parse_topics_func)

    # Periodically check for new topics
    while True:
        schedule.run_pending()
        time.sleep(60)


############################################ FLASK ################################################

# Initialization
openai.api_key = load_openai_api_key()

# Topic processing thread
threading.Thread(target=schedule_topic_fetching, args=(processing_routine,)).start()
# processing_routine()

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html", context=CONTEXT)

app.run(debug=False)


