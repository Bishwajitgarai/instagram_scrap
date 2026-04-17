import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize rate limiter with a global limit of 60 requests per minute
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Instagram credentials
    INSTAGRAM_USERNAME: str = Field(..., env="INSTAGRAM_USERNAME")
    INSTAGRAM_PASSWORD: str = Field(..., env="INSTAGRAM_PASSWORD")
    
    # Browser settings
    HEADLESS: bool = Field(True, env="HEADLESS")
    USER_DATA_DIR: str = Field("./instagram_profile", env="USER_DATA_DIR")
    
    @field_validator("USER_DATA_DIR", mode="after")
    @classmethod
    def force_tmp_on_vercel(cls, v: str) -> str:
        if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
            return "/tmp/instagram_profile"
        return v
    
    # Browser configuration
    BROWSER_TIMEOUT: int = Field(60000, env="BROWSER_TIMEOUT")
    NAVIGATION_TIMEOUT: int = Field(45000, env="NAVIGATION_TIMEOUT")
    DEFAULT_TIMEOUT: int = Field(45000, env="DEFAULT_TIMEOUT")
    
    # API settings
    API_HOST: str = Field("0.0.0.0", env="API_HOST")
    API_PORT: int = Field(9010, env="API_PORT")
    
    # Scraping settings
    TOP_REELS_DEFAULT: int = Field(12, env="TOP_REELS_DEFAULT")
    MAX_PAGINATION_ITERATIONS: int = Field(50, env="MAX_PAGINATION_ITERATIONS")
    PAGINATION_DELAY: float = Field(1.0, env="PAGINATION_DELAY")
    TOP_DEFAULT: int = Field(12, env="TOP_REELS_DEFAULT")
    
    # Browser arguments
    BROWSER_ARGS: List[str] = Field([
        '--no-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-extensions',
        '--disable-plugins',
        '--disable-translate',
        '--disable-web-security',
        '--disable-features=site-per-process',
        '--disable-ipc-flooding-protection',
        '--aggressive-cache-discard',
        '--max_old_space_size=4096',
    ])
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get settings instance (useful for dependency injection)"""
    return settings