# src/_ocr_worker.py
import sys
import asyncio
import io

# [추가] stdout을 UTF-8로 강제 변경
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import winsdk.windows.security.cryptography as crypto
import winsdk.windows.storage.streams as streams
import winsdk.windows.media.ocr as ocr
import winsdk.windows.graphics.imaging as imaging
import winsdk.windows.globalization as globalization

async def run_ocr(image_path: str) -> str:
    from pathlib import Path
    path = Path(image_path).resolve()
    
    with open(path, "rb") as f:
        bytes_data = f.read()
    
    crypt_buffer = crypto.CryptographicBuffer.create_from_byte_array(bytes_data)
    stream = streams.InMemoryRandomAccessStream()
    await stream.write_async(crypt_buffer)
    stream.seek(0)
    
    decoder = await imaging.BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    
    target_lang = globalization.Language("ko-KR")
    engine = ocr.OcrEngine.try_create_from_language(target_lang)
    if not engine:
        engine = ocr.OcrEngine.try_create_from_language(
            ocr.OcrEngine.get_available_languages()[0]
        )
    
    result = await engine.recognize_async(software_bitmap)
    return "\n".join([line.text for line in result.lines])

if __name__ == "__main__":
    image_path = sys.argv[1]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    text = loop.run_until_complete(run_ocr(image_path))
    loop.close()
    print(text)