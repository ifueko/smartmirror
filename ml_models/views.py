from django.shortcuts import render

def simple_audio_recorder(request):
    return render(request, 'ml_models/simple_recorder.html')
