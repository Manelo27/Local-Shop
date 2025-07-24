from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Management API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URL)
db = client.stock_management
products_collection = db.products

# Pydantic models
class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    barcode: Optional[str] = None
    price: float
    cost_price: Optional[float] = None
    stock_quantity: int
    low_stock_threshold: int = 10  # Seuil personnalisable pour alerte stock faible
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    supplier: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    barcode: Optional[str] = None
    price: Optional[float] = None
    cost_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    supplier: Optional[str] = None

class StockAlert(BaseModel):
    product_id: str
    name: str
    current_stock: int
    threshold: int = 10

# Standard categories for French commerce
STANDARD_CATEGORIES = [
    "ALIMENTAIRE",
    "BOISSONS", 
    "HYGIENE_BEAUTE",
    "TEXTILE",
    "ELECTRONIQUE",
    "MAISON_JARDIN",
    "SPORT_LOISIRS",
    "ARTISANAT",
    "AUTRE"
]

SUBCATEGORIES = {
    "ALIMENTAIRE": ["BOUCHERIE", "BOULANGERIE", "EPICERIE", "FRUITS_LEGUMES", "PRODUITS_FRAIS"],
    "BOISSONS": ["ALCOOLISEES", "NON_ALCOOLISEES", "CHAUDES"],
    "HYGIENE_BEAUTE": ["HYGIENE", "COSMETIQUES", "PARFUMS"],
    "TEXTILE": ["VETEMENTS", "CHAUSSURES", "ACCESSOIRES"],
    "ARTISANAT": ["FAIT_MAIN", "MATERIAUX", "OUTILS"]
}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/api/categories")
async def get_categories():
    return {
        "categories": STANDARD_CATEGORIES,
        "subcategories": SUBCATEGORIES
    }

@app.post("/api/products", response_model=Product)
async def create_product(product: Product):
    try:
        # Calculate margin if cost_price is provided
        margin = None
        if product.cost_price and product.price > product.cost_price:
            margin = ((product.price - product.cost_price) / product.price) * 100
        
        product_dict = product.dict()
        if margin:
            product_dict["margin"] = round(margin, 2)
        
        result = products_collection.insert_one(product_dict)
        if result.inserted_id:
            logger.info(f"Created product: {product.name}")
            return product
        else:
            raise HTTPException(status_code=500, detail="Failed to create product")
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products", response_model=List[Product])
async def get_products(category: Optional[str] = None, search: Optional[str] = None):
    try:
        query = {}
        if category:
            query["category"] = category
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"barcode": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        products = list(products_collection.find(query, {"_id": 0}))
        return products
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    try:
        product = products_collection.find_one({"id": product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/products/{product_id}", response_model=Product)
async def update_product(product_id: str, product_update: ProductUpdate):
    try:
        update_data = {k: v for k, v in product_update.dict().items() if v is not None}
        update_data["updated_at"] = datetime.now()
        
        # Recalculate margin if price or cost_price changed
        existing_product = products_collection.find_one({"id": product_id}, {"_id": 0})
        if not existing_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        new_price = update_data.get("price", existing_product.get("price"))
        new_cost_price = update_data.get("cost_price", existing_product.get("cost_price"))
        
        if new_price and new_cost_price and new_price > new_cost_price:
            margin = ((new_price - new_cost_price) / new_price) * 100
            update_data["margin"] = round(margin, 2)
        
        result = products_collection.update_one(
            {"id": product_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        
        updated_product = products_collection.find_one({"id": product_id}, {"_id": 0})
        logger.info(f"Updated product: {product_id}")
        return updated_product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str):
    try:
        result = products_collection.delete_one({"id": product_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        
        logger.info(f"Deleted product: {product_id}")
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    try:
        total_products = products_collection.count_documents({})
        
        # Count products with low stock using their individual thresholds
        low_stock_pipeline = [
            {"$match": {"$expr": {"$lte": ["$stock_quantity", "$low_stock_threshold"]}}},
            {"$count": "low_stock_count"}
        ]
        low_stock_result = list(products_collection.aggregate(low_stock_pipeline))
        low_stock_products = low_stock_result[0]["low_stock_count"] if low_stock_result else 0
        
        # Total stock value
        pipeline = [
            {"$group": {
                "_id": None,
                "total_value": {"$sum": {"$multiply": ["$price", "$stock_quantity"]}},
                "total_cost": {"$sum": {"$multiply": ["$cost_price", "$stock_quantity"]}}
            }}
        ]
        
        value_result = list(products_collection.aggregate(pipeline))
        total_value = value_result[0]["total_value"] if value_result else 0
        total_cost = value_result[0]["total_cost"] if value_result else 0
        
        # Category breakdown
        category_pipeline = [
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "value": {"$sum": {"$multiply": ["$price", "$stock_quantity"]}}
            }}
        ]
        
        category_stats = list(products_collection.aggregate(category_pipeline))
        
        return {
            "total_products": total_products,
            "low_stock_alerts": low_stock_products,
            "total_stock_value": round(total_value, 2),
            "total_cost_value": round(total_cost, 2),
            "estimated_profit": round(total_value - total_cost, 2),
            "category_breakdown": category_stats
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts/low-stock", response_model=List[StockAlert])
async def get_low_stock_alerts():
    try:
        # Find products where stock_quantity <= low_stock_threshold
        products = list(products_collection.find(
            {"$expr": {"$lte": ["$stock_quantity", "$low_stock_threshold"]}},
            {"_id": 0, "id": 1, "name": 1, "stock_quantity": 1, "low_stock_threshold": 1}
        ))
        
        alerts = [
            StockAlert(
                product_id=p["id"],
                name=p["name"],
                current_stock=p["stock_quantity"],
                threshold=p.get("low_stock_threshold", 10)
            )
            for p in products
        ]
        
        return alerts
    except Exception as e:
        logger.error(f"Error fetching low stock alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/products")
async def export_products():
    """Export all products in standardized JSON format for external systems"""
    try:
        products = list(products_collection.find({}, {"_id": 0}))
        
        # Standardized export format
        export_data = {
            "export_info": {
                "timestamp": datetime.now().isoformat(),
                "total_products": len(products),
                "format_version": "1.0",
                "standard": "EAN13_JSON"
            },
            "products": products
        }
        
        return export_data
    except Exception as e:
        logger.error(f"Error exporting products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)