from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import os
import uuid
from datetime import datetime, timedelta
import logging
import hashlib
import secrets
from passlib.context import CryptContext
from jose import JWTError, jwt
from geopy.geocoders import Nominatim

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Local Shop Pro API", version="1.0.0", description="API pour la gestion de stock des commerçants locaux")

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'local-shop-pro-secret-key-2025')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

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
db = client.local_shop_pro
merchants_collection = db.merchants
products_collection = db.products

# Enhanced categories for French commerce
STANDARD_CATEGORIES = [
    "ALIMENTAIRE",
    "BOISSONS", 
    "BOULANGERIE_PATISSERIE",
    "BOUCHERIE_CHARCUTERIE",
    "POISSONNERIE",
    "FRUITS_LEGUMES",
    "EPICERIE_FINE",
    "PRODUITS_BIO",
    "HYGIENE_BEAUTE",
    "PHARMACIE_PARAPHARMACIE",
    "TEXTILE_MODE",
    "CHAUSSURES_MAROQUINERIE",
    "BIJOUTERIE_HORLOGERIE",
    "ELECTRONIQUE_INFORMATIQUE",
    "TELEPHONIE_ACCESSOIRES",
    "MAISON_DECORATION",
    "BRICOLAGE_JARDINAGE",
    "SPORT_LOISIRS",
    "LIBRAIRIE_PAPETERIE",
    "JOUETS_PUERICULTURE",
    "ARTISANAT_ART",
    "FLEURS_PLANTES",
    "AUTOMOBILE_MOTO",
    "TABAC_PRESSE",
    "OPTIQUE",
    "AUTO_ENTREPRENEUR",
    "SERVICES",
    "AUTRE"
]

SUBCATEGORIES = {
    "ALIMENTAIRE": ["CONSERVES", "SURGELES", "FRAIS", "SEC", "EPICERIE_GENERALE"],
    "BOISSONS": ["ALCOOLISEES", "NON_ALCOOLISEES", "CHAUDES", "VINS_SPIRITUEUX"],
    "BOULANGERIE_PATISSERIE": ["PAIN", "VIENNOISERIES", "PATISSERIES", "GATEAUX_COMMANDE"],
    "BOUCHERIE_CHARCUTERIE": ["VIANDE_FRAICHE", "VOLAILLE", "CHARCUTERIE", "PLATS_PREPARES"],
    "POISSONNERIE": ["POISSONS_FRAIS", "FRUITS_MER", "POISSONS_FUMES", "CONSERVES_MER"],
    "FRUITS_LEGUMES": ["FRUITS_FRAIS", "LEGUMES_FRAIS", "FRUITS_SECS", "LEGUMES_PREPARES"],
    "HYGIENE_BEAUTE": ["HYGIENE_CORPORELLE", "COSMETIQUES", "PARFUMS", "SOINS_VISAGE"],
    "TEXTILE_MODE": ["VETEMENTS_HOMME", "VETEMENTS_FEMME", "VETEMENTS_ENFANT", "ACCESSOIRES_MODE"],
    "ELECTRONIQUE_INFORMATIQUE": ["ORDINATEURS", "SMARTPHONES", "AUDIO_VIDEO", "ACCESSOIRES_TECH"],
    "MAISON_DECORATION": ["MOBILIER", "DECORATION", "TEXTILE_MAISON", "LUMINAIRES"],
    "ARTISANAT_ART": ["FAIT_MAIN", "MATERIAUX_CREATION", "OUTILS_ARTISANAT", "OEUVRES_ART"],
    "SPORT_LOISIRS": ["EQUIPEMENT_SPORT", "VETEMENTS_SPORT", "JEUX_SOCIETE", "LOISIRS_CREATIFS"],
    "BIJOUTERIE_HORLOGERIE": ["BIJOUX", "MONTRES", "REPARATION", "SUR_MESURE"],
    "AUTOMOBILE_MOTO": ["PIECES_DETACHEES", "ACCESSOIRES", "ENTRETIEN", "EQUIPEMENT"]
}

# Pydantic models
class MerchantLocation(BaseModel):
    address: str
    city: str
    postal_code: str
    country: str = "France"
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class MerchantProfile(BaseModel):
    business_name: str
    business_type: str
    siret: Optional[str] = None
    phone: Optional[str] = None
    location: MerchantLocation
    description: Optional[str] = None

class MerchantRegistration(BaseModel):
    email: EmailStr
    password: str
    profile: MerchantProfile

class MerchantLogin(BaseModel):
    email: EmailStr
    password: str

class Merchant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    password_hash: str
    profile: MerchantProfile
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    merchant_id: str
    name: str
    barcode: Optional[str] = None
    price: float
    cost_price: Optional[float] = None
    stock_quantity: int
    low_stock_threshold: int = 10
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    supplier: Optional[str] = None
    is_available: bool = True
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
    is_available: Optional[bool] = None

class StockAlert(BaseModel):
    product_id: str
    name: str
    current_stock: int
    threshold: int = 10

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    merchant_id: str
    business_name: str

class MerchantProfileResponse(BaseModel):
    id: str
    email: str
    profile: MerchantProfile
    is_active: bool
    created_at: datetime

# Utility functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_jwt_token(merchant_id: str) -> str:
    payload = {
        "merchant_id": merchant_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("merchant_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

async def get_current_merchant(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    merchant_id = verify_jwt_token(credentials.credentials)
    merchant = merchants_collection.find_one({"id": merchant_id, "is_active": True}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail="Commerçant introuvable")
    return merchant

def geocode_address(location: MerchantLocation) -> MerchantLocation:
    """Convert address to GPS coordinates"""
    try:
        geolocator = Nominatim(user_agent="local-shop-pro")
        full_address = f"{location.address}, {location.city}, {location.postal_code}, {location.country}"
        location_result = geolocator.geocode(full_address)
        
        if location_result:
            location.latitude = location_result.latitude
            location.longitude = location_result.longitude
            logger.info(f"Geocoded address: {location.latitude}, {location.longitude}")
        else:
            logger.warning(f"Could not geocode address: {full_address}")
        
        return location
    except Exception as e:
        logger.warning(f"Geocoding failed: {str(e)}")
        return location

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Local Shop Pro API", "timestamp": datetime.now()}

# Categories endpoint
@app.get("/api/categories")
async def get_categories():
    return {
        "categories": STANDARD_CATEGORIES,
        "subcategories": SUBCATEGORIES
    }

# Authentication endpoints
@app.post("/api/auth/register", response_model=TokenResponse)
async def register_merchant(registration: MerchantRegistration):
    try:
        # Check if email already exists
        existing_merchant = merchants_collection.find_one({"email": registration.email})
        if existing_merchant:
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
        
        # Geocode the address
        location_with_coords = geocode_address(registration.profile.location)
        registration.profile.location = location_with_coords
        
        # Create merchant
        merchant = Merchant(
            email=registration.email,
            password_hash=hash_password(registration.password),
            profile=registration.profile
        )
        
        # Save to database
        result = merchants_collection.insert_one(merchant.dict())
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Erreur lors de la création du compte")
        
        # Generate token
        token = create_jwt_token(merchant.id)
        
        logger.info(f"New merchant registered: {registration.email}")
        
        return TokenResponse(
            access_token=token,
            merchant_id=merchant.id,
            business_name=registration.profile.business_name
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'inscription")

@app.post("/api/auth/login", response_model=TokenResponse)
async def login_merchant(login: MerchantLogin):
    try:
        # Find merchant
        merchant = merchants_collection.find_one({"email": login.email, "is_active": True}, {"_id": 0})
        if not merchant:
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
        
        # Verify password
        if not verify_password(login.password, merchant["password_hash"]):
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
        
        # Generate token
        token = create_jwt_token(merchant["id"])
        
        logger.info(f"Merchant logged in: {login.email}")
        
        return TokenResponse(
            access_token=token,
            merchant_id=merchant["id"],
            business_name=merchant["profile"]["business_name"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=401, detail="Erreur lors de la connexion")

@app.get("/api/auth/profile", response_model=MerchantProfileResponse)
async def get_merchant_profile(current_merchant: dict = Depends(get_current_merchant)):
    try:
        return MerchantProfileResponse(
            id=current_merchant["id"],
            email=current_merchant["email"],
            profile=current_merchant["profile"],
            is_active=current_merchant["is_active"],
            created_at=current_merchant["created_at"]
        )
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération du profil")

# Products endpoints (protected)
@app.post("/api/products", response_model=Product)
async def create_product(product: Product, current_merchant: dict = Depends(get_current_merchant)):
    try:
        # Associate product with current merchant
        product.merchant_id = current_merchant["id"]
        
        # Calculate margin if cost_price is provided
        margin = None
        if product.cost_price and product.price > product.cost_price:
            margin = ((product.price - product.cost_price) / product.price) * 100
        
        product_dict = product.dict()
        if margin:
            product_dict["margin"] = round(margin, 2)
        
        result = products_collection.insert_one(product_dict)
        if result.inserted_id:
            logger.info(f"Created product: {product.name} for merchant: {current_merchant['profile']['business_name']}")
            return product
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la création du produit")
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products", response_model=List[Product])
async def get_products(
    current_merchant: dict = Depends(get_current_merchant),
    category: Optional[str] = None, 
    search: Optional[str] = None
):
    try:
        query = {"merchant_id": current_merchant["id"]}
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
async def get_product(product_id: str, current_merchant: dict = Depends(get_current_merchant)):
    try:
        product = products_collection.find_one({
            "id": product_id, 
            "merchant_id": current_merchant["id"]
        }, {"_id": 0})
        
        if not product:
            raise HTTPException(status_code=404, detail="Produit introuvable")
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/products/{product_id}", response_model=Product)
async def update_product(
    product_id: str, 
    product_update: ProductUpdate,
    current_merchant: dict = Depends(get_current_merchant)
):
    try:
        update_data = {k: v for k, v in product_update.dict().items() if v is not None}
        update_data["updated_at"] = datetime.now()
        
        # Recalculate margin if price or cost_price changed
        existing_product = products_collection.find_one({
            "id": product_id, 
            "merchant_id": current_merchant["id"]
        }, {"_id": 0})
        
        if not existing_product:
            raise HTTPException(status_code=404, detail="Produit introuvable")
        
        new_price = update_data.get("price", existing_product.get("price"))
        new_cost_price = update_data.get("cost_price", existing_product.get("cost_price"))
        
        if new_price and new_cost_price and new_price > new_cost_price:
            margin = ((new_price - new_cost_price) / new_price) * 100
            update_data["margin"] = round(margin, 2)
        
        result = products_collection.update_one(
            {"id": product_id, "merchant_id": current_merchant["id"]},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Produit introuvable")
        
        updated_product = products_collection.find_one({
            "id": product_id, 
            "merchant_id": current_merchant["id"]
        }, {"_id": 0})
        
        logger.info(f"Updated product: {product_id}")
        return updated_product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str, current_merchant: dict = Depends(get_current_merchant)):
    try:
        result = products_collection.delete_one({
            "id": product_id, 
            "merchant_id": current_merchant["id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Produit introuvable")
        
        logger.info(f"Deleted product: {product_id}")
        return {"message": "Produit supprimé avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_merchant: dict = Depends(get_current_merchant)):
    try:
        merchant_id = current_merchant["id"]
        
        total_products = products_collection.count_documents({"merchant_id": merchant_id})
        
        # Count products with low stock using their individual thresholds
        low_stock_pipeline = [
            {"$match": {"merchant_id": merchant_id, "$expr": {"$lte": ["$stock_quantity", "$low_stock_threshold"]}}},
            {"$count": "low_stock_count"}
        ]
        low_stock_result = list(products_collection.aggregate(low_stock_pipeline))
        low_stock_products = low_stock_result[0]["low_stock_count"] if low_stock_result else 0
        
        # Total stock value
        pipeline = [
            {"$match": {"merchant_id": merchant_id}},
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
            {"$match": {"merchant_id": merchant_id}},
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
            "category_breakdown": category_stats,
            "merchant_info": {
                "business_name": current_merchant["profile"]["business_name"],
                "business_type": current_merchant["profile"]["business_type"]
            }
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts/low-stock", response_model=List[StockAlert])
async def get_low_stock_alerts(current_merchant: dict = Depends(get_current_merchant)):
    try:
        # Find products where stock_quantity <= low_stock_threshold
        products = list(products_collection.find(
            {
                "merchant_id": current_merchant["id"],
                "$expr": {"$lte": ["$stock_quantity", "$low_stock_threshold"]}
            },
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
async def export_products(current_merchant: dict = Depends(get_current_merchant)):
    """Export merchant's products in standardized JSON format for external systems"""
    try:
        products = list(products_collection.find({"merchant_id": current_merchant["id"]}, {"_id": 0}))
        
        # Standardized export format
        export_data = {
            "export_info": {
                "timestamp": datetime.now().isoformat(),
                "total_products": len(products),
                "format_version": "1.0",
                "standard": "LOCAL_SHOP_PRO_JSON",
                "merchant": {
                    "id": current_merchant["id"],
                    "business_name": current_merchant["profile"]["business_name"],
                    "location": current_merchant["profile"]["location"]
                }
            },
            "products": products
        }
        
        return export_data
    except Exception as e:
        logger.error(f"Error exporting products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Public endpoint for future customer app
@app.get("/api/public/search")
async def search_products_public(
    latitude: float,
    longitude: float,
    radius_km: float = 10,
    category: Optional[str] = None,
    search: Optional[str] = None
):
    """Public endpoint for customer app to search products by location"""
    try:
        # This is a placeholder for your future customer app
        # It will search for products within radius and return with merchant info
        
        query = {"is_available": True}
        if category:
            query["category"] = category
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        # For now, return structure that your future app can use
        return {
            "search_params": {
                "latitude": latitude,
                "longitude": longitude,
                "radius_km": radius_km,
                "category": category,
                "search": search
            },
            "message": "Endpoint prêt pour l'application client",
            "note": "Implémentation complète prévue pour l'app de recherche"
        }
    
    except Exception as e:
        logger.error(f"Error in public search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)