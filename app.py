# app.py
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS # CORS (Cross-Origin Resource Sharing) を有効にするために必要
import serial
import time
import sys
import os # osモジュールをインポート

# Flaskアプリケーションの初期化
app = Flask(__name__, static_folder='static') # static_folder を明示的に指定
# 開発中はCORSを許可して、異なるオリジンからのリクエストを受け入れる
# 本番環境では、フロントエンドのオリジンのみを許可するように設定を厳しくすることを推奨
CORS(app)

# シリアル通信のタイムアウト時間 (秒)
SERIAL_TIMEOUT = 1
# コマンド送信後にモジュールからの応答を待つ時間 (秒)
READ_RESPONSE_DURATION = 2

@app.route('/')
def index():
    """ルートURLへのアクセス時にsetup.htmlにリダイレクトする"""
    return redirect(url_for('serve_setup_html'))

@app.route('/setup.html')
def serve_setup_html():
    """staticフォルダからsetup.htmlを配信する"""
    return send_from_directory(app.static_folder, 'setup.html')

@app.route('/api/write_config', methods=['POST'])
def write_config():
    """
    フロントエンド (setup.html) から送られてきた設定コマンドをWTRTK-982モジュールに書き込む。
    """
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON data received"}), 400

    port = data.get('port')
    baudrate = data.get('baudrate')
    commands = data.get('commands')

    if not all([port, baudrate, commands is not None]):
        return jsonify({"status": "error", "message": "Missing port, baudrate, or commands"}), 400

    app.logger.info(f"Received write config request for port: {port}, baudrate: {baudrate}")
    app.logger.info(f"Commands to send: {commands}")

    received_data_lines = []
    try:
        # シリアルポートを開く
        # write_timeoutを設定することで、書き込みがブロックされるのを防ぐ
        ser = serial.Serial(port, baudrate, timeout=SERIAL_TIMEOUT, write_timeout=SERIAL_TIMEOUT)
        time.sleep(0.1) # ポートが開くのを少し待つ

        for cmd in commands:
            full_command = cmd.strip() + '\r\n'
            app.logger.info(f"Sending command: '{full_command.strip()}'")
            ser.write(full_command.encode('ascii')) # ASCIIエンコーディングで送信

            # コマンド送信後の応答を読み取る
            start_time = time.time()
            while (time.time() - start_time) < READ_RESPONSE_DURATION:
                if ser.in_waiting > 0:
                    try:
                        # モジュールからの応答を読み取り、デコードを試みる
                        line = ser.readline().decode('ascii', errors='ignore').strip()
                        if line:
                            received_data_lines.append(f"Received: {line}")
                            app.logger.info(f"Received: {line}")
                    except UnicodeDecodeError:
                        received_data_lines.append("Received: (Binary data - cannot decode as ASCII)")
                        app.logger.warning("Received binary data, cannot decode as ASCII.")
                    except Exception as e:
                        received_data_lines.append(f"Error reading during command: {e}")
                        app.logger.error(f"Error reading during command: {e}")
                time.sleep(0.01) # 短い遅延でCPU使用率を抑える

        ser.close()
        app.logger.info(f"Serial port '{port}' closed.")
        return jsonify({
            "status": "success",
            "message": "Configuration commands sent successfully.",
            "received_data": "\n".join(received_data_lines)
        }), 200

    except serial.SerialException as e:
        app.logger.error(f"Serial port error on {port}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Failed to open or communicate with serial port '{port}'. Error: {e}"
        }), 500
    except Exception as e:
        app.logger.error(f"Unexpected error during write config: {e}")
        return jsonify({
            "status": "error",
            "message": f"An unexpected error occurred: {e}"
        }), 500

@app.route('/api/save_config', methods=['POST'])
def save_config():
    """
    WTRTK-982モジュールに設定を永続的に保存するコマンドを送信する。
    """
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON data received"}), 400

    port = data.get('port')
    baudrate = data.get('baudrate')

    if not all([port, baudrate]):
        return jsonify({"status": "error", "message": "Missing port or baudrate"}), 400

    app.logger.info(f"Received save config request for port: {port}, baudrate: {baudrate}")
　　　save_command = "SAVECONFIG\r\n"

    

    try:
        ser = serial.Serial(port, baudrate, timeout=SERIAL_TIMEOUT, write_timeout=SERIAL_TIMEOUT)
        time.sleep(0.1)

        app.logger.info(f"Sending save command: '{save_command.strip()}'")
        ser.write(save_command.encode('ascii'))

        # SAVEコマンド後の応答も少し読み取る
        received_data_lines = []
        start_time = time.time()
        while (time.time() - start_time) < READ_RESPONSE_DURATION:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('ascii', errors='ignore').strip()
                    if line:
                        received_data_lines.append(f"Received: {line}")
                        app.logger.info(f"Received: {line}")
                except UnicodeDecodeError:
                    received_data_lines.append("Received: (Binary data - cannot decode as ASCII)")
                except Exception as e:
                    received_data_lines.append(f"Error reading during save: {e}")
            time.sleep(0.01)

        ser.close()
        app.logger.info(f"Serial port '{port}' closed after save command.")
        return jsonify({
            "status": "success",
            "message": "Configuration saved to module successfully.",
            "received_data": "\n".join(received_data_lines)
        }), 200

    except serial.SerialException as e:
        app.logger.error(f"Serial port error on {port} during save: {e}")
        return jsonify({
            "status": "error",
            "message": f"Failed to open or communicate with serial port '{port}' for saving. Error: {e}"
        }), 500
    except Exception as e:
        app.logger.error(f"Unexpected error during save config: {e}")
        return jsonify({
            "status": "error",
            "message": f"An unexpected error occurred: {e}"
        }), 500

if __name__ == '__main__':
    # Flaskアプリケーションを起動
    # ホストを '0.0.0.0' に設定することで、ラズベリーパイのどのIPアドレスからもアクセス可能にする
    # デフォルトポートは5000
    app.run(host='0.0.0.0', port=5000, debug=True) # debug=True は開発用

