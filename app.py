from flask import Flask, render_template, request, jsonify, send_file
import pyttsx3
import os
import tempfile
from datetime import datetime
import threading
import time
from gtts import gTTS
import io
import pygame

app = Flask(__name__)

class TTSManager:
    def __init__(self):
        pygame.mixer.init()
        self._init_engine()
        self.lock = threading.Lock()  # <-- CHANGED

    def _init_engine(self):
        try:
            self.pyttsx_engine = pyttsx3.init()
            self.setup_pyttsx_voice()
        except Exception as e:
            print(f"Error initializing engine: {str(e)}")
            try:
                if hasattr(self, 'pyttsx_engine'):
                    self.pyttsx_engine.stop()
            except:
                pass
            self.pyttsx_engine = pyttsx3.init()
            self.setup_pyttsx_voice()

    def setup_pyttsx_voice(self):
        voices = self.pyttsx_engine.getProperty('voices')
        for voice in voices:
            if 'indonesia' in voice.name.lower() or 'id' in voice.id.lower():
                self.pyttsx_engine.setProperty('voice', voice.id)
                break
        self.pyttsx_engine.setProperty('rate', 150)
        self.pyttsx_engine.setProperty('volume', 0.9)

    def set_speed(self, speed):
        speed_map = {
            'slow': 100,
            'normal': 150,
            'fast': 200
        }
        self.pyttsx_engine.setProperty('rate', speed_map.get(speed, 150))

    def play_audio_file(self, filepath):
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"Error playing audio: {str(e)}")
            
    def text_to_speech(self, text, speed='normal', gender='default', save_file=False, file_format=None):
        try:
            # Otomatis pilih format
            if file_format is None:
                file_format = 'mp3' if gender == 'female' else 'wav'

            if gender == 'female':
                temp_dir = tempfile.gettempdir()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"tts_output_{timestamp}.{file_format}"
                filepath = os.path.join(temp_dir, filename)

                tts = gTTS(text=text, lang='id', slow=(speed == 'slow'))
                tts.save(filepath)

                if save_file:
                    return filepath
                else:
                    self.play_audio_file(filepath)
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    return None
            else:
                with self.lock:
                    self._init_engine()
                    self.set_speed(speed)

                    temp_dir = tempfile.gettempdir()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"tts_output_{timestamp}.{file_format}"
                    filepath = os.path.join(temp_dir, filename)

                    self.pyttsx_engine.save_to_file(text, filepath)
                    self.pyttsx_engine.runAndWait()

                    if save_file:
                        return filepath
                    else:
                        self.play_audio_file(filepath)
                        try:
                            os.remove(filepath)
                        except:
                            pass
                        return None


        except Exception as e:
            print(f"Error in TTS: {str(e)}")
            try:
                if hasattr(self, 'pyttsx_engine'):
                    self.pyttsx_engine.stop()
            except:
                pass
            self._init_engine()
            return None


# Initialize TTS Manager
tts_manager = TTSManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/speak', methods=['POST'])
def speak():
    try:
        data = request.json
        text = data.get('text', '')
        speed = data.get('speed', 'normal')
        gender = data.get('gender', 'default')
        
        if not text.strip():
            return jsonify({'error': 'Teks tidak boleh kosong'}), 400
        
        # Run TTS in background thread to avoid blocking
        def speak_async():
            tts_manager.text_to_speech(text, speed, gender)
        
        thread = threading.Thread(target=speak_async)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Sedang memutar audio...'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        text = data.get('text', '')
        speed = data.get('speed', 'normal')
        gender = data.get('gender', 'default')
        file_format = data.get('format', 'wav')

        if not text.strip():
            return jsonify({'error': 'Teks tidak boleh kosong'}), 400

        filepath = tts_manager.text_to_speech(
            text, speed, gender, save_file=True, file_format=file_format
        )

        if filepath and os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                data = f.read()

            response = send_file(
                io.BytesIO(data),
                as_attachment=True,
                download_name=f"tts_output.{file_format}",
                mimetype='audio/mpeg' if file_format == 'mp3' else 'audio/wav'
            )
            response.headers["Content-Length"] = str(len(data))
            return response
        else:
            return jsonify({'error': 'Gagal membuat file audio'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)