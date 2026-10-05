"""HTTP API entry point. The frontend never supplies the calculation result."""

import csv
import io
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .calculator import CalculationError, calculate
from .database import HistoryStore


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expression: str = Field(min_length=1, max_length=1024)


class FavoriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    is_favorite: bool


def create_app(database_path: Path | None = None) -> FastAPI:
    path = database_path or Path(
        os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parents[1] / "data" / "calculator.db"))
    )
    store = HistoryStore(path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        store.initialize()
        yield

    application = FastAPI(title="Calculator API", version="1.1.0", lifespan=lifespan)
    origins = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return JSONResponse(status_code=error.status_code, content={"success": False, "message": str(error.detail)})

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(status_code=422, content={"success": False, "message": "请求参数格式错误，请检查表达式和分页参数"})

    @application.exception_handler(sqlite3.Error)
    async def database_error(request: Request, error: sqlite3.Error):
        logging.exception("Database operation failed", exc_info=error)
        return JSONResponse(status_code=503, content={"success": False, "message": "数据库暂时不可用，请稍后重试"})

    @application.get("/api/health")
    def health():
        with store.connect() as connection:
            connection.execute("SELECT COUNT(*) FROM calculation_history").fetchone()
        return {"success": True, "status": "ok"}

    @application.post("/api/calculate", status_code=201)
    def calculate_expression(payload: CalculationRequest):
        try:
            expression, result = calculate(payload.expression)
        except CalculationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        record = store.insert(expression, result)
        return {"success": True, **record}

    @application.get("/api/history")
    def get_history(
        page: int = Query(default=1, ge=1, le=1000000),
        limit: int = Query(default=10, ge=1, le=100),
        search: str = Query(default="", max_length=1024),
        favorites_only: bool = False,
    ):
        return {"success": True, **store.list(page, limit, search, favorites_only)}

    @application.get("/api/history/export", response_class=Response)
    def export_history(search: str = Query(default="", max_length=1024), favorites_only: bool = False):
        records = store.export(search, favorites_only)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["ID", "表达式", "结果", "计算时间（UTC）", "收藏"])
        for record in records:
            expression = record["expression"]
            # Preserve leading +/- expressions as text when opening in a spreadsheet.
            if expression.startswith(("=", "+", "-", "@")):
                expression = "'" + expression
            writer.writerow([
                record["id"], expression, record["result"], record["created_at"],
                "是" if record["is_favorite"] else "否",
            ])
        filename = f"calculation-history-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.csv"
        return Response(
            content=output.getvalue().encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
        )

    @application.patch("/api/history/{record_id}/favorite")
    def set_favorite(record_id: int, payload: FavoriteRequest):
        record = store.set_favorite(record_id, payload.is_favorite) if record_id > 0 else None
        if record is None:
            raise HTTPException(status_code=404, detail="这条历史记录不存在或已被删除")
        return {"success": True, **record}

    @application.delete("/api/history/{record_id}")
    def delete_history(record_id: int):
        if record_id <= 0 or not store.delete(record_id):
            raise HTTPException(status_code=404, detail="这条历史记录不存在或已被删除")
        return {"success": True, "deleted_id": record_id}

    return application


app = create_app()
