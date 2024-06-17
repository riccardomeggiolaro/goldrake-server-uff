#/usr/bin/bash
source venv/bin/activate
pip install -r requirements.txt
pyinstaller --onefile --add-data "config.json:." --add-data "service.log:."  main.py
./dist/main