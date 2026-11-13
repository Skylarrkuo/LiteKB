from django.urls import path

from chat import views
from chat.views.mcp import mcp_view
from maxkb.capabilities import MEDIA_NODES

app_name = 'chat'

urlpatterns = [
    path('mcp', mcp_view),
    path('open', views.OpenView.as_view(), name='open'),
    path('chat_message/<str:chat_id>', views.ChatView.as_view(), name='chat'),
    path('<str:application_id>/chat/completions', views.OpenAIView.as_view(), name='application/chat_completions'),
]

if MEDIA_NODES:
    urlpatterns += [
        path('text_to_speech', views.TextToSpeech.as_view()),
        path('speech_to_text', views.SpeechToText.as_view()),
    ]
