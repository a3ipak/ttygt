from django.shortcuts import render

# Create your views here.
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextSendMessage, ImageSendMessage

from googletrans import Translator
import requests
import numpy as np
import matplotlib.pyplot as plt
from PIL import ImageFont, ImageDraw, Image
import time
import random
import openai

import cloudinary
cloudinary.config(cloud_name = settings.CLOUD_NAME,
                  api_key = settings.CLOUD_API_KEY,
                  api_secret = settings.CLOUD_API_SECRET)
                    
import cloudinary.uploader
import cloudinary.api

def debug_print(tmpstr):
    print(f'\n##### debug: {tmpstr}\n')

line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)
Your_User_ID = settings.YOUR_USER_ID
STATIC_ROOT = settings.STATIC_ROOT

line_bot_api.push_message(Your_User_ID, TextSendMessage(text='請輸入中文關鍵字（ex: 雞湯）'))

# 處理訊息
@csrf_exempt
def callback(request):
    debug_print('in callback function')
    if request.method == 'POST':
        signature = request.META['HTTP_X_LINE_SIGNATURE']
        body = request.body.decode('utf-8')
        try:
            event = parser.parse(body, signature)[0]
            keyword = event.message.text
            debug_print(f'users\' keyword: {keyword}')

            # initiate google translator
            translator = Translator()  
            results = translator.translate(keyword, dest='en')
            eng_keyword = results.text
            debug_print(f'translate done: {eng_keyword}')


            # https://deepai.org/machine-learning-model/cute-creature-generator
            r = requests.post(
                "https://api.deepai.org/api/fantasy-world-generator",
                data = { 'text': eng_keyword },
                headers={'api-key': 'quickstart-QUdJIGlzIGNvbWluZy4uLi4K'}
            )
            time.sleep(3)
            try:
                # {'status': "Looks like you're enjoying our API. 
                # Want to keep using it? Sign up to get an API Key 
                # that's as unique as you are. https://deepai.org/"}
                img_url = r.json()['output_url']
                r_img = requests.get(img_url, stream = True)
                f_img = open(STATIC_ROOT + '/output_from_ai.jpg', 'wb')
                debug_print('get and save the deepai picture')
                f_img.write(r_img.content)
                f_img.close()
            except KeyError:
                debug_print(r.json())
            finally:
                img = plt.imread(STATIC_ROOT + '/output_from_ai.jpg')
                debug_print('read the downloading picture')

            # ai will output 4 image in one picture
            # randomly crop it
            pic_coord = [(0, 512, 0 ,512), (512, 1023, 0, 512), (512, 1023, 512, 1023), (0, 512, 512, 1023)]
            (xs, xe, ys, ye) = pic_coord[random.randint(0,3)]
            img_crop = img[xs:xe, ys:ye, :]
            debug_print('2x2 image crop into 1 image')


            openai.api_key = settings.CHATGPT_API_KEY
            bs = openai.Completion.create(
                model = 'text-davinci-003',
                prompt = f'以\"{keyword}\"給我一首詩',
                max_tokens = 150,
                temperature = 0.7
            )
            time.sleep(3)
            debug_print('openai ChatGPT text generating done')
            bs_text = bs['choices'][0]['text']
            debug_print(bs_text)
            tmp_lst = []
            for i in bs_text.split('\n')[:-1]:
                for j in i.split('，'):
                    if len(j) > 1:
                        tmp_lst.append(j)
            bs_text_final = '\n'.join(tmp_lst)

            debug_print('start: adding text into image')
            fontpath = STATIC_ROOT + '/msjh.ttf'
            font = ImageFont.truetype(fontpath, 20)
            imgPil = Image.fromarray(img_crop)
            draw = ImageDraw.Draw(imgPil)

            x, y = 10, 10
            fillcolor = "white"
            shadowcolor = "gray"

            draw.text((x-1, y), bs_text_final, font=font, fill=shadowcolor)
            draw.text((x+1, y), bs_text_final, font=font, fill=shadowcolor)
            draw.text((x, y-1), bs_text_final, font=font, fill=shadowcolor)
            draw.text((x, y+1), bs_text_final, font=font, fill=shadowcolor)

            # thicker border
            draw.text((x-1, y-1), bs_text_final, font=font, fill=shadowcolor)
            draw.text((x+1, y-1), bs_text_final, font=font, fill=shadowcolor)
            draw.text((x-1, y+1), bs_text_final, font=font, fill=shadowcolor)
            draw.text((x+1, y+1), bs_text_final, font=font, fill=shadowcolor)


            draw.text((x, y), bs_text_final, fill=fillcolor, font=font)
            img = np.array(imgPil)                   
            plt.imsave(STATIC_ROOT + '/ai_img_with_text.jpg', img)
            debug_print('image processing is done (adding text and save locally')

            cloud_res = cloudinary.uploader.upload(STATIC_ROOT + "/ai_img_with_text.jpg", folder = "ttygt/", overwrite = True)
            debug_print('image uploaded to cloudinary')
            message = ImageSendMessage(
                original_content_url=cloud_res['secure_url'],
                preview_image_url=cloud_res['secure_url'],
            )
            reply_arr = []
            reply_arr.append(TextSendMessage(text=bs_text_final))
            reply_arr.append(message)
            line_bot_api.reply_message(event.reply_token, reply_arr)
        except InvalidSignatureError:
             return HttpResponseForbidden()
        except LineBotApiError:
             return HttpResponseBadRequest()
    
        return HttpResponse()
    else:
        return HttpResponseBadRequest()