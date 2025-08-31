import os
from typing import Optional

class Settings:
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Database/Files
    OUTPUT_JSON: str = os.getenv("OUTPUT_JSON", "output.json")
    LOCATIONS_CSV: str = os.getenv("LOCATIONS_CSV", "locations.csv")
    TOKEN_PATH: str = os.getenv("TOKEN_PATH", "token.txt")
    
    # Security
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
    
    # API URLs
    API_BASE_URL: str = os.getenv("API_BASE_URL", "")
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

settings = Settings()