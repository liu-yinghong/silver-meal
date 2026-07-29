from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.adapters.web_api import router

app = FastAPI(
    title='银龄放心单 Silver Meal',
    description='适老点餐 Demo 服务 - 帮助恢复期独居老人安全、低负担地完成一顿饭',
    version='0.1.0',
)

app.include_router(router)

# 静态文件服务：前端页面
frontend_dir = Path('frontend')
if frontend_dir.exists():
    app.mount('/elder', StaticFiles(directory='frontend/elder', html=True), name='elder')
    app.mount('/family', StaticFiles(directory='frontend/family', html=True), name='family')


@app.get('/')
def root():
    return {
        'project': '银龄放心单',
        'version': '0.1.0',
        'docs': '/docs',
        'elder_page': '/elder/',
        'family_page': '/family/',
    }


@app.get('/health')
def health():
    return {'status': 'ok'}