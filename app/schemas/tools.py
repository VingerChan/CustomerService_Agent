from pydantic import BaseModel, Field
from typing import Optional

class ProductSearchParams(BaseModel):
    """商品搜索参数"""
    keyword: Optional[str] = Field(None, description="搜索关键词")
    category: Optional[str] = Field(None, description="商品分类")
    ordering: Optional[str] = Field(None, description="排序方式：comments-评论数, sales-销量, price-价格")
    min_price: Optional[float] = Field(None, description="最低价格")
    max_price: Optional[float] = Field(None, description="最高价格")
    page: int = Field(1, description="页码")
    page_size: int = Field(20, description="每页数量")