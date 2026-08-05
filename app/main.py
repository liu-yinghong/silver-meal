from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.adapters.web_api import router

app = FastAPI(
    title='饭心·银龄放心单 Silver Meal API',
    description='适老点餐 Demo 服务 - 帮助恢复期独居老人安全、低负担地完成一顿饭',
    version='0.1.0',
)

# 允许跨域请求，前后端分离后前端可跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
    allow_credentials=True,
)

app.include_router(router)

# 前端页面托管（前后端分离，前端通过同一后端静态服务访问）
frontend_dir = Path('frontend')
if frontend_dir.exists():
    app.mount('/elder', StaticFiles(directory='frontend/elder', html=True), name='elder')
    app.mount('/family', StaticFiles(directory='frontend/family', html=True), name='family')


@app.get('/')
def root():
    return {
        'project': '饭心·银龄放心单',
        'version': '0.1.0',
        'docs': '/docs',
        'elder_page': '/elder/',
        'family_page': '/family/',
    }


@app.get('/health')
def health():
    return {'status': 'ok'}
