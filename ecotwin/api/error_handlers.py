from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from ecotwin.errors import TwinError

def problem(request,code,detail,status,missing=None):
    headers={'WWW-Authenticate':'Bearer'} if status==401 else {}
    return JSONResponse(status_code=status,media_type='application/problem+json',headers=headers,content={'type':'urn:ecotwin:error:'+code,'title':code,'status':status,'detail':detail,'code':code,'request_id':getattr(request.state,'request_id',''),'missing_inputs':missing or []})

def register_handlers(app):
    @app.exception_handler(TwinError)
    async def twin(request,exc):return problem(request,exc.code,exc.detail,exc.status,exc.missing_inputs)
    @app.exception_handler(RequestValidationError)
    async def validation(request,exc):return problem(request,'INVALID_REQUEST','Request shape or field values are invalid',422)
    @app.exception_handler(HTTPException)
    async def http(request,exc):return problem(request,'HTTP_ERROR','Request could not be served',exc.status_code)
    @app.exception_handler(Exception)
    async def internal(request,exc):return problem(request,'INTERNAL_ERROR','Request failed; inspect correlated server logs',500)
