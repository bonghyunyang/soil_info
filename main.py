from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
import uvicorn
from soil_info import get_soil_info_by_address

app = FastAPI()

# HTML 템플릿 디렉토리 설정
templates = Jinja2Templates(directory="templates")

# API 키 설정
JUSO_API_KEY = "devU01TX0FVVEgyMDI1MDMwMjEzNTYyNTExNTUxMDQ="
SOIL_API_KEY = "AExC2xVOtaEE0vN/Yb3geQ2K2jifusUyQlPdt4sv1pI/v4nToQ/BU3WPQ2QgIFOXPy/fi8IPEz39XfnIQB932Q=="

# Request 모델 추가
class SoilInfoRequest(BaseModel):
    address: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "요청 데이터 검증 실패",
            "detail": str(exc)
        }
    )

@app.post("/soil-info")
async def soil_info(request: SoilInfoRequest):
    result = get_soil_info_by_address(
        request.address,
        JUSO_API_KEY,
        SOIL_API_KEY
    )
    
    if not result:
        return {"success": False, "message": "토양 정보를 찾을 수 없습니다."}
        
    if 'error' in result:
        return {"success": False, "message": result['error']}
        
    return {
        "success": True,
        "data": result['soil_data'][0],
        "exact_match": result.get('exact_match', True),
        "matched_address": result.get('matched_address', '')
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 