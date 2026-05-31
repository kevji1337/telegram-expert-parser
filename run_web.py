"""
Точка входа для веб-интерфейса
Запуск: python run_web.py
URL: http://localhost:5000
"""
import sys
sys.path.insert(0, 'src')

from web.app import app

if __name__ == "__main__":
    print("Веб-интерфейс запущен на http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
