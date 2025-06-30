import io
import json
import os
import re
from django.conf import settings
from django.core.mail import EmailMessage
import calendar
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
import pandas as pd
import firebase_admin
import numpy as np
import requests
import torch
from PIL import Image
from firebase_admin import credentials
from firebase_admin import db, storage
from paddleocr import PaddleOCR
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from ultralytics import YOLO
from sops.databaseurls import FIREBASE_DB_MAP
from sops.models import SopStep, City, Sops
from sops.serializers import CitySerializer, SopsSerializer
from sops.mailtowhom import site_info



cred = credentials.Certificate("sops/cert.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://dtdnavigator.firebaseio.com/',
        'storageBucket': 'dtdnavigator.appspot.com'
    })