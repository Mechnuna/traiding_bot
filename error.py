from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--verbose")  # Включить подробные логи
service = Service(executable_path="./chromedriver-mac-arm64/chromedriver")
driver = webdriver.Chrome(service=service, options=options)
