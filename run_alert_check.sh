#!/bin/bash
cd /home/yusuf/TOOLP/tool-tracker
source venv/bin/activate
python manage.py check_calibrations >> logs/alerts_$(date +\%Y\%m\%d).log 2>&1