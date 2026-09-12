import os
import glob
import tempfile
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

# 允許前端 HTML 跨來源請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp4"  # "mp4" 或 "mp3"

def cleanup(file_path: str, temp_dir: str):
    """檔案傳輸後自動清理暫存檔"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
    except Exception:
        pass

@app.post("/download")
async def process_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    temp_dir = tempfile.mkdtemp()
    outtmpl = os.path.join(temp_dir, "%(title)s.%(ext)s")

    if req.format.lower() == "mp3":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
        }
        target_ext = "mp3"
        media_type = "audio/mpeg"
    else:
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "quiet": True,
        }
        target_ext = "mp4"
        media_type = "video/mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([req.url])

        matched_files = glob.glob(os.path.join(temp_dir, f"*.{target_ext}"))
        if not matched_files:
            raise HTTPException(status_code=500, detail="轉檔失敗，找不到輸出檔案")

        file_path = matched_files[0]
        filename = os.path.basename(file_path)

        # 請求完成後自動清理暫存
        background_tasks.add_task(cleanup, file_path, temp_dir)

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
    except Exception as e:
        cleanup("", temp_dir)
        raise HTTPException(status_code=400, detail=str(e))
