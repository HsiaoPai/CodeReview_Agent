"""Web 入口：python -m cra.web 启动本地服务。"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("cra.web.app:app", host="127.0.0.1", port=8000, reload=False)
