"""
Точка входа для запуска парсера
"""
import sys
sys.path.insert(0, 'src')

from main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
